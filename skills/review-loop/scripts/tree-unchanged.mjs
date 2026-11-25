#!/usr/bin/env node
// tree-unchanged.mjs snapshot <worktree> > before.json      (run before delegating the reviewer)
// tree-unchanged.mjs check <worktree> <sha> <before.json>   (run after it returns)
// Read-only proof for a reviewer that ran with write access in a linked worktree. `check` exits 0 only when HEAD is
// still <sha>, the worktree has no staged, unstaged, or untracked change, and the shared git control files that can
// run code or redirect git (config, config.worktree, hooks/, info/) hold nothing new.
// The config files are compared entry by entry, because other writers touch them while a review runs: the agent host
// records a merge base for each worktree it makes, gh, glab, and editors keep their own notes, and a new branch
// gains its tracking. Those entries are printed as NOTE and do not fail; `noteOnly` below is the whole list. With
// them set aside, the remaining entries must be the same in the same order, and a per-worktree config must be the
// same file.
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
 * Whether one `[key, value]` entry of the shared config is a note that may come and go. `other` is the set of keys
 * on the other side of the comparison: tracking is a note only for a branch that has none there, so a second value
 * for an existing branch, which git would read instead of the first, is not one.
 */
export function noteOnly([key, value], other) {
	if (BRANCH_NOTES.test(key)) return true;
	if (REMOTE_NOTES.test(key)) return value === "base" || value === "head";
	return TRACKING.test(key) && !other.has(key);
}

/**
 * `{ notes, failures }` as printable lines, from the ordered `[key, value]` entries of the shared config before and
 * after; a value is null for a key written without one. With the notes set aside, the two sequences must be equal,
 * order included, because git reads the last value of a key and the first url of a remote. A failure names the key
 * and not its values, which can hold a credential.
 */
export function configChanges(before, after) {
	const keys = (entries) => new Set(entries.map(([key]) => key));
	const split = (entries, other) => ({ notes: entries.filter((entry) => noteOnly(entry, other)), rest: entries.filter((entry) => !noteOnly(entry, other)) });
	const [was, now] = [split(before, keys(after)), split(after, keys(before))];
	const id = (entry) => JSON.stringify(entry);
	const only = (mine, theirs) => {
		const left = theirs.map(id);
		return mine.filter((entry) => {
			const at = left.indexOf(id(entry));
			if (at >= 0) left.splice(at, 1);
			return at < 0;
		});
	};
	const line = (sign) => ([key, value]) => Buffer.from(`${sign} ${key}${value === null ? "" : `=${value}`}`, "latin1").toString("utf8");
	const notes = [...only(was.notes, now.notes).map(line("-")), ...only(now.notes, was.notes).map(line("+"))];
	const failures = [];
	if (was.rest.map(id).join("\n") !== now.rest.map(id).join("\n")) {
		const values = (entries, key) => id(entries.filter((entry) => entry[0] === key));
		const changed = [...new Set([...was.rest, ...now.rest].map(([key]) => key))].filter((key) => values(was.rest, key) !== values(now.rest, key));
		failures.push(...(changed.length > 0 ? changed.sort().map((key) => `entries of ${key} differ`) : ["the order of the entries differs"]));
	}
	return { notes, failures };
}

const env = { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_OPTIONAL_LOCKS: "0" };
const git = (worktree, ...argv) =>
	execFileSync("git", ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-C", worktree, ...argv], { encoding: "utf8", env, stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 * 1024 * 1024 });

/** The ordered `[key, value]` entries of a config file, one character per byte; a value is null for a key written without one. It throws when git cannot list the file. */
function configEntries(file) {
	// latin1 keeps every byte apart: decoded as UTF-8, two different invalid sequences would both become U+FFFD.
	const listed = execFileSync("git", ["config", "--file", file, "--list", "--null"], { encoding: "latin1", env, stdio: ["ignore", "pipe", "pipe"], maxBuffer: 1024 * 1024 * 1024 });
	return listed.split("\0").filter(Boolean).map((entry) => {
		const cut = entry.indexOf("\n");
		return cut < 0 ? [entry, null] : [entry.slice(0, cut), entry.slice(cut + 1)];
	});
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
	// Only the shared config is read entry by entry. A per-worktree config is where nothing is expected to write, so it is digested like a hook.
	const linked = lstatSync(join(common, "worktrees"), { throwIfNoEntry: false })?.isDirectory() ? readdirSync(join(common, "worktrees")).sort() : [];
	const files = {};
	for (const path of ["config", "config.worktree", "hooks", "info", ...linked.map((name) => join("worktrees", name, "config.worktree"))]) digests(common, join(common, path), files);
	let config = null;
	if (files.config?.startsWith("sha256 ")) {
		try {
			config = configEntries(join(common, "config"));
		} catch {
			// Left null: the check then fails, whatever the other snapshot holds.
		}
	}
	delete files.config;
	const refs = git(worktree, "for-each-ref", "--format=%(objectname) %(refname)").split("\n").filter(Boolean);
	return { commonDir: common, config, files, refs };
}

function check(worktree, sha, beforeFile) {
	let before;
	try {
		before = JSON.parse(readFileSync(beforeFile, "utf8"));
	} catch {
		process.stderr.write(`missing or unreadable snapshot: ${beforeFile}\n`);
		process.exit(2);
	}
	const print = (lines) => process.stdout.write(`${lines.slice(0, 20).join("\n")}\n`);
	const stop = (lines) => {
		print(lines);
		process.exit(1);
	};
	let now;
	try {
		now = snapshot(worktree);
	} catch {
		// git's own message can repeat a config value, so it is not printed.
		stop(["CHANGED git cannot read this worktree's repository; run `git status` there to see why"]);
	}
	const notes = [];
	const failures = [];
	if (now.commonDir !== before.commonDir) failures.push(`common-dir ${before.commonDir} -> ${now.commonDir}`);
	if (!Array.isArray(before.config) || !Array.isArray(now.config)) failures.push("config: is not a plain file that git can list, before or after, so it cannot be compared");
	else {
		const changes = configChanges(before.config, now.config);
		notes.push(...changes.notes.map((line) => `config: ${line}`));
		failures.push(...changes.failures.map((line) => `config: ${line}`));
	}
	for (const path of new Set([...Object.keys(before.files), ...Object.keys(now.files)]))
		if (before.files[path] !== now.files[path]) failures.push(`${path}: ${before.files[path] ?? "absent"} -> ${now.files[path] ?? "absent"}`);
	const moved = [...before.refs.filter((ref) => !now.refs.includes(ref)).map((ref) => `< ${ref}`), ...now.refs.filter((ref) => !before.refs.includes(ref)).map((ref) => `> ${ref}`)];
	if (moved.length > 0) print(["NOTE refs moved (judge whether another writer explains them):", ...moved]);
	if (notes.length > 0) print(["NOTE config entries that other tools keep (not a failure):", ...notes]);
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
