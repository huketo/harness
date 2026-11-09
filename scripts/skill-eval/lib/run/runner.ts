/**
 * Runner orchestration: select (case, arm, run) triples, prepare or resume the
 * iteration directory, materialize each arm's skills once, and execute every
 * run in its own temporary workspace. `main` takes injectable dependencies so
 * tests run without a real agent or the real repository.
 */

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { type IterationMeta, type RunMeta, type Suite, validateSuite } from "../schema.ts";
import { type AgentRunner, agentEnv, buildAgentArgs, parseTranscript, spawnAgent, systemAppendText } from "./agent.ts";
import { buildPatch, computeChanges } from "./changes.ts";
import { type CliOptions, DEFAULT_MODEL, DEFAULT_RUNS, DEFAULT_TIMEOUT_SEC, parseCli, USAGE } from "./cli.ts";
import { copyTree, workspaceExclude } from "./files.ts";
import { gitText, type Materialized, materializeArm, resolveRef } from "./skills.ts";

export interface Deps {
	/** This repository's root: local skill paths and `harnessCommit` resolve here. */
	repoRoot: string;
	/** Root of the per-run agent workspaces (contract: `/tmp/skill-eval`). */
	tmpRoot: string;
	cwd: string;
	runAgent: AgentRunner;
	agentCommand: string;
	env: Record<string, string>;
	log: (line: string) => void;
	warn: (line: string) => void;
	now: () => Date;
}

export function defaultDeps(): Deps {
	return {
		repoRoot: gitText(["rev-parse", "--show-toplevel"], import.meta.dirname),
		tmpRoot: "/tmp/skill-eval",
		cwd: process.cwd(),
		runAgent: spawnAgent,
		agentCommand: "claude",
		env: agentEnv(),
		log: (l) => console.log(l),
		warn: (l) => console.error(l),
		now: () => new Date(),
	};
}

interface PlannedRun {
	caseId: string;
	arm: string;
	run: number;
	skip: boolean;
}

const json = (v: unknown) => `${JSON.stringify(v, null, 2)}\n`;

export function iterationNumbers(suiteDir: string): number[] {
	if (!existsSync(suiteDir)) return [];
	return readdirSync(suiteDir)
		.map((n) => /^iteration-([1-9][0-9]*)$/.exec(n)?.[1])
		.filter((n): n is string => !!n)
		.map(Number)
		.sort((a, b) => a - b);
}

function textDiff(a: string, b: string): string {
	const res = spawnSync("diff", ["-u", a, b]);
	return res.stdout?.toString() ?? "";
}

export async function main(argv: string[], partial: Partial<Deps> = {}): Promise<number> {
	const warn = partial.warn ?? ((l: string) => console.error(l));
	let opts: CliOptions;
	try {
		opts = parseCli(argv);
	} catch (e) {
		warn(`${(e as Error).message}\n${USAGE}`);
		return 2;
	}
	try {
		return await execute(opts, { ...defaultDeps(), ...partial });
	} catch (e) {
		warn(`error: ${(e as Error).message}`);
		return 1;
	}
}

async function execute(opts: CliOptions, deps: Deps): Promise<number> {
	const { log, warn } = deps;
	const suiteFile = resolve(deps.cwd, opts.suite);
	const suiteBytes = readFileSync(suiteFile);
	let suite: Suite;
	try {
		suite = JSON.parse(suiteBytes.toString("utf8"));
	} catch (e) {
		warn(`${suiteFile}: invalid JSON (${(e as Error).message})`);
		return 1;
	}
	const errors = validateSuite(suite, suiteFile);
	if (errors.length) {
		warn(`${suiteFile}: suite is invalid; nothing was run`);
		for (const e of errors) warn(`  ${e}`);
		return 1;
	}
	const fixtureRoot = join(dirname(suiteFile), "fixtures");

	// Selection.
	const cases = opts.cases
		? opts.cases.map((id) => {
				const c = suite.cases.find((x) => x.id === id);
				if (!c) throw new Error(`--case: unknown case "${id}"`);
				return c;
			})
		: suite.cases;
	for (const a of opts.arms ?? []) if (!(a in suite.arms)) throw new Error(`--arm: unknown arm "${a}"`);
	for (const a of Object.keys(opts.refs)) {
		if (!(a in suite.arms)) throw new Error(`--ref: unknown arm "${a}"`);
		if (!suite.arms[a].skills.some((s) => s.source === "local"))
			throw new Error(`--ref: arm "${a}" has no local skill`);
	}
	const dashed = cases.filter((c) => c.prompt.startsWith("-")).map((c) => c.id);
	if (dashed.length) throw new Error(`prompt starts with "-" and would be read as a flag: ${dashed.join(", ")}`);

	// Iteration.
	const outRoot = opts.outRoot ? resolve(deps.cwd, opts.outRoot) : join(deps.repoRoot, "var", "skill-eval");
	const suiteDir = join(outRoot, suite.suite);
	const iteration = opts.iteration ?? (iterationNumbers(suiteDir).at(-1) ?? 0) + 1;
	const iterDir = join(suiteDir, `iteration-${iteration}`);
	const metaFile = join(iterDir, "iteration.json");
	const existing: IterationMeta | null = existsSync(metaFile) ? JSON.parse(readFileSync(metaFile, "utf8")) : null;
	const snapshot = join(iterDir, "suite.json");
	if (existing && existsSync(snapshot) && !readFileSync(snapshot).equals(suiteBytes)) {
		const diff = textDiff(snapshot, suiteFile);
		if (!opts.force) {
			warn(`${snapshot} differs from ${suiteFile}; start a new iteration or pass --force to continue anyway`);
			if (diff) warn(diff.trimEnd());
			return 1;
		}
		warn(`warning: ${snapshot} differs from ${suiteFile}; continuing with --force, snapshot kept`);
		if (diff) warn(diff.trimEnd());
	}
	if (existing && existing.suite !== suite.suite)
		throw new Error(`${metaFile} belongs to suite "${existing.suite}", not "${suite.suite}"`);
	const model = opts.model ?? existing?.model ?? DEFAULT_MODEL;
	const effort = opts.effort ?? existing?.effort ?? null;
	if (existing && (model !== existing.model || effort !== existing.effort))
		throw new Error(
			`iteration ${iteration} ran model=${existing.model} effort=${existing.effort}; ` +
				`this invocation asks for model=${model} effort=${effort}. Start a new iteration instead.`,
		);
	const runs = opts.runs ?? existing?.runs ?? DEFAULT_RUNS;

	// Plan.
	const plan: PlannedRun[] = [];
	for (const c of cases) {
		const arms = c.arms.filter((a) => !opts.arms || opts.arms.includes(a));
		for (const arm of arms)
			for (let k = 1; k <= runs; k++) {
				const done = existsSync(join(iterDir, c.id, arm, `run-${k}`, "meta.json"));
				plan.push({ caseId: c.id, arm, run: k, skip: done && !opts.force });
			}
	}
	if (!plan.length) throw new Error("no (case, arm) pair matches the selection");
	const plannedArms = [...new Set(plan.map((p) => p.arm))];

	// Local refs: --ref, else the ref this iteration already recorded, else the skill's ref or HEAD.
	const localRefs: Record<string, string> = { ...(existing?.localRefs ?? {}) };
	for (const arm of plannedArms) {
		const locals = suite.arms[arm].skills.filter((s) => s.source === "local");
		if (!locals.length) continue;
		const recorded = existing?.localRefs?.[arm];
		const shas = new Set(
			locals.map((s) =>
				resolveRef(deps.repoRoot, opts.refs[arm] ?? recorded ?? ("ref" in s && s.ref ? s.ref : "HEAD")),
			),
		);
		if (shas.size > 1) throw new Error(`arm ${arm}: local skills resolve to different commits (${[...shas].join(", ")})`);
		const sha = [...shas][0];
		if (recorded && recorded !== sha)
			throw new Error(`arm ${arm}: iteration ${iteration} used ${recorded}, --ref resolves to ${sha}. Start a new iteration instead.`);
		localRefs[arm] = sha;
	}
	const harnessCommit = gitText(["rev-parse", "HEAD"], deps.repoRoot);

	if (opts.dryRun) {
		log(`suite ${suite.suite} v${suite.version}: iteration ${iteration} (${existing ? "resume" : "new"}) in ${iterDir}`);
		log(`model ${model} effort ${effort ?? "-"} runs ${runs} parallel ${opts.parallel}`);
		for (const arm of plannedArms) {
			const skills = suite.arms[arm].skills;
			if (!skills.length) log(`arm ${arm}: no skills`);
			for (const s of skills) {
				if (s.source === "local") log(`arm ${arm}: local ${s.path} @ ${localRefs[arm]}`);
				else log(`arm ${arm}: ${s.source} ${suite.sources[s.source].repo} ${s.path} @ ${suite.sources[s.source].commit}`);
			}
		}
		for (const p of plan) log(`${p.caseId} ${p.arm} run-${p.run}${p.skip ? " (skip: meta.json exists)" : ""}`);
		log(`${plan.filter((p) => !p.skip).length} to run, ${plan.filter((p) => p.skip).length} to skip`);
		return 0;
	}

	// Iteration files.
	mkdirSync(iterDir, { recursive: true });
	if (!existsSync(snapshot)) writeFileSync(snapshot, suiteBytes);
	const union = (a: string[] = [], b: string[]) => [...new Set([...a, ...b])];
	const meta: IterationMeta = {
		suite: suite.suite,
		suiteVersion: suite.version,
		iteration,
		createdAt: existing?.createdAt ?? deps.now().toISOString(),
		harnessCommit: existing?.harnessCommit ?? harnessCommit,
		model,
		effort,
		runs: Math.max(runs, existing?.runs ?? 0),
		cases: union(existing?.cases, cases.map((c) => c.id)),
		arms: union(existing?.arms, plannedArms),
		sources: suite.sources,
		localRefs,
	};
	writeFileSync(metaFile, json(meta));

	// Materialize the skills of every arm that has work to do.
	const todo = plan.filter((p) => !p.skip);
	const tmpIter = join(deps.tmpRoot, suite.suite, `iteration-${iteration}`);
	const materialized = new Map<string, Materialized[]>();
	for (const arm of new Set(todo.map((p) => p.arm)))
		materialized.set(
			arm,
			materializeArm(suite.arms[arm], join(tmpIter, ".materialized", arm), {
				repoRoot: deps.repoRoot,
				outRoot,
				sources: suite.sources,
				localSha: localRefs[arm],
			}),
		);

	// A case judgement compares arms; any new run makes the old one stale.
	for (const caseId of new Set(todo.map((p) => p.caseId))) {
		const judge = join(iterDir, caseId, "judge.json");
		if (existsSync(judge)) {
			rmSync(judge);
			warn(`removed stale ${judge}`);
		}
	}

	let ok = 0;
	let failed = 0;
	const skipped = plan.length - todo.length;
	for (const p of plan) if (p.skip) log(`${p.caseId} ${p.arm} run-${p.run} skipped`);

	const runOne = async (p: PlannedRun) => {
		const c = cases.find((x) => x.id === p.caseId)!;
		const label = `${p.caseId} ${p.arm} run-${p.run}`;
		try {
			const skills = materialized.get(p.arm) ?? [];
			const tmpRun = join(tmpIter, p.caseId, p.arm, `run-${p.run}`);
			const sysFile = `${tmpRun}.system.md`;
			const outRun = join(iterDir, p.caseId, p.arm, `run-${p.run}`);
			const fixture = c.fixture === null ? null : join(fixtureRoot, c.fixture);
			rmSync(tmpRun, { recursive: true, force: true });
			rmSync(sysFile, { force: true });
			rmSync(outRun, { recursive: true, force: true });
			mkdirSync(tmpRun, { recursive: true });
			mkdirSync(outRun, { recursive: true });
			if (fixture) copyTree(fixture, tmpRun, workspaceExclude);
			for (const s of skills) copyTree(s.dir, join(tmpRun, ".skills", s.meta.name));
			let appendFile: string | null = null;
			if (skills.length) {
				const text = systemAppendText(
					skills.map((s) => ({ name: s.meta.name, skillMd: readFileSync(join(s.dir, "SKILL.md"), "utf8") })),
				);
				writeFileSync(sysFile, text);
				writeFileSync(join(outRun, "system-append.md"), text);
				appendFile = sysFile;
			}
			const transcriptFile = join(outRun, "transcript.jsonl");
			const startedAt = deps.now();
			const t0 = performance.now();
			const outcome = await deps.runAgent({
				command: deps.agentCommand,
				args: buildAgentArgs({ prompt: c.prompt, model, effort, appendFile }),
				cwd: tmpRun,
				env: deps.env,
				timeoutMs: (c.timeoutSec ?? DEFAULT_TIMEOUT_SEC) * 1000,
				stdoutPath: transcriptFile,
				stderrPath: join(outRun, "stderr.log"),
			});
			const secs = Math.round((performance.now() - t0) / 100) / 10;
			const summary = parseTranscript(existsSync(transcriptFile) ? readFileSync(transcriptFile, "utf8") : "");
			writeFileSync(join(outRun, "final.md"), summary.final ?? "");
			const captured = join(outRun, "workspace");
			copyTree(tmpRun, captured, workspaceExclude);
			const changes = computeChanges(fixture, captured);
			writeFileSync(join(outRun, "changes.json"), json(changes));
			writeFileSync(join(outRun, "diff.patch"), buildPatch(fixture, captured, changes));
			const runMeta: RunMeta = {
				case: p.caseId,
				arm: p.arm,
				run: p.run,
				model,
				effort,
				rc: outcome.rc,
				timedOut: outcome.timedOut,
				secs,
				startedAt: startedAt.toISOString(),
				usage: summary.usage,
				costUsd: summary.costUsd,
				numTurns: summary.numTurns,
				skills: skills.map((s) => s.meta),
				suiteVersion: suite.version,
				harnessCommit,
			};
			writeFileSync(join(outRun, "meta.json"), json(runMeta));
			if (outcome.rc === 0 && !outcome.timedOut) ok++;
			else failed++;
			log(`${label} rc=${outcome.rc} ${secs}s${outcome.timedOut ? " (timed out)" : ""}`);
		} catch (e) {
			failed++;
			log(`${label} failed: ${(e as Error).message}`);
		}
	};

	const queue = [...todo];
	const workers = Array.from({ length: Math.min(opts.parallel, queue.length) }, async () => {
		for (let p = queue.shift(); p; p = queue.shift()) await runOne(p);
	});
	await Promise.all(workers);
	log(`done: ${ok} ok, ${failed} failed, ${skipped} skipped (${iterDir})`);
	return failed ? 1 : 0;
}
