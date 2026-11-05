/**
 * Workspace capture against the fixture: `changes.json` and `diff.patch`.
 * Both sides are filtered with the workspace exclusion rule; a `null`
 * fixture compares against an empty directory.
 */

import { spawnSync } from "node:child_process";
import { lstatSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Changes } from "../schema.ts";
import { entryBytes, listFiles, workspaceExclude } from "./files.ts";

export function computeChanges(fixture: string | null, workspace: string): Changes {
	const before = new Set(fixture ? listFiles(fixture, workspaceExclude) : []);
	const after = new Set(listFiles(workspace, workspaceExclude));
	const added: string[] = [];
	const modified: string[] = [];
	const deleted: string[] = [];
	for (const rel of after) {
		if (!before.has(rel)) added.push(rel);
		else if (!entryBytes(join(fixture as string, rel)).equals(entryBytes(join(workspace, rel)))) modified.push(rel);
	}
	for (const rel of before) if (!after.has(rel)) deleted.push(rel);
	return { added: added.sort(), modified: modified.sort(), deleted: deleted.sort() };
}

/** Git's heuristic: a NUL byte in the first 8000 bytes means binary. */
function isText(abs: string): boolean {
	if (lstatSync(abs).isSymbolicLink()) return false;
	return !readFileSync(abs).subarray(0, 8000).includes(0);
}

/** Unified diff of the changed text files, with `a/` and `b/` workspace-relative labels. */
export function buildPatch(fixture: string | null, workspace: string, changes: Changes): string {
	const entries = [
		...changes.added.map((rel) => ({ rel, from: null as string | null, to: join(workspace, rel) as string | null })),
		...changes.modified.map((rel) => ({ rel, from: join(fixture as string, rel), to: join(workspace, rel) })),
		...changes.deleted.map((rel) => ({ rel, from: join(fixture as string, rel), to: null })),
	].sort((a, b) => (a.rel < b.rel ? -1 : a.rel > b.rel ? 1 : 0));
	let patch = "";
	for (const { rel, from, to } of entries) {
		if ((from && !isText(from)) || (to && !isText(to))) continue;
		const res = spawnSync(
			"diff",
			[
				"-u",
				"--label",
				from ? `a/${rel}` : "/dev/null",
				"--label",
				to ? `b/${rel}` : "/dev/null",
				from ?? "/dev/null",
				to ?? "/dev/null",
			],
			{ maxBuffer: 1 << 30 },
		);
		if (res.error) throw res.error;
		if (res.status !== 0 && res.status !== 1) throw new Error(`diff ${rel} failed: ${res.stderr.toString().trim()}`);
		patch += res.stdout.toString();
	}
	return patch;
}
