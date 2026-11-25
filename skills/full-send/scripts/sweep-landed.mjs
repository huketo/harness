#!/usr/bin/env node
// sweep-landed — delete the local branches and worktrees of work that already landed on the default branch.
// A branch has landed when its tip is a commit of the default branch, or a commit of a PR that GitHub reports as
// merged into the default branch (which covers squash merges and reviewer branches cut from a PR's commits).
// What is kept, whatever else holds:
//   the default branch, the main worktree, the worktree this command runs in, a locked worktree, a worktree with
//   modified or untracked files, a detached worktree, a worktree whose directory is missing, and a worktree whose
//   branch has not moved since it was created on a commit the default branch itself pointed at, because that is
//   how a task that just started looks. Ignored files do not keep a worktree, as with `git worktree remove`.
// Usage: sweep-landed.mjs [--apply]
// Without --apply it prints what it would delete and deletes nothing. It never touches a remote.
// It exits 1 when a deletion it attempted failed.
import { execFileSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { sep } from "node:path";
import { fileURLToPath } from "node:url";
import { repoKey } from "../../../plugin/hooks/merge-guard.mjs";

/** The entries of `git worktree list --porcelain`; the first one is the main worktree. */
export function parseWorktrees(porcelain) {
	return porcelain
		.split(/\n\n+/)
		.map((block) => block.trim())
		.filter(Boolean)
		.map((block, index) => {
			const entry = { path: null, branch: null, locked: false, prunable: false, main: index === 0 };
			for (const line of block.split("\n")) {
				if (line.startsWith("worktree ")) entry.path = line.slice(9);
				else if (line.startsWith("branch refs/heads/")) entry.branch = line.slice(18);
				else if (line === "locked" || line.startsWith("locked ")) entry.locked = true;
				else if (line === "prunable" || line.startsWith("prunable ")) entry.prunable = true;
			}
			return entry;
		});
}

/**
 * What to do with one local branch: `{ remove, reason }`.
 * `landed` is whether the tip is a commit of the default branch or of a merged PR; `unmoved` is whether the
 * branch still sits where it was created, on a commit the default branch itself pointed at; `worktree` is the
 * branch's worktree entry with `current` and `dirty` added, or null.
 */
export function decide({ branch, defaultBranch, landed, unmoved, worktree }) {
	const keep = (reason) => ({ remove: false, reason });
	if (branch === defaultBranch) return keep("the default branch");
	if (!landed) return keep("has commits that are not on the default branch or in a merged PR");
	if (!worktree) return { remove: true, reason: "landed, no worktree" };
	if (worktree.prunable) return keep("its worktree directory is missing (git worktree prune or repair)");
	if (worktree.main) return keep("checked out in the main worktree");
	if (worktree.current) return keep("this command runs in its worktree");
	if (worktree.locked) return keep("its worktree is locked");
	if (worktree.dirty) return keep("its worktree has modified or untracked files");
	if (unmoved) return keep("its worktree has no commit of its own yet");
	return { remove: true, reason: "landed, worktree clean" };
}

function run(file, argv, cwd) {
	return execFileSync(file, argv, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 * 1024 * 1024 });
}

/** Commits of GitHub PRs merged into the default branch that are not on it, or null when GitHub could not be asked. */
function mergedPrCommits(key, defaultBranch, upstream, git, cwd) {
	if (key.split("/")[0] !== "github.com" || key.split("/").length !== 3) return null;
	let prs;
	try {
		prs = JSON.parse(run("gh", ["pr", "list", "-R", key, "--state", "merged", "--base", defaultBranch, "--limit", "1000", "--json", "number,headRefOid,baseRefName"], cwd));
		prs = prs.filter((pr) => pr.baseRefName === defaultBranch);
	} catch {
		return null;
	}
	const has = (oid) => {
		try {
			git(["cat-file", "-e", `${oid}^{commit}`]);
			return true;
		} catch {
			return false;
		}
	};
	const missing = prs.filter((pr) => !has(pr.headRefOid));
	if (missing.length > 0) {
		try {
			git(["fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "origin", ...missing.map((pr) => `refs/pull/${pr.number}/head`)]);
		} catch {
			// A head that cannot be fetched is left out below; its branches are then kept.
		}
	}
	const heads = prs.map((pr) => pr.headRefOid).filter((oid) => /^[0-9a-f]{40,64}$/.test(oid) && has(oid));
	if (heads.length === 0) return new Set();
	return new Set(git(["rev-list", ...heads, "--not", upstream]).split("\n").filter(Boolean));
}

function main() {
	const argv = process.argv.slice(2);
	if (argv.some((arg) => arg !== "--apply") || argv.length > 1) {
		process.stderr.write("usage: sweep-landed.mjs [--apply]\n");
		process.exit(2);
	}
	const apply = argv.length === 1;
	const cwd = process.cwd();
	const git = (args, dir = cwd) => run("git", ["-c", "core.fsmonitor=false", ...args], dir).trim();
	let origin, defaultBranch, upstream;
	try {
		origin = git(["config", "--get", "remote.origin.url"]);
	} catch {
		process.stderr.write("sweep-landed: needs a git worktree with an origin remote\n");
		process.exit(2);
	}
	try {
		defaultBranch = git(["ls-remote", "--symref", "origin", "HEAD"]).match(/^ref: refs\/heads\/(\S+)\tHEAD$/m)[1];
		git(["fetch", "--quiet", "--no-tags", "origin", `refs/heads/${defaultBranch}`]);
		upstream = git(["rev-parse", "--verify", "FETCH_HEAD^{commit}"]);
	} catch {
		process.stderr.write("sweep-landed: could not read and fetch origin's default branch; nothing deleted\n");
		process.exit(1);
	}
	const here = realpathSync(cwd);
	const worktrees = new Map();
	for (const entry of parseWorktrees(git(["worktree", "list", "--porcelain"]))) {
		if (!entry.branch) continue;
		if (!entry.prunable && !entry.locked) {
			try {
				const path = realpathSync(entry.path);
				entry.current = here === path || here.startsWith(path + sep);
				entry.dirty = git(["status", "--porcelain"], entry.path) !== "";
			} catch {
				entry.prunable = true;
			}
		}
		worktrees.set(entry.branch, entry);
	}
	const mainline = new Set(git(["rev-list", "--first-parent", upstream]).split("\n"));
	const onDefault = new Set(git(["rev-list", upstream]).split("\n"));
	const merged = mergedPrCommits(repoKey(origin), defaultBranch, upstream, git, cwd);
	if (merged === null) process.stdout.write("sweep-landed: merged PRs could not be read from GitHub, so only branches whose tip is on the default branch count as landed\n");
	const branches = git(["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"]).split("\n").filter(Boolean);
	let removed = 0;
	let failed = 0;
	const kept = new Map();
	for (const line of branches) {
		const [ref, tip] = line.split(" ");
		const branch = ref.slice("refs/heads/".length);
		const worktree = worktrees.get(branch) ?? null;
		const moves = worktree ? new Set(git(["reflog", "show", "--format=%H", ref]).split("\n").filter(Boolean)).size : 0;
		const verdict = decide({ branch, defaultBranch, landed: onDefault.has(tip) || (merged?.has(tip) ?? false), unmoved: mainline.has(tip) && moves <= 1, worktree });
		if (!verdict.remove) {
			kept.set(verdict.reason, [...(kept.get(verdict.reason) ?? []), branch]);
			continue;
		}
		const where = worktree ? ` and worktree ${worktree.path}` : "";
		if (apply) {
			try {
				if (worktree) git(["worktree", "remove", worktree.path]);
				if (git(["worktree", "list", "--porcelain"]).split("\n").includes(`branch ${ref}`)) throw new Error("checked out in a worktree");
				git(["update-ref", "-d", ref, tip]);
			} catch (error) {
				process.stdout.write(`failed  ${branch}${where}: ${String(error.stderr || error.message).trim().split("\n")[0]}\n`);
				failed++;
				continue;
			}
		}
		removed++;
		process.stdout.write(`${apply ? "deleted" : "would delete"}  ${branch}${where}\n`);
	}
	for (const [reason, names] of kept) process.stdout.write(`kept (${reason}): ${names.join(", ")}\n`);
	process.stdout.write(`sweep-landed: ${apply ? "deleted" : "would delete"} ${removed} of ${branches.length} local branches${apply ? "" : "; run with --apply to delete them"}\n`);
	if (failed > 0) process.exit(1);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
