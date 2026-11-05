/**
 * Skill materialization: turn an arm's `SkillRef`s into directories whose
 * bytes are pinned to a commit.
 *
 * - local: `git archive <sha> <path>` from this repository, so uncommitted
 *   working-tree edits never leak into a run.
 * - git source: a clone under `<out-root>/sources/<key>@<commit>/`, checked
 *   out at the pinned commit. The clone is untrusted data: nothing inside it
 *   is executed, hooks are disabled, and only file bytes are copied.
 */

import { spawnSync } from "node:child_process";
import { existsSync, lstatSync, mkdirSync, mkdtempSync, renameSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import type { Arm, GitSource, MaterializedSkill, SkillRef } from "../schema.ts";
import { copyTree, listFiles, skillExclude, treeSha256 } from "./files.ts";

const SAFE_GIT = ["-c", "core.hooksPath=/dev/null", "-c", "core.autocrlf=false", "-c", "advice.detachedHead=false"];

export function git(args: string[], cwd: string, input?: Buffer): Buffer {
	const res = spawnSync("git", [...SAFE_GIT, ...args], {
		cwd,
		input,
		maxBuffer: 1 << 30,
		// System and global config (filter drivers, attributes files, includes) never
		// apply: a cloned repo's .gitattributes must not select an installed driver.
		env: {
			...process.env,
			GIT_TERMINAL_PROMPT: "0",
			GIT_CONFIG_NOSYSTEM: "1",
			GIT_CONFIG_GLOBAL: "/dev/null",
			GIT_ATTR_NOSYSTEM: "1",
		},
	});
	if (res.error) throw res.error;
	if (res.status !== 0)
		throw new Error(`git ${args.join(" ")} failed (rc=${res.status}): ${res.stderr.toString().trim()}`);
	return res.stdout;
}

export function gitText(args: string[], cwd: string): string {
	return git(args, cwd).toString().trim();
}

export function skillName(ref: SkillRef): string {
	return ref.path.split("/").filter(Boolean).at(-1) ?? "";
}

/** Rejects absolute paths and `..` segments so a suite cannot read outside its tree. */
export function checkSkillPath(path: string): void {
	const parts = path.split("/").filter(Boolean);
	if (path.startsWith("/") || !parts.length || parts.some((p) => p === ".." || p === "."))
		throw new Error(`skill path "${path}" must be a relative path without "." or ".." segments`);
}

/** Rejects `path` when any of its components under `root` is a symlink (it could point outside `root`). */
export function checkNoSymlinkComponents(root: string, path: string): void {
	const parts = path.split("/").filter(Boolean);
	for (let i = 1; i <= parts.length; i++) {
		const rel = parts.slice(0, i).join("/");
		if (lstatSync(join(root, rel), { throwIfNoEntry: false })?.isSymbolicLink())
			throw new Error(`skill path "${path}": "${rel}" is a symlink`);
	}
}

/** Resolves a git ref in `repoRoot` to a full commit SHA. */
export function resolveRef(repoRoot: string, ref: string): string {
	return gitText(["rev-parse", "--verify", "--end-of-options", `${ref}^{commit}`], repoRoot);
}

/** Extracts `path` at `sha` from `repoRoot` into `dest`, without the skill's `evals/`. */
export function materializeLocal(repoRoot: string, sha: string, path: string, dest: string): void {
	checkSkillPath(path);
	const tar = git(["archive", "--format=tar", sha, "--", path], repoRoot);
	const staging = mkdtempSync(join(tmpdir(), "skill-eval-archive-"));
	try {
		const res = spawnSync("tar", ["-x", "-C", staging], { input: tar });
		if (res.status !== 0) throw new Error(`tar failed: ${res.stderr.toString().trim()}`);
		const src = join(staging, path);
		checkNoSymlinkComponents(staging, path);
		if (!existsSync(src) || !lstatSync(src).isDirectory())
			throw new Error(`local skill ${path} is not a directory at ${sha}`);
		copyTree(src, dest, skillExclude);
	} finally {
		rmSync(staging, { recursive: true, force: true });
	}
}

/**
 * Ensures `<outRoot>/sources/<key>@<commit>/` is a checkout of `src.commit`.
 * Reuses an existing clone only when its HEAD is exactly that commit.
 */
export function ensureGitSource(outRoot: string, key: string, src: GitSource): string {
	const dir = join(outRoot, "sources", `${key}@${src.commit}`);
	if (existsSync(dir)) {
		const head = gitText(["rev-parse", "HEAD"], dir);
		if (head !== src.commit)
			throw new Error(`source ${key}: ${dir} has HEAD ${head}, expected ${src.commit}; remove it to re-clone`);
		return dir;
	}
	mkdirSync(dirname(dir), { recursive: true });
	const tmp = `${dir}.tmp-${process.pid}`;
	rmSync(tmp, { recursive: true, force: true });
	try {
		git(["clone", "--quiet", "--no-checkout", "--", src.repo, tmp], dirname(dir));
		try {
			git(["cat-file", "-e", `${src.commit}^{commit}`], tmp);
		} catch {
			git(["fetch", "--quiet", "origin", src.commit], tmp);
		}
		git(["checkout", "--quiet", "--detach", src.commit], tmp);
		const head = gitText(["rev-parse", "HEAD"], tmp);
		if (head !== src.commit) throw new Error(`source ${key}: checkout gave ${head}, expected ${src.commit}`);
		renameSync(tmp, dir);
	} catch (e) {
		rmSync(tmp, { recursive: true, force: true });
		throw e;
	}
	return dir;
}

/** Copies `path` from a verified, clean source checkout into `dest`. */
export function materializeFromCheckout(checkout: string, key: string, path: string, dest: string): void {
	checkSkillPath(path);
	const dirty = gitText(["status", "--porcelain", "--untracked-files=all", "--", path], checkout);
	if (dirty) throw new Error(`source ${key}: ${path} differs from the pinned commit in ${checkout}:\n${dirty}`);
	const src = join(checkout, path);
	checkNoSymlinkComponents(checkout, path);
	if (!existsSync(src) || !lstatSync(src).isDirectory())
		throw new Error(`source ${key}: ${path} is not a directory`);
	copyTree(src, dest, skillExclude);
}

export interface Materialized {
	meta: MaterializedSkill;
	/** Directory holding the copied skill files. */
	dir: string;
}

export interface MaterializeContext {
	repoRoot: string;
	outRoot: string;
	sources: Record<string, GitSource>;
	/** Resolved SHA used for this arm's local skills. */
	localSha?: string;
}

/** Materializes every skill of an arm under `stageDir/<name>/`. */
export function materializeArm(arm: Arm, stageDir: string, ctx: MaterializeContext): Materialized[] {
	rmSync(stageDir, { recursive: true, force: true });
	const out: Materialized[] = [];
	for (const ref of arm.skills) {
		const name = skillName(ref);
		const dir = join(stageDir, name);
		let commit: string;
		if (ref.source === "local") {
			if (!ctx.localSha) throw new Error(`local skill ${ref.path}: no resolved ref`);
			commit = ctx.localSha;
			materializeLocal(ctx.repoRoot, commit, ref.path, dir);
		} else {
			const src = ctx.sources[ref.source];
			if (!src) throw new Error(`unknown source "${ref.source}"`);
			commit = src.commit;
			materializeFromCheckout(ensureGitSource(ctx.outRoot, ref.source, src), ref.source, ref.path, dir);
		}
		const links = listFiles(dir).filter((rel) => lstatSync(join(dir, rel)).isSymbolicLink());
		if (links.length) throw new Error(`skill ${ref.source}:${ref.path} contains symlinks: ${links.join(", ")}`);
		if (!existsSync(join(dir, "SKILL.md"))) throw new Error(`skill ${ref.source}:${ref.path} has no SKILL.md`);
		out.push({ meta: { name, source: ref.source, commit, path: ref.path, sha256: treeSha256(dir) }, dir });
	}
	return out;
}
