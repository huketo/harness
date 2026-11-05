/**
 * File-tree helpers shared by skill materialization and workspace capture.
 * Paths handed to filters and returned by `listFiles` are POSIX paths relative
 * to the walked root. Symlinks are kept as links and never followed.
 */

import { createHash } from "node:crypto";
import {
	copyFileSync,
	lstatSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	readlinkSync,
	symlinkSync,
} from "node:fs";
import { join } from "node:path";

/** Returns true when the entry (and, for a directory, everything below it) is skipped. */
export type Exclude = (rel: string, isDir: boolean) => boolean;

/**
 * Workspace capture rule (contract K7): `.skills/` at the workspace root, and
 * any `.git` or `node_modules` entry at any depth.
 */
export const workspaceExclude: Exclude = (rel) => {
	const parts = rel.split("/");
	if (parts[0] === ".skills") return true;
	return parts.some((p) => p === ".git" || p === "node_modules");
};

/** Skill copy rule (contract K8): the skill's top-level `evals/` never reaches the agent. */
export const skillExclude: Exclude = (rel) => rel.split("/")[0] === "evals";

/** Sorted relative POSIX paths of every regular file and symlink under `root`. */
export function listFiles(root: string, exclude?: Exclude): string[] {
	const out: string[] = [];
	const walk = (dir: string, prefix: string) => {
		for (const name of readdirSync(dir)) {
			const rel = prefix ? `${prefix}/${name}` : name;
			const abs = join(dir, name);
			const st = lstatSync(abs);
			const isDir = st.isDirectory();
			if (exclude?.(rel, isDir)) continue;
			if (isDir) walk(abs, rel);
			else if (st.isFile() || st.isSymbolicLink()) out.push(rel);
		}
	};
	walk(root, "");
	return out.sort();
}

/** Copies `src` into `dst` (created if missing), keeping symlinks as links. */
export function copyTree(src: string, dst: string, exclude?: Exclude): void {
	mkdirSync(dst, { recursive: true });
	const walk = (from: string, to: string, prefix: string) => {
		for (const name of readdirSync(from)) {
			const rel = prefix ? `${prefix}/${name}` : name;
			const abs = join(from, name);
			const st = lstatSync(abs);
			if (exclude?.(rel, st.isDirectory())) continue;
			const target = join(to, name);
			if (st.isDirectory()) {
				mkdirSync(target, { recursive: true });
				walk(abs, target, rel);
			} else if (st.isSymbolicLink()) {
				symlinkSync(readlinkSync(abs), target);
			} else if (st.isFile()) {
				copyFileSync(abs, target);
			}
		}
	};
	walk(src, dst, "");
}

/** Bytes of a file, or the link target text of a symlink. */
export function entryBytes(abs: string): Buffer {
	return lstatSync(abs).isSymbolicLink() ? Buffer.from(readlinkSync(abs)) : readFileSync(abs);
}

/**
 * `MaterializedSkill.sha256`: over every file in sorted relative POSIX path
 * order, hash `path + NUL + bytes + NUL`.
 */
export function treeSha256(root: string): string {
	const hash = createHash("sha256");
	for (const rel of listFiles(root)) {
		hash.update(rel);
		hash.update("\0");
		hash.update(entryBytes(join(root, rel)));
		hash.update("\0");
	}
	return hash.digest("hex");
}
