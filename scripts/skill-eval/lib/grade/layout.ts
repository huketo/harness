/**
 * Reads an iteration directory laid out as described in `../schema.ts`.
 * Readers plus the one JSON writer the grader shares across artifacts.
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import type { Case, IterationMeta, RunMeta, Suite } from "../schema.ts";
import { loadSuite, validateSuite } from "../schema.ts";

export interface RunRef {
	k: number;
	dir: string;
}

export interface ArmRef {
	key: string;
	runs: RunRef[];
}

export interface CaseRef {
	def: Case;
	dir: string;
	arms: ArmRef[];
}

export interface Iteration {
	dir: string;
	meta: IterationMeta;
	suite: Suite;
	cases: CaseRef[];
}

export function readJson<T>(file: string): T | null {
	if (!existsSync(file)) return null;
	return JSON.parse(readFileSync(file, "utf8")) as T;
}

export function readText(file: string): string | null {
	return existsSync(file) ? readFileSync(file, "utf8") : null;
}

export function writeJson(file: string, value: unknown): void {
	mkdirSync(dirname(file), { recursive: true });
	writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
}

function isDir(path: string): boolean {
	return existsSync(path) && statSync(path).isDirectory();
}

/** `run-<k>` directories of one arm, ascending by k. */
export function listRuns(armDir: string): RunRef[] {
	if (!isDir(armDir)) return [];
	return readdirSync(armDir)
		.map((name) => /^run-([1-9][0-9]*)$/.exec(name))
		.filter((m): m is RegExpExecArray => m !== null)
		.map((m) => ({ k: Number(m[1]), dir: join(armDir, m[0]) }))
		.filter((run) => isDir(run.dir))
		.sort((a, b) => a.k - b.k);
}

/**
 * Loads `iteration.json` and the `suite.json` snapshot, then lists the cases,
 * arms, and runs present on disk. Only arms named in the case and present on
 * disk are listed; `onlyCases` filters by case id.
 */
export function loadIteration(dir: string, onlyCases?: string[]): Iteration {
	const metaFile = join(dir, "iteration.json");
	const suiteFile = join(dir, "suite.json");
	const meta = readJson<IterationMeta>(metaFile);
	if (!meta) throw new Error(`missing ${metaFile}`);
	if (!existsSync(suiteFile)) throw new Error(`missing ${suiteFile}`);
	const suite = loadSuite(suiteFile);
	// The snapshot has no fixtures beside it; the grader never reads fixtures.
	const errors = validateSuite(suite, suiteFile).filter((e) => !e.includes("fixture directory"));
	if (errors.length) throw new Error(`invalid ${suiteFile}:\n${errors.join("\n")}`);
	if (onlyCases) {
		const known = new Set(suite.cases.map((c) => c.id));
		const unknown = onlyCases.filter((id) => !known.has(id));
		if (unknown.length) throw new Error(`unknown case id: ${unknown.join(", ")}`);
	}
	const cases: CaseRef[] = [];
	for (const def of suite.cases) {
		if (onlyCases && !onlyCases.includes(def.id)) continue;
		const caseDir = join(dir, def.id);
		if (!isDir(caseDir)) continue;
		const arms = def.arms
			.map((key) => ({ key, runs: listRuns(join(caseDir, key)) }))
			.filter((arm) => arm.runs.length > 0);
		if (arms.length) cases.push({ def, dir: caseDir, arms });
	}
	return { dir, meta, suite, cases };
}

export function runMeta(runDir: string): RunMeta | null {
	return readJson<RunMeta>(join(runDir, "meta.json"));
}

/** Every regular file under `root`, as sorted POSIX paths relative to it. */
export function listFiles(root: string): string[] {
	if (!isDir(root)) return [];
	const out: string[] = [];
	for (const entry of readdirSync(root, { recursive: true, withFileTypes: true })) {
		if (!entry.isFile()) continue;
		const abs = join(entry.parentPath, entry.name);
		out.push(relative(root, abs).split(sep).join("/"));
	}
	return out.sort();
}

/** UTF-8 text without NUL bytes. */
export function decodeText(bytes: Uint8Array): string | null {
	if (bytes.includes(0)) return null;
	try {
		return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
	} catch {
		return null;
	}
}

/** `<entry-stem>`: the entry file name without its last extension. */
export function entryStem(entry: string): string {
	const name = entry.split("/").at(-1) ?? entry;
	const dot = name.lastIndexOf(".");
	return dot > 0 ? name.slice(0, dot) : name;
}
