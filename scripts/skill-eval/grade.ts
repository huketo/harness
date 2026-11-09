#!/usr/bin/env node
/**
 * skill-eval grader. Reads an iteration directory written by run.ts and adds
 * per-run machine checks and screens (`grading.json`, `screens/`), one blind
 * comparison judgement per case (`judge.json`), and the iteration-wide
 * `benchmark.json`, `benchmark.md`, and `viewer.html`. Layout and types:
 * `lib/schema.ts`.
 *
 *   node scripts/skill-eval/grade.ts --iteration-dir <dir> [--case <id,...>]
 *       [--no-judge] [--judge-model <m>] [--force]
 */

import { existsSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { aggregate, renderMarkdown, type Benchmark, type CaseData } from "./lib/grade/benchmark.ts";
import { gradeRun } from "./lib/grade/checks.ts";
import { codexJudge, DEFAULT_JUDGE_MODEL, judgeCase, type JudgeInvoker } from "./lib/grade/judge.ts";
import { loadIteration, readJson, readText, runMeta, writeJson } from "./lib/grade/layout.ts";
import { playwrightRenderer, type Renderer } from "./lib/grade/render.ts";
import { renderViewer, viewerCase, type ViewerCase } from "./lib/grade/viewer.ts";
import type { CaseJudgement, RunGrading } from "./lib/schema.ts";

export interface GradeOptions {
	iterationDir: string;
	cases?: string[];
	judge: boolean;
	judgeModel: string;
	force: boolean;
	renderer?: Renderer;
	invokeJudge?: JudgeInvoker;
	log?: (line: string) => void;
	/** Fixed timestamp for reproducible output in tests. */
	now?: string;
}

export interface GradeSummary {
	graded: number;
	reusedGradings: number;
	judged: string[];
	reusedJudgements: string[];
	judgeErrors: string[];
	benchmark: Benchmark;
}

function usage(): string {
	return [
		"Usage: node scripts/skill-eval/grade.ts --iteration-dir <dir> [--case <id,...>] [--no-judge] [--judge-model <m>] [--force]",
		"",
		"  --iteration-dir DIR  var/skill-eval/<suite>/iteration-<n>; the suite is read from DIR/suite.json",
		"  --case IDS           grade only these comma-separated case ids",
		"  --no-judge           skip the blind judge (existing judge.json files still count)",
		`  --judge-model M      Codex judge model (default: ${DEFAULT_JUDGE_MODEL})`,
		"  --force              rebuild grading.json and judge.json even when present",
	].join("\n");
}

export function parseGradeArgs(argv: string[]): GradeOptions | { help: true } {
	const options: GradeOptions = { iterationDir: "", judge: true, judgeModel: DEFAULT_JUDGE_MODEL, force: false };
	const value = (i: number) => {
		const v = argv[i + 1];
		if (v === undefined || v.startsWith("--")) throw new Error(`${argv[i]} requires a value`);
		return v;
	};
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		if (arg === "--help" || arg === "-h") return { help: true };
		else if (arg === "--iteration-dir") options.iterationDir = resolve(value(i++));
		else if (arg === "--case") options.cases = value(i++).split(",").map((s) => s.trim()).filter(Boolean);
		else if (arg === "--no-judge") options.judge = false;
		else if (arg === "--judge-model") options.judgeModel = value(i++);
		else if (arg === "--force") options.force = true;
		else throw new Error(`unknown argument: ${arg}`);
	}
	if (!options.iterationDir) throw new Error("--iteration-dir is required");
	return options;
}

export async function gradeIteration(options: GradeOptions): Promise<GradeSummary> {
	const log = options.log ?? ((line: string) => console.error(line));
	const renderer = options.renderer ?? playwrightRenderer;
	const invoke = options.invokeJudge ?? codexJudge;
	const iteration = loadIteration(options.iterationDir, options.cases);
	const summary: Omit<GradeSummary, "benchmark"> = {
		graded: 0,
		reusedGradings: 0,
		judged: [],
		reusedJudgements: [],
		judgeErrors: [],
	};
	const caseData: CaseData[] = [];
	const viewerCases: ViewerCase[] = [];

	for (const caseRef of iteration.cases) {
		const gradings = new Map<string, RunGrading>();
		for (const arm of caseRef.arms) {
			for (const run of arm.runs) {
				const file = join(run.dir, "grading.json");
				const existing = options.force ? null : readJson<RunGrading>(file);
				if (existing) {
					summary.reusedGradings++;
					gradings.set(`${arm.key}/${run.k}`, existing);
					continue;
				}
				if (options.force) rmSync(join(run.dir, "screens"), { recursive: true, force: true });
				const grading = await gradeRun(caseRef.def, run.dir, renderer);
				writeJson(file, grading);
				summary.graded++;
				gradings.set(`${arm.key}/${run.k}`, grading);
				const passed = grading.checks.filter((c) => c.pass === true).length;
				log(`graded ${caseRef.def.id}/${arm.key}/run-${run.k}: ${passed}/${grading.checks.length} checks passed`);
			}
		}

		const judgeFile = join(caseRef.dir, "judge.json");
		let judgement = options.force ? null : readJson<CaseJudgement>(judgeFile);
		if (judgement) summary.reusedJudgements.push(caseRef.def.id);
		else if (options.judge) {
			log(`judging ${caseRef.def.id} with ${options.judgeModel}`);
			const outcome = await judgeCase({
				caseRef,
				suite: iteration.suite,
				iteration: iteration.meta.iteration,
				gradings,
				model: options.judgeModel,
				invoke,
			});
			if (outcome.status === "judged") {
				judgement = outcome.judgement;
				summary.judged.push(caseRef.def.id);
				log(`judged ${caseRef.def.id}: ${judgement.ranking.join(" > ")}`);
			} else if (outcome.status === "error") {
				summary.judgeErrors.push(caseRef.def.id);
				log(`judge failed for ${caseRef.def.id}: ${outcome.error}`);
			} else log(`judge skipped for ${caseRef.def.id}: ${outcome.reason}`);
		} else if (options.force) {
			judgement = readJson<CaseJudgement>(judgeFile);
		}
		const judgeError = !judgement && existsSync(join(caseRef.dir, "judge.error.json"));

		const arms = caseRef.arms.map((arm) => ({
			key: arm.key,
			runs: arm.runs.map((run) => ({
				k: run.k,
				meta: runMeta(run.dir),
				grading: gradings.get(`${arm.key}/${run.k}`)!,
				final: readText(join(run.dir, "final.md")),
				diff: readText(join(run.dir, "diff.patch")),
			})),
		}));
		caseData.push({
			def: caseRef.def,
			arms: arms.map((a) => ({ key: a.key, runs: a.runs.map(({ k, meta, grading }) => ({ k, meta, grading })) })),
			judgement,
			judgeError,
		});
		viewerCases.push(viewerCase(caseRef.def, { judgement, judgeError, arms }));
	}

	const benchmark = aggregate(iteration.suite, iteration.meta, caseData, {
		judgeModel: options.judgeModel,
		generatedAt: options.now,
	});
	writeJson(join(iteration.dir, "benchmark.json"), benchmark);
	writeFileSync(join(iteration.dir, "benchmark.md"), renderMarkdown(benchmark, options.judgeModel));
	writeFileSync(join(iteration.dir, "viewer.html"), renderViewer(benchmark, viewerCases));
	log(`wrote benchmark.json, benchmark.md, viewer.html in ${iteration.dir}`);
	return { ...summary, benchmark };
}

if (import.meta.main) {
	try {
		const parsed = parseGradeArgs(process.argv.slice(2));
		if ("help" in parsed) console.log(usage());
		else await gradeIteration(parsed);
	} catch (error) {
		console.error((error as Error).message);
		process.exitCode = 1;
	}
}
