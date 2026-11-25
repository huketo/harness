/**
 * A skill's own cases, `skills/<name>/evals/evals.json`: the file format, its
 * validation, and the conversion into a runnable Suite. `scripts/check-repo.ts`
 * validates every tracked file with this; `from-evals.ts` writes the suite.
 */

import { cpSync, lstatSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { basename, dirname, isAbsolute, join, normalize, relative } from "node:path";
import { KEY_PATTERN, type Arm, type Case, type Suite } from "./schema.ts";

export interface EvalCase {
	id: number | string;
	/** Short kebab name; becomes the case directory name. */
	name: string;
	/** The user message, as a person would type it. */
	prompt: string;
	/** One sentence describing a good result; the judge scores against it. */
	expected_output: string;
	/** Plain files, relative to the `evals/` directory, copied into the workspace. */
	files: string[];
	/** Directory under `evals/` that becomes the workspace root; every file must be inside it. Absent: `evals/` itself, so paths arrive as listed. */
	root?: string;
	/** Pass/fail statements the judge decides. */
	expectations: string[];
	/** Agent wall-clock limit in seconds; the runner's default applies when absent. */
	timeout_sec?: number;
}

export interface EvalsFile {
	skill_name: string;
	evals: EvalCase[];
}

/** Arm keys of a suite generated from evals.json. */
export const BASELINE_ARM = "none";
export const SKILL_ARM = "skill";
export const PREVIOUS_ARM = "previous";

/** The longest limit a case may ask for: one hour. */
export const MAX_TIMEOUT_SEC = 3600;

const text = (value: unknown): value is string => typeof value === "string" && value.trim() !== "";
const escapes = (path: string) => isAbsolute(path) || normalize(path).split("/").includes("..");

/** What the slash-separated `path` under `base` is. "link": it, `base`, or a directory on the way is a symbolic link. "missing" also covers a file written with a trailing slash. */
function kind(base: string, path: string): "file" | "directory" | "link" | "missing" {
	let current = base;
	for (const part of ["", ...path.split("/")]) {
		current = join(current, part);
		const stat = lstatSync(current, { throwIfNoEntry: false });
		if (!stat) return "missing";
		if (stat.isSymbolicLink()) return "link";
		if (!stat.isDirectory()) return current === join(base, path) && stat.isFile() ? "file" : "missing";
	}
	return "directory";
}

/** Human-readable errors; an empty array means the file is valid. `skillDir` is the skill's directory on disk. */
export function validateEvals(data: unknown, skillDir: string): string[] {
	const errors: string[] = [];
	const file = data as Partial<EvalsFile> | null;
	if (!file || typeof file !== "object" || Array.isArray(file)) return ["the file must hold one JSON object"];
	if (file.skill_name !== basename(skillDir)) errors.push(`skill_name must equal the skill directory name "${basename(skillDir)}"`);
	if (!Array.isArray(file.evals) || file.evals.length === 0) return [...errors, "evals must be a non-empty array"];
	const ids = new Set<unknown>();
	const names = new Set<string>();
	for (const [index, entry] of file.evals.entries()) {
		const at = `evals[${index}]`;
		if (!entry || typeof entry !== "object") {
			errors.push(`${at}: must be an object`);
			continue;
		}
		if (typeof entry.id !== "number" && !text(entry.id)) errors.push(`${at}: id must be a number or a string`);
		else if (ids.has(entry.id)) errors.push(`${at}: id ${entry.id} is used twice`);
		ids.add(entry.id);
		if (!text(entry.name) || !KEY_PATTERN.test(entry.name)) errors.push(`${at}: name must be lowercase kebab (${KEY_PATTERN}); it names the case directory`);
		else if (names.has(entry.name)) errors.push(`${at}: name "${entry.name}" is used twice`);
		else names.add(entry.name);
		if (!text(entry.prompt)) errors.push(`${at}: prompt must be the request a person would type`);
		else if (entry.prompt.startsWith("-")) errors.push(`${at}: prompt starts with "-" and would be read as a flag`);
		if (!text(entry.expected_output)) errors.push(`${at}: expected_output must describe a good result in one sentence`);
		if (!Array.isArray(entry.expectations) || entry.expectations.length === 0 || !entry.expectations.every(text))
			errors.push(`${at}: expectations must be a non-empty array of pass/fail statements`);
		if (entry.timeout_sec !== undefined && !(Number.isInteger(entry.timeout_sec) && entry.timeout_sec > 0 && entry.timeout_sec <= MAX_TIMEOUT_SEC))
			errors.push(`${at}: timeout_sec must be a whole number of seconds from 1 to ${MAX_TIMEOUT_SEC}`);
		if (!Array.isArray(entry.files) || !entry.files.every(text)) {
			errors.push(`${at}: files must be an array of paths relative to evals/ (use [] for none)`);
			continue;
		}
		const root = entry.root === undefined ? "" : entry.root;
		if (typeof root !== "string" || escapes(root) || kind(skillDir, join("evals", root)) !== "directory") {
			errors.push(`${at}: root must be an existing directory inside evals/, reached through no symbolic link`);
			continue;
		}
		for (const path of entry.files) {
			if (escapes(path)) errors.push(`${at}: file "${path}" must stay inside evals/`);
			else if (escapes(relative(normalize(root), normalize(path)))) errors.push(`${at}: file "${path}" must be inside root "${root}"`);
			else if (kind(skillDir, join("evals", path)) !== "file") errors.push(`${at}: file "${path}" must be an existing plain file under evals/, reached through no symbolic link`);
		}
	}
	return errors;
}

export interface SuiteOptions {
	/** Skill path relative to the repository root, e.g. `skills/tdd`. */
	skillPath: string;
	/** Git ref of the version to compare against; adds the `previous` arm. */
	previousRef?: string;
}

/** The Suite that runs every case without the skill, with it, and optionally with an earlier version. */
export function suiteFromEvals(file: EvalsFile, options: SuiteOptions): Suite {
	const arms: Record<string, Arm> = {
		[BASELINE_ARM]: { skills: [], note: "no skill" },
		[SKILL_ARM]: { skills: [{ source: "local", path: options.skillPath }], note: "the skill at the commit being measured" },
	};
	if (options.previousRef)
		arms[PREVIOUS_ARM] = { skills: [{ source: "local", path: options.skillPath, ref: options.previousRef }], note: `the skill at ${options.previousRef}` };
	const cases: Case[] = file.evals.map((entry) => ({
		id: entry.name,
		title: entry.name,
		covers: [file.skill_name],
		prompt: entry.prompt,
		fixture: entry.files.length ? entry.name : null,
		arms: Object.keys(arms),
		expectations: entry.expectations,
		rubric: [entry.expected_output],
		checks: [],
		...(entry.timeout_sec === undefined ? {} : { timeoutSec: entry.timeout_sec }),
	}));
	return { suite: `${file.skill_name}-cases`, version: 1, sources: {}, arms, cases };
}

/** Writes `suite.json` and each case's fixture directory under `outDir`, replacing what was there. Returns the suite path. */
export function writeSuite(file: EvalsFile, skillDir: string, outDir: string, options: SuiteOptions): string {
	rmSync(outDir, { recursive: true, force: true });
	mkdirSync(outDir, { recursive: true });
	for (const entry of file.evals) {
		for (const path of entry.files) {
			const target = join(outDir, "fixtures", entry.name, relative(normalize(entry.root ?? ""), normalize(path)));
			mkdirSync(dirname(target), { recursive: true });
			cpSync(join(skillDir, "evals", path), target);
		}
	}
	const suiteFile = join(outDir, "suite.json");
	writeFileSync(suiteFile, `${JSON.stringify(suiteFromEvals(file, options), null, 2)}\n`);
	return suiteFile;
}
