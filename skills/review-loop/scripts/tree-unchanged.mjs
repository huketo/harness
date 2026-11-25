#!/usr/bin/env node
// tree-unchanged.mjs snapshot <worktree> > before.json      (run before delegating the reviewer)
// tree-unchanged.mjs check <worktree> <sha> <before.json>   (run after it returns)
// Read-only proof for a reviewer that ran with write access in a linked worktree. `check` exits 0 only when HEAD is
// still <sha>, the worktree has no staged, unstaged, or untracked change, and the shared git control files that can
// run code or redirect git (config, config.worktree, hooks/, info/) hold nothing new.
// The config files are compared entry by entry, because other writers touch them while a review runs: the agent host
// records a merge base for each worktree it makes, gh, glab, and editors keep their own notes, and a new branch
// gains its tracking. Those entries are printed as NOTE and do not fail; `noteOnly` below is the whole list, and
// every other entry that appears, disappears, or changes value fails the check.
// Ref changes are listed but do not fail, because other workers may commit to their own branches meanwhile. Ignored
// files are counted, not failed. Every git call disables hooks and fsmonitor, so a tampered config cannot run code
// during the check itself.
// This catches a well-meaning reviewer's stray writes; it is not a sandbox against a hostile one (use codex/review.ts).
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { lstatSync, readdirSync, readFileSync, readlinkSync, realpathSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const BRANCH_NOTES = /^branch\..+\.(t3-merge-base|t3-merge-base-ref|gh-merge-base|vscode-merge-base)$/;
const REMOTE_NOTES = /^remote\..+\.(glab-resolved|glab-resolved-base|glab-resolved-head)$/;
const TRACKING = /^branch\..+\.(remote|merge)$/;

/**
 * Whether one config entry may appear or disappear without failing the check. `sign` is "+" or "-"; `changedKeys`
 * holds the keys that have both a removed and an added entry, which is how a changed value looks.
 */
export function noteOnly({ sign, key, value, changedKeys }) {
	if (BRANCH_NOTES.test(key)) return true;
	if (REMOTE_NOTES.test(key)) return sign === "-" || value === "base" || value === "head";
	// A branch gaining or losing its tracking redirects nothing; an existing branch pointed somewhere else does.
	if (TRACKING.test(key)) return !changedKeys.has(key);
	return false;
}

/** `{ notes, failures }` as printable lines, from the `[key, value]` entries of one config file before and after. */
export function configChanges(before, after) {
	const count = (entries) => {
		const seen = new Map();
		for (const [key, value] of entries) seen.set(JSON.stringify([key, value]), (seen.get(JSON.stringify([key, value])) ?? 0) + 1);
		return seen;
	};
	const [was, now] = [count(before), count(after)];
	const diff = [];
	for (const id of new Set([...was.keys(), ...now.keys()])) {
		const delta = (now.get(id) ?? 0) - (was.get(id) ?? 0);
		const [key, value] = JSON.parse(id);
		for (let i = 0; i < Math.abs(delta); i++) diff.push({ sign: delta > 0 ? "+" : "-", key, value });
	}
	const signs = new Map();
	for (const entry of diff) signs.set(entry.key, (signs.get(entry.key) ?? "") + entry.sign);
	const changedKeys = new Set([...signs].filter(([, seen]) => seen.includes("+") && seen.includes("-")).map(([key]) => key));
	const out = { notes: [], failures: [] };
	for (const entry of diff.sort((a, b) => (a.key + a.sign).localeCompare(b.key + b.sign)))
		(noteOnly({ ...entry, changedKeys }) ? out.notes : out.failures).push(`${entry.sign} ${entry.key}=${entry.value}`);
	return out;
}

const env = { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_OPTIONAL_LOCKS: "0" };
const git = (worktree, ...argv) =>
	execFileSync("git", ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-C", worktree, ...argv], { encoding: "utf8", env, stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 * 1024 * 1024 });

/** The `[key, value]` entries of a config file, null when the file is missing, or a string saying why it could not be read. */
function configEntries(file) {
	if (!lstatSync(file, { throwIfNoEntry: false })) return null;
	if (lstatSync(file).isSymbolicLink()) return `symlink to ${readlinkSync(file)}`;
	try {
		const listed = execFileSync("git", ["config", "--file", file, "--list", "--null"], { encoding: "utf8", env, stdio: ["ignore", "pipe", "pipe"] });
		return listed.split("\0").filter(Boolean).map((entry) => {
			const cut = entry.indexOf("\n");
			return cut < 0 ? [entry, ""] : [entry.slice(0, cut), entry.slice(cut + 1)];
		});
	} catch {
		return "unreadable as a git config file";
	}
}

/** Every file and symlink under `dir`, as `{ <path relative to base>: "sha256 <hex>" | "symlink <target>" }`. */
function digests(base, dir, out = {}) {
	const stat = lstatSync(dir, { throwIfNoEntry: false });
	if (!stat) return out;
	if (stat.isSymbolicLink()) out[relative(base, dir)] = `symlink ${readlinkSync(dir)}`;
	else if (stat.isDirectory()) for (const name of readdirSync(dir).sort()) digests(base, join(dir, name), out);
	else if (stat.isFile()) out[relative(base, dir)] = `sha256 ${createHash("sha256").update(readFileSync(dir)).digest("hex")}`;
	return out;
}

function snapshot(worktree) {
	const common = realpathSync(git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir").trim());
	const config = {};
	const linked = lstatSync(join(common, "worktrees"), { throwIfNoEntry: false })?.isDirectory() ? readdirSync(join(common, "worktrees")).sort() : [];
	for (const file of ["config", "config.worktree", ...linked.map((name) => join("worktrees", name, "config.worktree"))]) {
		const entries = configEntries(join(common, file));
		if (entries !== null) config[file] = entries;
	}
	const refs = git(worktree, "for-each-ref", "--format=%(objectname) %(refname)").split("\n").filter(Boolean);
	return { commonDir: common, config, files: { ...digests(common, join(common, "hooks")), ...digests(common, join(common, "info")) }, refs };
}

function check(worktree, sha, beforeFile) {
	let before;
	try {
		before = JSON.parse(readFileSync(beforeFile, "utf8"));
	} catch {
		process.stderr.write(`missing or unreadable snapshot: ${beforeFile}\n`);
		process.exit(2);
	}
	const now = snapshot(worktree);
	const notes = [];
	const failures = [];
	if (now.commonDir !== before.commonDir) failures.push(`common-dir ${before.commonDir} -> ${now.commonDir}`);
	for (const file of new Set([...Object.keys(before.config), ...Object.keys(now.config)])) {
		const [was, is] = [before.config[file] ?? [], now.config[file] ?? []];
		if (typeof was === "string" || typeof is === "string") {
			if (was !== is) failures.push(`${file}: ${typeof is === "string" ? is : "was not a readable config file before"}`);
			continue;
		}
		const changes = configChanges(was, is);
		notes.push(...changes.notes.map((line) => `${file}: ${line}`));
		failures.push(...changes.failures.map((line) => `${file}: ${line}`));
	}
	for (const path of new Set([...Object.keys(before.files), ...Object.keys(now.files)]))
		if (before.files[path] !== now.files[path]) failures.push(`${path}: ${before.files[path] ?? "absent"} -> ${now.files[path] ?? "absent"}`);
	const moved = [...before.refs.filter((ref) => !now.refs.includes(ref)).map((ref) => `< ${ref}`), ...now.refs.filter((ref) => !before.refs.includes(ref)).map((ref) => `> ${ref}`)];
	const print = (lines) => process.stdout.write(`${lines.slice(0, 20).join("\n")}\n`);
	if (moved.length > 0) print(["NOTE refs moved (judge whether another writer explains them):", ...moved]);
	if (notes.length > 0) print(["NOTE config entries that other tools keep (not a failure):", ...notes]);
	const stop = (lines) => {
		print(lines);
		process.exit(1);
	};
	if (failures.length > 0) stop(["CHANGED git control files", ...failures]);
	let want;
	try {
		want = git(worktree, "rev-parse", "--verify", "--quiet", `${sha}^{commit}`).trim();
	} catch {
		stop([`CHANGED ${sha} is not a commit in this worktree's repository`]);
	}
	const head = git(worktree, "rev-parse", "HEAD").trim();
	if (head !== want) stop([`CHANGED head ${head} != ${want}`, ...git(worktree, "log", "--oneline", `${want}..${head}`).split("\n").filter(Boolean)]);
	const changes = git(worktree, "status", "--porcelain=v1", "--untracked-files=all").split("\n").filter(Boolean);
	if (changes.length > 0) stop(["CHANGED working tree", ...changes]);
	const ignored = git(worktree, "status", "--porcelain=v1", "--ignored=matching").split("\n").filter((line) => line.startsWith("!!")).length;
	process.stdout.write(`UNCHANGED head ${head.slice(0, 12)}; ignored entries ${ignored}\n`);
}

function main() {
	const [command, ...rest] = process.argv.slice(2);
	if (command === "snapshot" && rest.length === 1) process.stdout.write(`${JSON.stringify(snapshot(rest[0]), null, "\t")}\n`);
	else if (command === "check" && rest.length === 3) check(...rest);
	else {
		process.stderr.write("usage: tree-unchanged.mjs snapshot <worktree> | check <worktree> <sha> <before.json>\n");
		process.exit(2);
	}
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
