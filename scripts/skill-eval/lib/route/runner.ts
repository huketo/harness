/**
 * Description-based routing runner: one classification call per distinct
 * prompt of a routing file, graded against the expected skill, written to
 * `<out-root>/<suite>/run-<time>/` as `results.json`, `report.md`, and the
 * call transcripts. It reuses the skill-eval runner's `Deps`, so tests inject a
 * fake `runAgent` and call no model.
 */

import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { parseTranscript } from "../run/agent.ts";
import { DEFAULT_MODEL } from "../run/cli.ts";
import { type Deps, defaultDeps } from "../run/runner.ts";
import { gitText } from "../run/skills.ts";
import { parseRouting, type RoutePrompt } from "./cases.ts";
import {
	gradeAnswer,
	readDescriptions,
	ROUTE_SCOPE,
	ROUTE_TITLE,
	routeArgs,
	routeRequest,
	type SkillDescription,
	type Verdict,
	VERDICTS,
} from "./classify.ts";

export const USAGE =
	"usage: node scripts/skill-eval/route.ts --cases <routing.json> [--ref <gitref>] [--model <m>] [--effort <e>] [--parallel <p>] [--out-root <dir>] [--dry-run]";

const DEFAULT_PARALLEL = 4;
const CALL_TIMEOUT_MS = 180_000;

interface RouteOptions {
	cases: string;
	ref: string;
	model: string;
	effort: string | null;
	parallel: number;
	outRoot?: string;
	dryRun: boolean;
}

export interface RoutedPrompt extends RoutePrompt {
	answer: string | null;
	verdict: Verdict;
	rc: number | null;
	timedOut: boolean;
	costUsd: number | null;
}

export interface RouteResults {
	title: string;
	scope: string;
	suite: string;
	version: number;
	ref: string;
	descriptionsCommit: string;
	harnessCommit: string;
	model: string;
	effort: string | null;
	startedAt: string;
	candidates: SkillDescription[];
	totals: { prompts: number } & Record<Verdict, number>;
	prompts: RoutedPrompt[];
}

function parseCli(argv: string[]): RouteOptions {
	const { values, positionals } = parseArgs({
		args: argv,
		strict: true,
		allowPositionals: true,
		options: {
			cases: { type: "string" },
			ref: { type: "string" },
			model: { type: "string" },
			effort: { type: "string" },
			parallel: { type: "string" },
			"out-root": { type: "string" },
			"dry-run": { type: "boolean", default: false },
		},
	});
	if (positionals.length) throw new Error(`unexpected argument "${positionals[0]}"`);
	if (!values.cases) throw new Error("--cases is required");
	if (values.parallel !== undefined && !/^[1-9][0-9]*$/.test(values.parallel))
		throw new Error(`--parallel: positive integer required, got "${values.parallel}"`);
	return {
		cases: values.cases,
		ref: values.ref ?? "HEAD",
		model: values.model ?? DEFAULT_MODEL,
		effort: values.effort ?? null,
		parallel: values.parallel ? Number(values.parallel) : DEFAULT_PARALLEL,
		outRoot: values["out-root"],
		dryRun: values["dry-run"] ?? false,
	};
}

export async function main(argv: string[], partial: Partial<Deps> = {}): Promise<number> {
	const warn = partial.warn ?? ((l: string) => console.error(l));
	let opts: RouteOptions;
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

const shellWord = (arg: string) => (/^[\w./=:@-]+$/.test(arg) ? arg : JSON.stringify(arg));

async function execute(opts: RouteOptions, deps: Deps): Promise<number> {
	const { log } = deps;
	const casesFile = resolve(deps.cwd, opts.cases);
	const routing = parseRouting(readFileSync(casesFile, "utf8"), casesFile);
	const { sha, skills } = readDescriptions(deps.repoRoot, opts.ref, routing.candidates);
	const { prompts } = routing;

	if (opts.dryRun) {
		const args = routeArgs({ request: "<request>", model: opts.model, effort: opts.effort });
		log(`${ROUTE_TITLE}: ${routing.suite} v${routing.version} (dry run; no model is called)`);
		log(ROUTE_SCOPE);
		log(`descriptions: skills/<name>/SKILL.md at ${sha} (${opts.ref})`);
		log(`${prompts.length} prompts, ${prompts.length} classification calls`);
		log(`command: ${deps.agentCommand} ${args.map((a) => (a === "<request>" ? a : shellWord(a))).join(" ")}`);
		log("request (the prompt replaces {prompt}):");
		log(routeRequest(skills, "{prompt}"));
		log("prompts:");
		const width = Math.max(...prompts.map((p) => p.expected.length));
		for (const p of prompts) log(`${p.id} expect ${p.expected.padEnd(width)} | ${p.prompt}`);
		return 0;
	}

	const startedAt = deps.now();
	const runId = `run-${startedAt.toISOString().replace(/\.\d+Z$/, "Z").replaceAll(":", "-")}`;
	const outRoot = opts.outRoot ? resolve(deps.cwd, opts.outRoot) : join(deps.repoRoot, "var", "skill-eval", "route");
	const runDir = join(outRoot, routing.suite, runId);
	mkdirSync(join(runDir, ".."), { recursive: true });
	try {
		// Not recursive, so a second run that picked the same directory fails here instead of sharing it.
		mkdirSync(runDir);
	} catch (e) {
		if ((e as NodeJS.ErrnoException).code === "EEXIST") throw new Error(`${runDir} already exists`);
		throw e;
	}
	const transcripts = join(runDir, "transcripts");
	mkdirSync(transcripts);
	mkdirSync(deps.tmpRoot, { recursive: true });
	const workRoot = mkdtempSync(join(deps.tmpRoot, `route-${routing.suite}-`));

	const routed: RoutedPrompt[] = [];
	const classify = async (p: RoutePrompt) => {
		const cwd = join(workRoot, p.id);
		mkdirSync(cwd, { recursive: true });
		const stdoutPath = join(transcripts, `${p.id}.jsonl`);
		const outcome = await deps.runAgent({
			command: deps.agentCommand,
			args: routeArgs({ request: routeRequest(skills, p.prompt), model: opts.model, effort: opts.effort }),
			cwd,
			env: deps.env,
			timeoutMs: CALL_TIMEOUT_MS,
			stdoutPath,
			stderrPath: join(transcripts, `${p.id}.stderr.log`),
		});
		const summary = parseTranscript(existsSync(stdoutPath) ? readFileSync(stdoutPath, "utf8") : "");
		const finished = outcome.rc === 0 && !outcome.timedOut;
		const graded = gradeAnswer(summary.final, finished, p.expected, routing.candidates);
		routed.push({ ...p, ...graded, rc: outcome.rc, timedOut: outcome.timedOut, costUsd: summary.costUsd });
		log(`${p.id} expect ${p.expected} got ${graded.answer ?? "-"} ${graded.verdict}`);
	};
	const queue = [...prompts];
	try {
		await Promise.all(
			Array.from({ length: Math.min(opts.parallel, queue.length) }, async () => {
				for (let p = queue.shift(); p; p = queue.shift()) await classify(p);
			}),
		);
	} finally {
		rmSync(workRoot, { recursive: true, force: true });
	}
	routed.sort((a, b) => a.id.localeCompare(b.id, "en", { numeric: true }));

	const totals = { prompts: routed.length, ...Object.fromEntries(VERDICTS.map((v) => [v, 0])) } as RouteResults["totals"];
	for (const r of routed) totals[r.verdict]++;
	const results: RouteResults = {
		title: ROUTE_TITLE,
		scope: ROUTE_SCOPE,
		suite: routing.suite,
		version: routing.version,
		ref: opts.ref,
		descriptionsCommit: sha,
		harnessCommit: gitText(["rev-parse", "HEAD"], deps.repoRoot),
		model: opts.model,
		effort: opts.effort,
		startedAt: startedAt.toISOString(),
		candidates: skills,
		totals,
		prompts: routed,
	};
	writeFileSync(join(runDir, "results.json"), `${JSON.stringify(results, null, 2)}\n`);
	writeFileSync(join(runDir, "report.md"), renderReport(results));
	log(`${totals.correct} of ${totals.prompts} prompts routed as expected (${runDir}/report.md)`);
	return totals.correct === totals.prompts ? 0 : 1;
}

/** A Markdown code span that survives backticks, pipes, and newlines in `text`. */
function code(text: string): string {
	const flat = text.replace(/\s*\n\s*/g, " ").replaceAll("|", "\\|");
	const fence = "`".repeat(Math.max(0, ...[...flat.matchAll(/`+/g)].map((m) => m[0].length)) + 1);
	const pad = flat.startsWith("`") || flat.endsWith("`") ? " " : "";
	return `${fence}${pad}${flat}${pad}${fence}`;
}

const hangul = /[가-힣]/;

export function renderReport(r: RouteResults): string {
	const t = r.totals;
	const share = (list: RoutedPrompt[]) => `${list.filter((p) => p.verdict === "correct").length} of ${list.length}`;
	const lines = [
		`# ${r.title}: ${r.suite} v${r.version}`,
		"",
		r.scope,
		"",
		`- Descriptions: \`skills/<name>/SKILL.md\` at \`${r.descriptionsCommit}\` (\`${r.ref}\`)`,
		`- Model: \`${r.model}\`, effort: ${r.effort ?? "default"}`,
		`- Prompts: ${t.prompts}, one classification call each`,
		`- Routed as expected: ${t.correct} of ${t.prompts} (another skill ${t.wrong}, none ${t.none}, malformed ${t.malformed}, failed ${t.failed})`,
		`- Korean prompts: ${share(r.prompts.filter((p) => hangul.test(p.prompt)))}; other prompts: ${share(r.prompts.filter((p) => !hangul.test(p.prompt)))}`,
		"",
		"## By expected answer",
		"",
		"| Expected | Routed as expected |",
		"| --- | --- |",
	];
	for (const expected of [...r.candidates.map((c) => c.name), "none"]) {
		const list = r.prompts.filter((p) => p.expected === expected);
		if (list.length) lines.push(`| ${expected} | ${share(list)} |`);
	}
	lines.push("", "## Not routed as expected", "");
	const misses = r.prompts.filter((p) => p.verdict !== "correct");
	if (!misses.length) lines.push("None.");
	else {
		lines.push("| Id | Prompt | Expected | Answer | Verdict |", "| --- | --- | --- | --- | --- |");
		for (const p of misses) {
			const answer = p.answer === null ? "(no answer)" : p.verdict === "malformed" ? code(p.answer) : p.answer;
			lines.push(`| ${p.id} | ${code(p.prompt)} | ${p.expected} | ${answer} | ${p.verdict} |`);
		}
	}
	return `${lines.join("\n")}\n`;
}
