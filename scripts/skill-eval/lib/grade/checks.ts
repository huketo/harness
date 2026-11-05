/**
 * Machine checks for one run. File checks read `changes.json` and
 * `workspace/` only; `render` delegates to an injectable Renderer.
 */

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import type { Case, Changes, Check, CheckResult, RunGrading, ScreenResult } from "../schema";
import { decodeText, entryStem, listFiles, readJson, readText, runMeta } from "./layout";
import type { Renderer } from "./render";

type CheckOf<T extends Check["type"]> = Extract<Check, { type: T }>;

interface RunFiles {
	workspace: string;
	changes: Changes | null;
	final: string | null;
	/** Lazily listed workspace files. */
	files: () => string[];
}

const result = (check: Check, pass: boolean | null, detail: string): CheckResult => ({
	id: check.id,
	type: check.type,
	pass,
	detail,
});

function list(items: string[], max = 5): string {
	const shown = items.slice(0, max).join(", ");
	return items.length > max ? `${shown}, … (+${items.length - max})` : shown;
}

function existsInWorkspace(run: RunFiles, path: string): boolean {
	const abs = join(run.workspace, path);
	return existsSync(abs) && statSync(abs).isFile();
}

function readWorkspaceText(run: RunFiles, path: string): string | null {
	return decodeText(readFileSync(join(run.workspace, path)));
}

function fileCheck(check: Check, run: RunFiles): CheckResult {
	switch (check.type) {
		case "unchanged":
		case "changed":
		case "only-changed": {
			const changes = run.changes;
			if (!changes) return result(check, null, "changes.json missing");
			const touched = new Set([...changes.added, ...changes.modified, ...changes.deleted]);
			if (check.type === "unchanged") {
				const changed = check.paths.filter((p) => touched.has(p));
				const missing = check.paths.filter((p) => !touched.has(p) && !existsInWorkspace(run, p));
				const problems = [
					...(changed.length ? [`changed: ${list(changed)}`] : []),
					...(missing.length ? [`missing from workspace: ${list(missing)}`] : []),
				];
				return problems.length
					? result(check, false, problems.join("; "))
					: result(check, true, `${check.paths.length} file(s) unchanged`);
			}
			if (check.type === "changed") {
				const edited = new Set([...changes.added, ...changes.modified]);
				const not = check.paths.filter((p) => !edited.has(p));
				return not.length
					? result(check, false, `not added or modified: ${list(not)}`)
					: result(check, true, `${check.paths.length} file(s) added or modified`);
			}
			const globs = check.allow.map((g) => new Bun.Glob(g));
			const outside = [...touched].sort().filter((p) => !globs.some((g) => g.match(p)));
			return outside.length
				? result(check, false, `changed outside ${list(check.allow)}: ${list(outside)}`)
				: result(check, true, `${touched.size} changed file(s), all within ${list(check.allow)}`);
		}
		case "present":
		case "absent": {
			if (!existsSync(run.workspace)) return result(check, null, "workspace/ missing");
			const glob = new Bun.Glob(check.files);
			const files = run.files().filter((p) => glob.match(p));
			const regex = new RegExp(check.pattern, check.flags);
			const hits: string[] = [];
			const binary: string[] = [];
			for (const file of files) {
				const text = readWorkspaceText(run, file);
				if (text === null) binary.push(file);
				else if (regex.test(text)) hits.push(file);
				regex.lastIndex = 0;
			}
			const skipped = binary.length ? `; skipped non-text: ${list(binary)}` : "";
			if (check.type === "present") {
				if (!files.length) return result(check, false, `no file matches ${check.files}`);
				return hits.length
					? result(check, true, `/${check.pattern}/ found in ${list(hits)}${skipped}`)
					: result(check, false, `/${check.pattern}/ not found in ${files.length} file(s)${skipped}`);
			}
			if (!files.length) return result(check, true, `no file matches ${check.files}`);
			return hits.length
				? result(check, false, `/${check.pattern}/ found in ${list(hits)}${skipped}`)
				: result(check, true, `/${check.pattern}/ absent from ${files.length} file(s)${skipped}`);
		}
		case "final-mentions":
		case "final-omits": {
			if (run.final === null) return result(check, null, "final.md missing");
			const found = new RegExp(check.pattern, check.flags).test(run.final);
			const pass = check.type === "final-mentions" ? found : !found;
			return result(check, pass, `/${check.pattern}/ ${found ? "matches" : "does not match"} final.md`);
		}
		case "render":
			throw new Error("render is not a file check");
	}
}

async function renderCheck(
	check: CheckOf<"render">,
	run: RunFiles,
	runDir: string,
	renderer: Renderer,
	screens: ScreenResult[],
): Promise<CheckResult> {
	if (!existsSync(run.workspace)) return result(check, null, "workspace/ missing");
	if (!existsInWorkspace(run, check.entry)) return result(check, false, `entry not found: ${check.entry}`);
	const outcome = await renderer({
		workspace: run.workspace,
		entry: check.entry,
		widths: check.widths,
		schemes: check.schemes,
		outDir: join(runDir, "screens"),
	});
	if (!outcome.ok) return result(check, null, `render unavailable: ${outcome.error}`);
	const mine: ScreenResult[] = outcome.screens.map((s) => ({
		entry: check.entry,
		width: s.width,
		scheme: s.scheme,
		path: `screens/${s.file}`,
		overflowPx: s.overflowPx,
		consoleErrors: s.consoleErrors,
	}));
	for (const screen of mine) {
		const at = screens.findIndex((s) => s.path === screen.path);
		if (at >= 0) screens[at] = screen;
		else screens.push(screen);
	}
	const failures: string[] = [];
	if (check.assert.includes("no-horizontal-overflow")) {
		const over = mine.filter((s) => s.overflowPx > 0);
		if (over.length)
			failures.push(`horizontal overflow: ${over.map((s) => `${s.width}-${s.scheme} ${s.overflowPx}px`).join(", ")}`);
	}
	if (check.assert.includes("no-console-errors")) {
		const errs = mine.filter((s) => s.consoleErrors.length);
		if (errs.length)
			failures.push(
				`console errors: ${errs.map((s) => `${s.width}-${s.scheme}: ${s.consoleErrors[0]}`).join("; ")}`,
			);
	}
	const blocked = outcome.blockedRequests.length
		? `; blocked ${outcome.blockedRequests.length} external request(s)`
		: "";
	if (failures.length) return result(check, false, failures.join("; ") + blocked);
	const asserted = check.assert.length ? check.assert.join(", ") : "no assertions";
	return result(check, true, `${mine.length} screen(s) of ${entryStem(check.entry)}: ${asserted} ok${blocked}`);
}

/** Grades one run directory against the case's checks. */
export async function gradeRun(def: Case, runDir: string, renderer: Renderer): Promise<RunGrading> {
	if (!runMeta(runDir))
		return {
			checks: def.checks.map((c) => result(c, null, "run failed: meta.json missing")),
			screens: [],
		};
	const workspace = join(runDir, "workspace");
	let cached: string[] | null = null;
	const run: RunFiles = {
		workspace,
		changes: readJson<Changes>(join(runDir, "changes.json")),
		final: readText(join(runDir, "final.md")),
		files: () => (cached ??= listFiles(workspace)),
	};
	const checks: CheckResult[] = [];
	const screens: ScreenResult[] = [];
	for (const check of def.checks) {
		try {
			checks.push(
				check.type === "render"
					? await renderCheck(check, run, runDir, renderer, screens)
					: fileCheck(check, run),
			);
		} catch (error) {
			checks.push(result(check, null, `check error: ${(error as Error).message}`));
		}
	}
	return { checks, screens };
}
