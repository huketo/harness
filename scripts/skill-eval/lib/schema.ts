#!/usr/bin/env node
/**
 * skill-eval contract: the suite file, the run output layout, and the grading
 * output. The runner (run.ts), the grader (grade.ts), and suite authors all
 * depend on this file; change it only together with every consumer.
 *
 * Output layout, rooted at `var/skill-eval/<suite>/iteration-<n>/`:
 *
 *   iteration.json                      IterationMeta (runner)
 *   suite.json                          byte copy of the suite file this iteration ran (runner)
 *   <case>/<arm>/run-<k>/workspace/     final workspace, without `.skills/` (runner)
 *   <case>/<arm>/run-<k>/changes.json   Changes against the fixture (runner)
 *   <case>/<arm>/run-<k>/diff.patch     unified diff against the fixture, text files only (runner)
 *   <case>/<arm>/run-<k>/transcript.jsonl  agent stream-json output (runner)
 *   <case>/<arm>/run-<k>/final.md       final assistant message (runner)
 *   <case>/<arm>/run-<k>/meta.json      RunMeta (runner)
 *   <case>/<arm>/run-<k>/grading.json   RunGrading (grader)
 *   <case>/<arm>/run-<k>/screens/<entry-stem>-<width>-<scheme>.png (grader)
 *   <case>/judge.json                   CaseJudgement (grader)
 *   benchmark.json, benchmark.md, viewer.html (grader)
 *
 * Paths inside checks are POSIX paths relative to the workspace root, which
 * starts as a copy of `fixtures/<case.fixture>/`. `k` starts at 1. The grader
 * evaluates file checks from `changes.json` and `workspace/` alone; it never
 * needs the original fixture.
 */

import { existsSync, lstatSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

/** Arm keys and case ids: lowercase kebab, used verbatim as directory names. */
export const KEY_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const SHA_PATTERN = /^[0-9a-f]{40}$/;
/** `Case.fixture`: a single directory name under the suite's `fixtures/`. */
export const FIXTURE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

/** A pinned upstream repository. `commit` is a full 40-hex SHA. */
export interface GitSource {
	repo: string;
	commit: string;
}

/**
 * One skill directory given to an arm.
 * - `source: "local"`: `path` is relative to this repository's root and is
 *   read at git `ref` (default `"HEAD"`; the runner may override the ref per
 *   arm from the command line).
 * - any other `source`: a key of `Suite.sources`; `path` is inside that repo.
 * The skill's name is the last path segment.
 */
export type SkillRef =
	| { source: "local"; path: string; ref?: string }
	| { source: string; path: string };

export interface Arm {
	/** Empty for the no-skill baseline. */
	skills: SkillRef[];
	note?: string;
}

export type RenderAssertion = "no-horizontal-overflow" | "no-console-errors";

export type Check =
	/** Each file must be byte-identical to the fixture copy (a missing file fails). */
	| { id: string; type: "unchanged"; paths: string[] }
	/** Each file must differ from the fixture copy or be newly added. */
	| { id: string; type: "changed"; paths: string[] }
	/** Every added, modified, or deleted file must match one of the globs. */
	| { id: string; type: "only-changed"; allow: string[] }
	/** `pattern` (JS RegExp source) must match in at least one file matching the glob `files`. */
	| { id: string; type: "present"; files: string; pattern: string; flags?: string }
	/** `pattern` must match in no file matching the glob `files`. */
	| { id: string; type: "absent"; files: string; pattern: string; flags?: string }
	/** `pattern` must match the final assistant message (`final.md`). */
	| { id: string; type: "final-mentions"; pattern: string; flags?: string }
	/** `pattern` must not match `final.md`. */
	| { id: string; type: "final-omits"; pattern: string; flags?: string }
	/** Render `entry` (an HTML file in the workspace) at each width and color scheme. */
	| {
			id: string;
			type: "render";
			entry: string;
			widths: number[];
			schemes: ("light" | "dark")[];
			assert: RenderAssertion[];
	  };

export interface Case {
	/** Unique kebab id. */
	id: string;
	title: string;
	/** Upstream skill names (e.g. "break-ui") and/or "ai:<reference>" (e.g. "ai:stress-test"). */
	covers: string[];
	/** The user message, as a person would type it. Never contains the expected answer. */
	prompt: string;
	/** Directory under the suite's `fixtures/`, copied to the workspace root; `null` = empty workspace. */
	fixture: string | null;
	/** Keys of `Suite.arms`; at least two. */
	arms: string[];
	/** Pass/fail statements the judge decides per arm. */
	expectations: string[];
	/** Criteria the judge scores 1-5 per arm. */
	rubric: string[];
	checks: Check[];
	/** Agent wall-clock limit; the runner's default is 900. */
	timeoutSec?: number;
}

export interface Suite {
	suite: string;
	version: number;
	sources: Record<string, GitSource>;
	arms: Record<string, Arm>;
	cases: Case[];
}

export interface IterationMeta {
	suite: string;
	suiteVersion: number;
	iteration: number;
	createdAt: string;
	/** `git rev-parse HEAD` of this repository when the iteration started. */
	harnessCommit: string;
	model: string;
	effort: string | null;
	runs: number;
	cases: string[];
	arms: string[];
	sources: Record<string, GitSource>;
	/** Resolved commit SHA of every local skill ref, keyed by arm. */
	localRefs: Record<string, string>;
}

export interface MaterializedSkill {
	name: string;
	source: string;
	/** Full commit SHA the files were read from. */
	commit: string;
	path: string;
	/** SHA-256 over the copied files (sorted relative POSIX path + NUL + bytes + NUL). */
	sha256: string;
}

export interface RunMeta {
	case: string;
	arm: string;
	run: number;
	model: string;
	effort: string | null;
	rc: number | null;
	timedOut: boolean;
	secs: number;
	startedAt: string;
	usage: {
		inputTokens: number;
		outputTokens: number;
		cacheReadTokens: number;
		cacheCreationTokens: number;
	} | null;
	costUsd: number | null;
	numTurns: number | null;
	skills: MaterializedSkill[];
	suiteVersion: number;
	harnessCommit: string;
}

export interface Changes {
	added: string[];
	modified: string[];
	deleted: string[];
}

export interface CheckResult {
	id: string;
	type: Check["type"];
	/** `null` when the check could not be evaluated (e.g. the browser is unavailable). */
	pass: boolean | null;
	detail: string;
}

export interface ScreenResult {
	entry: string;
	width: number;
	scheme: "light" | "dark";
	/** Relative to the run directory. */
	path: string;
	overflowPx: number;
	consoleErrors: string[];
}

export interface RunGrading {
	checks: CheckResult[];
	screens: ScreenResult[];
}

export interface ArmJudgement {
	expectations: { text: string; pass: boolean; evidence: string }[];
	rubric: { criterion: string; score: 1 | 2 | 3 | 4 | 5; reason: string }[];
	summary: string;
}

export interface CaseJudgement {
	case: string;
	judgeModel: string;
	/** Seed of the label shuffle. */
	seed: number;
	/** Blind label (e.g. "A") → arm key. */
	labels: Record<string, string>;
	/** Arm keys, best first, after unblinding. */
	ranking: string[];
	perArm: Record<string, ArmJudgement>;
	rationale: string;
}

/** Returns human-readable errors; an empty array means the suite is valid. */
export function validateSuite(suite: Suite, suiteFile: string): string[] {
	const errors: string[] = [];
	const fixtureRoot = join(dirname(resolve(suiteFile)), "fixtures");
	if (!suite.suite || !KEY_PATTERN.test(suite.suite)) errors.push(`suite: name must match ${KEY_PATTERN}`);
	if (!Number.isInteger(suite.version) || suite.version < 1) errors.push("version: positive integer required");
	for (const [key, src] of Object.entries(suite.sources ?? {})) {
		if (key === "local") errors.push('sources: "local" is reserved');
		if (!src.repo) errors.push(`sources.${key}: repo required`);
		if (!SHA_PATTERN.test(src.commit ?? "")) errors.push(`sources.${key}: commit must be a full 40-hex SHA`);
	}
	for (const [key, arm] of Object.entries(suite.arms ?? {})) {
		if (!KEY_PATTERN.test(key)) errors.push(`arms.${key}: key must match ${KEY_PATTERN}`);
		if (!Array.isArray(arm.skills)) {
			errors.push(`arms.${key}: skills must be an array`);
			continue;
		}
		const names = new Set<string>();
		for (const skill of arm.skills) {
			if (skill.source !== "local" && !(skill.source in (suite.sources ?? {})))
				errors.push(`arms.${key}: unknown source "${skill.source}"`);
			const name = skill.path?.split("/").filter(Boolean).at(-1);
			if (!name) errors.push(`arms.${key}: empty skill path`);
			else if (names.has(name)) errors.push(`arms.${key}: duplicate skill name "${name}"`);
			else names.add(name);
		}
	}
	const ids = new Set<string>();
	for (const [i, c] of (suite.cases ?? []).entries()) {
		const at = `cases[${i}] ${c.id ?? "?"}`;
		if (!KEY_PATTERN.test(c.id ?? "")) errors.push(`${at}: id must match ${KEY_PATTERN}`);
		if (ids.has(c.id)) errors.push(`${at}: duplicate id`);
		ids.add(c.id);
		if (!c.title) errors.push(`${at}: title required`);
		if (!c.prompt?.trim()) errors.push(`${at}: prompt required`);
		if (!c.covers?.length) errors.push(`${at}: covers must be non-empty`);
		if (!c.arms || c.arms.length < 2) errors.push(`${at}: at least two arms required`);
		for (const a of c.arms ?? []) if (!(a in (suite.arms ?? {}))) errors.push(`${at}: unknown arm "${a}"`);
		if (new Set(c.arms).size !== c.arms?.length) errors.push(`${at}: duplicate arm`);
		if (!c.expectations?.length) errors.push(`${at}: expectations must be non-empty`);
		if (!c.rubric?.length) errors.push(`${at}: rubric must be non-empty`);
		if (c.fixture !== null) {
			const dir = join(fixtureRoot, c.fixture ?? "");
			// One plain directory name, so a case can never copy the suite file or
			// anything else outside fixtures/ into the evaluated workspace.
			if (!FIXTURE_PATTERN.test(c.fixture ?? "") || lstatSync(dir, { throwIfNoEntry: false })?.isSymbolicLink())
				errors.push(`${at}: fixture must be a directory name directly under fixtures/ (${FIXTURE_PATTERN}), not a symlink`);
			else if (!existsSync(dir) || !statSync(dir).isDirectory())
				errors.push(`${at}: fixture directory fixtures/${c.fixture} not found`);
		}
		const checkIds = new Set<string>();
		for (const check of c.checks ?? []) {
			if (checkIds.has(check.id)) errors.push(`${at}: duplicate check id "${check.id}"`);
			checkIds.add(check.id);
			if ("pattern" in check) {
				try {
					new RegExp(check.pattern, check.flags);
				} catch (e) {
					errors.push(`${at}: check ${check.id}: bad pattern (${(e as Error).message})`);
				}
			}
			if (check.type === "render" && (!check.widths.length || !check.schemes.length))
				errors.push(`${at}: check ${check.id}: widths and schemes required`);
		}
		if (c.timeoutSec !== undefined && !(c.timeoutSec > 0)) errors.push(`${at}: timeoutSec must be positive`);
	}
	if (!suite.cases?.length) errors.push("cases: at least one case required");
	return errors;
}

export function loadSuite(suiteFile: string): Suite {
	return JSON.parse(readFileSync(suiteFile, "utf8")) as Suite;
}

if (import.meta.main) {
	const file = process.argv[2];
	if (!file) {
		console.error("usage: node scripts/skill-eval/lib/schema.ts <suite.json>");
		process.exit(2);
	}
	const errors = validateSuite(loadSuite(file), file);
	if (errors.length) {
		for (const e of errors) console.error(e);
		process.exit(1);
	}
	console.log("suite OK");
}
