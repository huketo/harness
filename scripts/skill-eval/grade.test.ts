import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, test } from "node:test";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { gradeIteration, parseGradeArgs, type GradeOptions } from "./grade.ts";
import { gradeRun } from "./lib/grade/checks.ts";
import {
	assignLabels,
	buildJudgeArgs,
	judgeSeed,
	makeRedactor,
	parseJudgeAnswer,
	redactionTerms,
	type JudgeInvoker,
	type JudgeRequest,
} from "./lib/grade/judge.ts";
import { listFiles } from "./lib/grade/layout.ts";
import type { Renderer } from "./lib/grade/render.ts";
import type { Benchmark } from "./lib/grade/benchmark.ts";
import type { CaseJudgement, IterationMeta, RunGrading, RunMeta, Suite } from "./lib/schema.ts";

const EMIL_COMMIT = "f1090bec277140d02ed202440185ad9d02ac1490";
const ITERATION = 3;

const suite: Suite = {
	suite: "demo-suite",
	version: 1,
	sources: { emil: { repo: "https://github.com/emilkowalski/skills", commit: EMIL_COMMIT } },
	arms: {
		none: { skills: [] },
		ai: { skills: [{ source: "local", path: "skills/awesome-interface" }] },
		"emil-animate": { skills: [{ source: "emil", path: "skills/animate" }] },
	},
	cases: [
		{
			id: "c1",
			title: "Card",
			covers: ["animate"],
			prompt: "Fix the card layout on index.html.",
			fixture: null,
			arms: ["none", "ai", "emil-animate"],
			expectations: ["The card fits a phone screen.", "The card keeps its title."],
			rubric: ["Visual quality", "Scope discipline"],
			checks: [
				{ id: "unchanged-ok", type: "unchanged", paths: ["keep.txt"] },
				{ id: "unchanged-bad", type: "unchanged", paths: ["index.html"] },
				{ id: "changed-ok", type: "changed", paths: ["index.html"] },
				{ id: "changed-bad", type: "changed", paths: ["keep.txt"] },
				{ id: "only-ok", type: "only-changed", allow: ["*.html", "new/**"] },
				{ id: "only-bad", type: "only-changed", allow: ["*.css"] },
				{ id: "present-ok", type: "present", files: "**/*.html", pattern: "card" },
				{ id: "present-bad", type: "present", files: "**/*.html", pattern: "zzz" },
				{ id: "absent-ok", type: "absent", files: "**/*.html", pattern: "marquee" },
				{ id: "absent-bad", type: "absent", files: "**/*.html", pattern: "card" },
				{ id: "mentions-ok", type: "final-mentions", pattern: "card", flags: "i" },
				{ id: "mentions-bad", type: "final-mentions", pattern: "nothing-here" },
				{ id: "omits-ok", type: "final-omits", pattern: "nothing-here" },
				{ id: "omits-bad", type: "final-omits", pattern: "CARD", flags: "i" },
				{
					id: "render",
					type: "render",
					entry: "index.html",
					widths: [390, 768, 1280],
					schemes: ["light", "dark"],
					assert: ["no-horizontal-overflow", "no-console-errors"],
				},
			],
		},
		{
			id: "c2",
			title: "Menu",
			covers: ["animate"],
			prompt: "Animate the menu.",
			fixture: null,
			arms: ["ai", "emil-animate"],
			expectations: ["The menu opens."],
			rubric: ["Motion quality"],
			checks: [{ id: "mentions-menu", type: "final-mentions", pattern: "menu" }],
		},
	],
};

const iterationMeta: IterationMeta = {
	suite: suite.suite,
	suiteVersion: 1,
	iteration: ITERATION,
	createdAt: "2026-11-04T00:00:00.000Z",
	harnessCommit: "3cf1ee6000000000000000000000000000000000",
	model: "claude-opus-5-5",
	effort: null,
	runs: 1,
	cases: ["c1", "c2"],
	arms: ["none", "ai", "emil-animate"],
	sources: suite.sources,
	localRefs: { ai: "3cf1ee6000000000000000000000000000000000" },
};

function meta(caseId: string, arm: string, over: Partial<RunMeta>): RunMeta {
	return {
		case: caseId,
		arm,
		run: 1,
		model: "claude-opus-5-5",
		effort: null,
		rc: 0,
		timedOut: false,
		secs: 1,
		startedAt: "2026-11-04T00:00:00.000Z",
		usage: { inputTokens: 1, outputTokens: 1, cacheReadTokens: 0, cacheCreationTokens: 0 },
		costUsd: null,
		numTurns: 1,
		skills: [],
		suiteVersion: 1,
		harnessCommit: iterationMeta.harnessCommit,
		...over,
	};
}

const usage = (outputTokens: number) => ({ inputTokens: 10, outputTokens, cacheReadTokens: 0, cacheCreationTokens: 0 });

function put(file: string, content: string | object): void {
	mkdirSync(dirname(file), { recursive: true });
	writeFileSync(file, typeof content === "string" ? content : JSON.stringify(content));
}

let root: string;
let iterDir: string;
const runDir = (c: string, arm: string, k = 1) => join(iterDir, c, arm, `run-${k}`);

/**
 * c1/none and c1/ai: complete runs with the same file changes; ai's text
 * carries identifying names. c1/emil-animate: timed out with meta.json only.
 * c2/ai: complete. c2/emil-animate: failed (no meta.json).
 */
function writeIteration(): void {
	put(join(iterDir, "iteration.json"), iterationMeta);
	put(join(iterDir, "suite.json"), suite);
	const changes = { added: ["new/a.html"], modified: ["index.html"], deleted: [] };
	for (const arm of ["none", "ai"]) {
		const dir = runDir("c1", arm);
		put(join(dir, "changes.json"), changes);
		put(join(dir, "workspace/keep.txt"), "keep\n");
		put(join(dir, "workspace/new/a.html"), "<p>new</p>\n");
		put(join(dir, "transcript.jsonl"), '{"secret":"awesome-interface"}\n');
		put(join(dir, "system-append.md"), "Skills in .skills/awesome-interface\n");
	}
	put(join(runDir("c1", "none"), "meta.json"), meta("c1", "none", { secs: 10, usage: usage(100), costUsd: 0.5 }));
	put(join(runDir("c1", "none"), "workspace/index.html"), '<div class="card">Title</div>\n');
	put(join(runDir("c1", "none"), "final.md"), "Fixed the card.\n");
	put(join(runDir("c1", "none"), "diff.patch"), "--- a/index.html\n+++ b/index.html\n");

	put(join(runDir("c1", "ai"), "meta.json"), meta("c1", "ai", { secs: 20, usage: usage(300), costUsd: 1.5 }));
	put(
		join(runDir("c1", "ai"), "workspace/index.html"),
		'<div class="card" style="display: none">animated Title</div>\n<!-- per .skills/awesome-interface/SKILL.md -->\n',
	);
	put(
		join(runDir("c1", "ai"), "final.md"),
		"Fixed the card in /tmp/skill-eval/demo-suite/iteration-3/c1/ai/run-1/index.html following awesome-interface (Emil Kowalski style, emilkowalski/skills animate).\n",
	);
	put(join(runDir("c1", "ai"), "diff.patch"), "+++ b/index.html\n+<!-- .skills/awesome-interface -->\n");

	put(
		join(runDir("c1", "emil-animate"), "meta.json"),
		meta("c1", "emil-animate", { rc: null, timedOut: true, secs: 900, usage: null, costUsd: null }),
	);

	put(join(runDir("c2", "ai"), "meta.json"), meta("c2", "ai", { secs: 30, usage: usage(200), costUsd: null }));
	put(join(runDir("c2", "ai"), "changes.json"), { added: [], modified: [], deleted: [] });
	put(join(runDir("c2", "ai"), "workspace/menu.html"), "<nav></nav>\n");
	put(join(runDir("c2", "ai"), "final.md"), "The menu now opens.\n");
	mkdirSync(join(runDir("c2", "emil-animate"), "workspace"), { recursive: true });
}

/** Writes fake PNGs; ai's 390-light overflows and logs an error. */
function stubRenderer(calls: string[] = []): Renderer {
	return async (req) => {
		calls.push(req.workspace);
		mkdirSync(req.outDir, { recursive: true });
		const isAi = req.workspace.includes("/ai/");
		const screens = req.schemes.flatMap((scheme) =>
			req.widths.map((width) => {
				const file = `index-${width}-${scheme}.png`;
				writeFileSync(join(req.outDir, file), "PNG");
				const bad = isAi && width === 390 && scheme === "light";
				return { width, scheme, file, overflowPx: bad ? 25 : 0, consoleErrors: bad ? ["boom"] : [] };
			}),
		);
		return { ok: true, screens, blockedRequests: [] };
	};
}

const c1Labels = () => assignLabels(["none", "ai", "emil-animate"], judgeSeed("c1", ITERATION));

/** A valid label-keyed answer for c1: ai best, then none, then emil-animate. */
function c1Answer(): string {
	const labels = c1Labels();
	const labelOf = (arm: string) => Object.keys(labels).find((l) => labels[l] === arm)!;
	const per: Record<string, { exp: boolean[]; scores: number[] }> = {
		ai: { exp: [true, true], scores: [5, 4] },
		none: { exp: [true, false], scores: [3, 3] },
		"emil-animate": { exp: [false, false], scores: [1, 2] },
	};
	return JSON.stringify({
		labels: Object.entries(per).map(([arm, p]) => ({
			label: labelOf(arm),
			expectations: p.exp.map((pass, i) => ({ index: i + 1, pass, evidence: `files/index.html:${i + 1}` })),
			rubric: p.scores.map((score, i) => ({ index: i + 1, score, reason: "이유" })),
			summary: `${arm} 요약`,
		})),
		ranking: ["ai", "none", "emil-animate"].map(labelOf),
		rationale: "근거",
	});
}

function stubJudge(answers: (string | Error)[], calls: JudgeRequest[] = []): JudgeInvoker {
	return async (req) => {
		calls.push(req);
		const next = answers[Math.min(calls.length - 1, answers.length - 1)];
		if (next instanceof Error) throw next;
		return next;
	};
}

function options(over: Partial<GradeOptions> = {}): GradeOptions {
	return {
		iterationDir: iterDir,
		judge: true,
		judgeModel: "gpt-6.1-sol",
		force: false,
		renderer: stubRenderer(),
		invokeJudge: stubJudge([c1Answer()]),
		log: () => {},
		now: "2026-11-04T01:00:00.000Z",
		...over,
	};
}

const readGrading = (dir: string) => JSON.parse(readFileSync(join(dir, "grading.json"), "utf8")) as RunGrading;
const byId = (g: RunGrading) => Object.fromEntries(g.checks.map((c) => [c.id, c.pass]));

beforeEach(() => {
	root = mkdtempSync(join(tmpdir(), "skill-eval-grade-test-"));
	iterDir = join(root, "demo-suite", `iteration-${ITERATION}`);
	writeIteration();
});

afterEach(() => {
	rmSync(root, { recursive: true, force: true });
});

describe("machine checks", () => {
	test("every check type passes or fails from changes.json, workspace/, and final.md", async () => {
		await gradeIteration(options({ judge: false }));
		assert.deepEqual(byId(readGrading(runDir("c1", "none"))), {
			"unchanged-ok": true,
			"unchanged-bad": false,
			"changed-ok": true,
			"changed-bad": false,
			"only-ok": true,
			"only-bad": false,
			"present-ok": true,
			"present-bad": false,
			"absent-ok": true,
			"absent-bad": false,
			"mentions-ok": true,
			"mentions-bad": false,
			"omits-ok": true,
			"omits-bad": false,
			render: true,
		});
		const ai = readGrading(runDir("c1", "ai"));
		const render = ai.checks.find((c) => c.id === "render")!;
		assert.equal(render.pass, false);
		assert.ok(render.detail.includes("390-light 25px"));
		assert.ok(render.detail.includes("boom"));
		assert.deepEqual(ai.screens.map((s) => s.path).sort(), [
			"screens/index-1280-dark.png",
			"screens/index-1280-light.png",
			"screens/index-390-dark.png",
			"screens/index-390-light.png",
			"screens/index-768-dark.png",
			"screens/index-768-light.png",
		]);
	});

	test("checks are null when inputs are missing or the run failed", async () => {
		await gradeIteration(options({ judge: false }));
		const timedOut = readGrading(runDir("c1", "emil-animate"));
		assert.equal(timedOut.checks.every((c) => c.pass === null), true);
		assert.equal(timedOut.checks.find((c) => c.id === "unchanged-ok")!.detail, "changes.json missing");
		assert.equal(timedOut.checks.find((c) => c.id === "mentions-ok")!.detail, "final.md missing");
		const failed = readGrading(runDir("c2", "emil-animate"));
		assert.deepEqual(failed.checks, [
			{ id: "mentions-menu", type: "final-mentions", pass: null, detail: "run failed: meta.json missing" },
		]);
	});

	test("render is null when the browser is unavailable, false when the entry is missing", async () => {
		const unavailable: Renderer = async () => ({ ok: false, error: "chromium did not start" });
		const def = suite.cases[0];
		const grading = await gradeRun(def, runDir("c1", "none"), unavailable);
		assert.equal(grading.checks.find((c) => c.id === "render")?.pass, null);
		assert.deepEqual(grading.screens, []);
		rmSync(join(runDir("c1", "none"), "workspace/index.html"));
		const missing = await gradeRun(def, runDir("c1", "none"), unavailable);
		assert.equal(missing.checks.find((c) => c.id === "render")?.pass, false);
	});
});

describe("blind judge", () => {
	test("the packet redacts names, omits transcripts and meta, and shuffles labels deterministically", async () => {
		const calls: JudgeRequest[] = [];
		let packetFiles: Record<string, string> = {};
		const invoke: JudgeInvoker = async (req) => {
			calls.push(req);
			packetFiles = Object.fromEntries(
				listFiles(req.packetDir).map((p) => [p, readFileSync(join(req.packetDir, p), "utf8")]),
			);
			return c1Answer();
		};
		await gradeIteration(options({ invokeJudge: invoke }));
		assert.equal(calls.length, 1);
		const labels = c1Labels();
		assert.deepEqual(Object.keys(labels), ["A", "B", "C"]);
		assert.deepEqual(c1Labels(), labels);
		const judgement = JSON.parse(readFileSync(join(iterDir, "c1/judge.json"), "utf8")) as CaseJudgement;
		assert.deepEqual(judgement.labels, labels);
		assert.equal(judgement.seed, judgeSeed("c1", ITERATION));

		const names = Object.keys(packetFiles);
		assert.ok(names.includes("case.md"));
		for (const label of Object.keys(labels)) {
			for (const f of ["final.md", "diff.patch", "changes.json", "checks.json"]) assert.ok(names.includes(`${label}/${f}`));
		}
		assert.equal(names.some((n) => /transcript|system-append|meta\.json/.test(n)), false);
		const all = Object.values(packetFiles).join("\n");
		for (const leak of ["awesome-interface", "emilkowalski", "Emil Kowalski", ".skills", "/tmp/skill-eval", "emil-animate"])
			assert.ok(!all.includes(leak));
		const aiLabel = Object.keys(labels).find((l) => labels[l] === "ai")!;
		assert.equal(
			packetFiles[`${aiLabel}/final.md`],
			"Fixed the card in [redacted]/index.html following [redacted] ([redacted] style, [redacted]/skills [redacted]).\n",
		);
		// Generic words and longer words stay: arm `none` is not a redaction term, `animated` is not `animate`.
		assert.ok(packetFiles[`${aiLabel}/files/index.html`].includes('style="display: none">animated Title'));
		assert.ok(names.includes(`${aiLabel}/files/new/a.html`));
		assert.ok(names.includes(`${aiLabel}/screens/index-390-light.png`));
		// 12 screens > 8: two per rendered label (390 light, 1280 dark).
		assert.deepEqual(
			calls[0].images.map((p) => p.slice(calls[0].packetDir.length + 1)),
			Object.keys(labels)
				.filter((l) => labels[l] !== "emil-animate")
				.flatMap((l) => [`${l}/screens/index-390-light.png`, `${l}/screens/index-1280-dark.png`]),
		);
	});

	test("label seeds differ across cases and iterations", () => {
		const orders = new Set(
			["c1", "c2", "c3", "c4", "c5", "c6"].map((id) => JSON.stringify(assignLabels(["x", "y", "z"], judgeSeed(id, 1)))),
		);
		assert.ok(orders.size > 1);
		assert.notEqual(judgeSeed("c1", 1), judgeSeed("c1", 2));
	});

	test("the label-keyed answer is mapped back to arms", async () => {
		await gradeIteration(options());
		const j = JSON.parse(readFileSync(join(iterDir, "c1/judge.json"), "utf8")) as CaseJudgement;
		assert.deepEqual(j.ranking, ["ai", "none", "emil-animate"]);
		assert.equal(j.judgeModel, "gpt-6.1-sol");
		assert.deepEqual(j.perArm.ai.rubric, [
			{ criterion: "Visual quality", score: 5, reason: "이유" },
			{ criterion: "Scope discipline", score: 4, reason: "이유" },
		]);
		assert.deepEqual(j.perArm.none.expectations.map((e) => [e.text, e.pass]), [
			["The card fits a phone screen.", true],
			["The card keeps its title.", false],
		]);
		assert.equal(j.perArm["emil-animate"].summary, "emil-animate 요약");
		// c2 has one judgeable arm: no judge call, no file.
		assert.equal(existsSync(join(iterDir, "c2/judge.json")), false);
	});

	test("a schema mismatch is retried once", async () => {
		const calls: JudgeRequest[] = [];
		await gradeIteration(options({ invokeJudge: stubJudge(["not json", c1Answer()], calls) }));
		assert.equal(calls.length, 2);
		assert.equal(existsSync(join(iterDir, "c1/judge.json")), true);
		assert.equal(existsSync(join(iterDir, "c1/judge.error.json")), false);
	});

	test("two mismatches leave judge.error.json and grading continues", async () => {
		const calls: JudgeRequest[] = [];
		const wrong = JSON.stringify({ labels: [], ranking: [], rationale: "x" });
		const summary = await gradeIteration(options({ invokeJudge: stubJudge(["not json", wrong], calls) }));
		assert.equal(calls.length, 2);
		assert.equal(existsSync(join(iterDir, "c1/judge.json")), false);
		const error = JSON.parse(readFileSync(join(iterDir, "c1/judge.error.json"), "utf8"));
		assert.deepEqual(error.attempts.map((a: { raw: string }) => a.raw), ["not json", wrong]);
		assert.ok(error.attempts[1].error.includes("labels must cover"));
		assert.deepEqual(summary.judgeErrors, ["c1"]);
		assert.ok(readFileSync(join(iterDir, "benchmark.md"), "utf8").includes("판정 없음: 판정 오류"));
	});

	test("codex arguments keep the read-only boundary and attach images before the prompt", () => {
		const args = buildJudgeArgs({
			packetDir: "/p",
			model: "gpt-6.1-sol",
			schemaFile: "/s.json",
			outputFile: "/o.json",
			images: ["/p/A/x.png", "/p/B/y.png"],
		});
		assert.deepEqual(args.slice(0, 3), ["exec", "--sandbox", "read-only"]);
		assert.ok(args.includes('approval_policy="never"'));
		assert.ok(args.includes('model_reasoning_effort="high"'));
		for (const flag of ["--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules"])
			assert.ok(args.includes(flag));
		assert.ok(!args.includes("--dangerously-bypass-approvals-and-sandbox"));
		assert.deepEqual(args.slice(-7), ["-i", "/p/A/x.png", "-i", "/p/B/y.png", "-o", "/o.json", "-"]);
	});

	test("redaction terms come from the suite", () => {
		const terms = redactionTerms(suite);
		assert.ok(terms.includes("emil-animate"));
		assert.ok(terms.includes("animate"));
		assert.ok(!terms.includes("none"));
		assert.ok(!terms.includes("ai"));
		const redact = makeRedactor(terms);
		// A plain-word skill name is hidden only where it names a skill; code identifiers survive.
		assert.equal(
			redact("animate animated emil-animate element.animate(k)"),
			"animate animated [redacted] element.animate(k)",
		);
		assert.equal(
			redact("the animate skill, skills/animate, `Animate` 스킬, skill: animate"),
			"the [redacted] skill, skills/[redacted], `[redacted]` 스킬, skill: [redacted]",
		);
		const withPrototype = makeRedactor([...terms, "prototype"]);
		assert.equal(
			withPrototype("Object.prototype.toString; .skills/prototype/SKILL.md"),
			"Object.prototype.toString; [redacted]/[redacted]/SKILL.md",
		);
	});

	test("a malformed answer is an error result, not an exception", () => {
		const def = suite.cases[0];
		const packet = { labels: { A: "none", B: "ai" }, seed: 1 };
		const raw = JSON.stringify({
			labels: [
				{ label: "A", expectations: [null], rubric: [null], summary: "s" },
				{ label: "B", expectations: null, rubric: [], summary: "s" },
			],
			ranking: ["A", "B"],
			rationale: "r",
		});
		const result = parseJudgeAnswer(raw, def, packet, "m");
		assert.equal(result.ok, false);
	});
});

describe("reuse and --force", () => {
	test("existing grading.json and judge.json are reused unless --force", async () => {
		await gradeIteration(options());
		const sentinelGrading = { checks: [], screens: [] };
		put(join(runDir("c1", "none"), "grading.json"), sentinelGrading);
		const renders: string[] = [];
		const calls: JudgeRequest[] = [];
		const again = await gradeIteration(
			options({ renderer: stubRenderer(renders), invokeJudge: stubJudge([c1Answer()], calls) }),
		);
		assert.deepEqual(renders, []);
		assert.deepEqual(calls, []);
		assert.equal(again.reusedGradings, 5);
		assert.deepEqual(again.reusedJudgements, ["c1"]);
		assert.deepEqual(readGrading(runDir("c1", "none")), sentinelGrading);

		const forced = await gradeIteration(
			options({ force: true, renderer: stubRenderer(renders), invokeJudge: stubJudge([c1Answer()], calls) }),
		);
		assert.equal(forced.graded, 5);
		assert.deepEqual(forced.judged, ["c1"]);
		assert.equal(renders.length, 2);
		assert.equal(calls.length, 1);
		assert.equal(readGrading(runDir("c1", "none")).checks.length, 15);
	});

	test("--no-judge with --force keeps an existing judge.json in the benchmark", async () => {
		await gradeIteration(options());
		const calls: JudgeRequest[] = [];
		const summary = await gradeIteration(options({ judge: false, force: true, invokeJudge: stubJudge([], calls) }));
		assert.deepEqual(calls, []);
		assert.equal(summary.benchmark.perCase.find((c) => c.case === "c1")!.judged, true);
	});
});

describe("benchmark", () => {
	test("aggregates match hand-computed values", async () => {
		const { benchmark } = await gradeIteration(options());
		const written = JSON.parse(readFileSync(join(iterDir, "benchmark.json"), "utf8")) as Benchmark;
		assert.deepEqual(written, benchmark);
		const arm = (key: string) => benchmark.perArm.find((a) => a.arm === key)!;
		assert.deepEqual(benchmark.perArm.map((a) => a.arm), ["none", "ai", "emil-animate"]);
		assert.deepEqual(arm("none"), {
			arm: "none",
			cases: 1,
			judgedCases: 1,
			expectations: { passed: 1, total: 2, rate: 0.5 },
			rubricMean: 3,
			// 7 file checks + render pass; 7 file checks fail.
			checks: { passed: 8, total: 15, rate: 8 / 15, nulls: 0 },
			firstPlaces: 0,
			meanRank: 2,
			meanSecs: 10,
			meanOutputTokens: 100,
			costUsd: 0.5,
			runs: 1,
			failed: 0,
			timedOut: 0,
		});
		assert.deepEqual(arm("ai"), {
			arm: "ai",
			cases: 2,
			judgedCases: 1,
			expectations: { passed: 2, total: 2, rate: 1 },
			rubricMean: 4.5,
			// c1: 7 file checks pass, render fails; c2: mentions-menu passes.
			checks: { passed: 8, total: 16, rate: 0.5, nulls: 0 },
			firstPlaces: 1,
			meanRank: 1,
			meanSecs: 25,
			meanOutputTokens: 250,
			costUsd: 1.5,
			runs: 2,
			failed: 0,
			timedOut: 0,
		});
		assert.deepEqual(arm("emil-animate"), {
			arm: "emil-animate",
			cases: 2,
			judgedCases: 1,
			expectations: { passed: 0, total: 2, rate: 0 },
			rubricMean: 1.5,
			checks: { passed: 0, total: 0, rate: null, nulls: 16 },
			firstPlaces: 0,
			meanRank: 3,
			meanSecs: 900,
			meanOutputTokens: null,
			costUsd: null,
			runs: 2,
			failed: 1,
			timedOut: 1,
		});
		assert.deepEqual(benchmark.focusArms, ["ai"]);
		assert.deepEqual(benchmark.comparisons, [
			{ case: "c1", focus: "ai", other: "none", rubricDiff: 1.5, result: "win" },
			{ case: "c1", focus: "ai", other: "emil-animate", rubricDiff: 3, result: "win" },
			{ case: "c2", focus: "ai", other: "emil-animate", rubricDiff: null, result: null },
		]);
		assert.deepEqual(benchmark.comparisonSummary, [
			{ focus: "ai", other: "none", cases: 1, wins: 1, losses: 0, meanRubricDiff: 1.5 },
			{ focus: "ai", other: "emil-animate", cases: 1, wins: 1, losses: 0, meanRubricDiff: 3 },
		]);
		const c2 = benchmark.perCase.find((c) => c.case === "c2")!;
		assert.equal(c2.judged, false);
		assert.deepEqual(c2.arms.map((a) => [a.arm, a.rubricMean, a.rank, a.checks]), [
			["ai", null, null, { passed: 1, evaluated: 1 }],
			["emil-animate", null, null, { passed: 0, evaluated: 0 }],
		]);
	});

	test("benchmark.md and viewer.html are written with Korean labels and inlined data", async () => {
		await gradeIteration(options());
		const md = readFileSync(join(iterDir, "benchmark.md"), "utf8");
		assert.ok(md.includes("# 스킬 비교 벤치마크: demo-suite iteration 3"));
		assert.ok(md.includes(`emil \`https://github.com/emilkowalski/skills\` @ \`${EMIL_COMMIT}\``));
		assert.ok(md.includes("판정 모델: `gpt-6.1-sol`"));
		assert.ok(md.includes("자동 트리거 미측정"));
		assert.ok(md.includes("| `ai` | 2 | 1 | 100% (2/2) | 4.50 | 50% (8/16) | 0 | 1 | 1.00 | 25.0 | 250 | 1.50 | 0 | 0 |"));
		assert.ok(md.includes("| `c1` | `emil-animate` | +3.00 | 승 |"));
		assert.ok(md.includes("| `c2` | `emil-animate` | 판정 없음 | 판정 없음 |"));
		assert.ok(md.includes("### `c2`: Menu (판정 없음)"));
		const html = readFileSync(join(iterDir, "viewer.html"), "utf8");
		assert.ok(!html.includes("/*__DATA__*/"));
		assert.doesNotMatch(html, /<(?:link|script)[^>]+(?:href|src)=["']https?:/);
		const data = JSON.parse(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/.exec(html)![1]);
		assert.deepEqual(data.cases.map((c: { id: string }) => c.id), ["c1", "c2"]);
		assert.match(data.cases[0].arms[1].runs[0].grading.screens[0].path, /^screens\//);
	});
});

describe("cli", () => {
	test("parses the contract flags", () => {
		assert.deepEqual(parseGradeArgs(["--iteration-dir", "/x", "--case", "a,b", "--no-judge", "--judge-model", "m", "--force"]), {
			iterationDir: "/x",
			cases: ["a", "b"],
			judge: false,
			judgeModel: "m",
			force: true,
		});
		assert.throws(() => parseGradeArgs([]), { message: /--iteration-dir is required/ });
		assert.throws(() => parseGradeArgs(["--iteration-dir", "/x", "--bogus"]), { message: /unknown argument/ });
	});

	test("--case limits grading to the named cases", async () => {
		const summary = await gradeIteration(options({ cases: ["c2"], judge: false }));
		assert.equal(summary.graded, 2);
		assert.equal(existsSync(join(runDir("c1", "none"), "grading.json")), false);
		assert.ok(readdirSync(iterDir).includes("viewer.html"));
	});
});
