// Contract tests for skills/full-send/scripts/sweep-landed.mjs. The origin, the clone, HOME, and the gh
// executable are temporary stand-ins; nothing contacts a remote.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { decide, parseWorktrees } from "./sweep-landed.mjs";

const SCRIPT = join(import.meta.dirname, "sweep-landed.mjs");

test("worktree entries carry the branch, the lock, and which one is the main worktree", () => {
	const list = parseWorktrees(
		"worktree /r\nHEAD aaa\nbranch refs/heads/main\n\nworktree /w/one\nHEAD bbb\nbranch refs/heads/feat/one\nlocked by hand\n\nworktree /w/two\nHEAD ccc\ndetached\n\nworktree /w/gone\nHEAD ddd\nbranch refs/heads/gone\nprunable gitdir file points to non-existent location\n",
	);
	assert.deepEqual(
		list.map((entry) => [entry.path, entry.branch, entry.locked, entry.prunable, entry.main]),
		[
			["/r", "main", false, false, true],
			["/w/one", "feat/one", true, false, false],
			["/w/two", null, false, false, false],
			["/w/gone", "gone", false, true, false],
		],
	);
});

test("a branch is removed only when it landed and nothing may still be using its worktree", () => {
	const clean = { main: false, current: false, locked: false, dirty: false, prunable: false };
	const d = (over = {}) => decide({ branch: "task", defaultBranch: "main", landed: true, unmoved: false, idle: () => false, worktree: null, ...over });
	assert.equal(d().remove, true);
	assert.equal(d({ worktree: clean }).remove, true);
	assert.match(d({ worktree: { ...clean, prunable: true } }).reason, /missing/);
	assert.equal(d({ unmoved: true }).remove, true);
	assert.match(d({ branch: "main" }).reason, /default branch/);
	assert.match(d({ landed: false }).reason, /not on the default branch/);
	assert.match(d({ landed: false, worktree: clean }).reason, /not on the default branch/);
	assert.match(d({ worktree: { ...clean, main: true } }).reason, /main worktree/);
	assert.match(d({ worktree: { ...clean, current: true } }).reason, /runs in/);
	assert.match(d({ worktree: { ...clean, locked: true } }).reason, /locked/);
	assert.match(d({ worktree: { ...clean, dirty: true } }).reason, /modified or untracked/);
	assert.match(d({ worktree: clean, unmoved: true }).reason, /no commit of its own/);
	assert.equal(d({ worktree: clean, unmoved: true, idle: () => true }).remove, true);
	assert.match(d({ worktree: { ...clean, dirty: true }, unmoved: true, idle: () => assert.fail("asked before the keep rules") }).reason, /modified or untracked/);
	for (const verdict of [d({ branch: "main" }), d({ landed: false }), d({ worktree: { ...clean, dirty: true } })]) assert.equal(verdict.remove, false);
});

let root, clone, env;
const URL = "https://github.com/example-owner/sweep";
const git = (cwd, ...argv) => execFileSync("git", argv, { cwd, encoding: "utf8", env }).trim();
const commit = (cwd, file) => {
	writeFileSync(join(cwd, file), file);
	git(cwd, "add", "-A");
	git(cwd, "commit", "-q", "-m", file);
	return git(cwd, "rev-parse", "HEAD");
};
const sweep = (cwd, ...argv) => spawnSync(process.execPath, [SCRIPT, ...argv], { cwd, encoding: "utf8", env });
const branches = () => git(clone, "for-each-ref", "--format=%(refname:short)", "refs/heads").split("\n").sort();

before(() => {
	root = mkdtempSync(join(tmpdir(), "sweep-landed-"));
	const home = join(root, "home");
	const bin = join(root, "bin");
	mkdirSync(home);
	mkdirSync(bin);
	env = { ...process.env, HOME: home, XDG_CONFIG_HOME: join(home, ".config"), GIT_CONFIG_NOSYSTEM: "1", PATH: `${bin}:${process.env.PATH}`, GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid" };
	writeFileSync(join(bin, "gh"), `#!/bin/sh\ncat "${join(root, "merged.json")}"\n`);
	chmodSync(join(bin, "gh"), 0o755);
	const bare = join(root, "origin.git");
	git(root, "init", "-q", "--bare", "-b", "main", bare);
	git(root, "config", "--global", `url.${bare}.insteadOf`, URL);
	git(root, "config", "--global", "init.defaultBranch", "main");
	clone = join(root, "clone");
	git(root, "init", "-q", clone);
	git(clone, "remote", "add", "origin", URL);
	commit(clone, "base");
	git(clone, "push", "-q", "-u", "origin", "main");

	// merged-commit: landed through a merge commit, clean worktree.
	const wt = (name, start = "main") => {
		git(clone, "worktree", "add", "-q", "-b", name, join(root, "wt", name), start);
		return join(root, "wt", name);
	};
	// fast-forwarded: landed without a merge commit, so its tip is a commit the default branch pointed at.
	git(clone, "merge", "-q", "--ff-only", commit(wt("fast-forwarded"), "ff"));
	const mergedCommit = commit(wt("merged-commit"), "a");
	// reviewer: cut from the first commit of the squashed PR, no worktree.
	const squashedDir = wt("squashed");
	const first = commit(squashedDir, "b1");
	git(clone, "branch", "reviewer", first);
	const squashedHead = commit(squashedDir, "b2");
	// dirty: landed, but its worktree holds an untracked file.
	const dirtyDir = wt("dirty");
	const dirtyHead = commit(dirtyDir, "c");
	writeFileSync(join(dirtyDir, "note"), "unsaved");
	// unfinished: commits nobody merged.
	commit(wt("unfinished"), "d");
	// here: landed, and the sweep runs inside its worktree.
	const hereHead = commit(wt("here"), "e");

	git(clone, "merge", "-q", "--no-ff", "-m", "merge merged-commit", mergedCommit);
	git(clone, "merge", "-q", "--squash", squashedHead);
	git(clone, "commit", "-q", "-m", "squashed");
	git(clone, "merge", "-q", "--no-ff", "-m", "merge dirty", dirtyHead);
	git(clone, "merge", "-q", "--no-ff", "-m", "merge here", hereHead);
	git(clone, "push", "-q", "origin", "main");
	// on-release: a commit that sits under a PR merged into another branch, and never reached the default branch.
	git(clone, "branch", "on-release", "unfinished");
	git(clone, "branch", "release-pr", "unfinished");
	// On origin, a tag named like the default branch, on unmerged work; locally, a tag named like a landed branch.
	git(clone, "push", "-q", "origin", "unfinished:refs/tags/main");
	git(clone, "tag", "merged-commit", "main");
	// fresh: a task that just started from the default branch and has no commit yet.
	wt("fresh-old");
	git(clone, "branch", "-m", "fresh-old", "fresh");
	git(clone, "worktree", "move", join(root, "wt", "fresh-old"), join(root, "wt", "fresh"));
	// idle: like fresh, but nothing has happened to its branch for two days, as with a reviewer that only read.
	const twoDaysAgo = `@${Math.floor(Date.now() / 1000) - 2 * 86400} +0000`;
	execFileSync("git", ["worktree", "add", "-q", "-b", "idle", join(root, "wt", "idle"), "main"], { cwd: clone, env: { ...env, GIT_COMMITTER_DATE: twoDaysAgo } });
	// reset-long-ago: idle too, but the only reflog entry left is a reset, so an earlier tip may live only in that reflog.
	const old = { cwd: clone, env: { ...env, GIT_COMMITTER_DATE: twoDaysAgo } };
	execFileSync("git", ["worktree", "add", "-q", "-b", "reset-long-ago", join(root, "wt", "reset-long-ago"), "main"], old);
	const tip = git(clone, "rev-parse", "main");
	writeFileSync(join(git(clone, "rev-parse", "--path-format=absolute", "--git-common-dir"), "logs/refs/heads/reset-long-ago"), `${"1".repeat(40)} ${tip} t <t@example.invalid> ${twoDaysAgo.slice(1)}\treset: moving to main\n`);
	// wandered: idle too, but a commit was made in it while detached, and only its HEAD reflog remembers that commit.
	const wandered = join(root, "wt", "wandered");
	execFileSync("git", ["worktree", "add", "-q", "-b", "wandered", wandered, "main"], old);
	execFileSync("git", ["checkout", "-q", "--detach"], { ...old, cwd: wandered });
	writeFileSync(join(wandered, "side"), "side");
	execFileSync("git", ["add", "-A"], { ...old, cwd: wandered });
	execFileSync("git", ["commit", "-q", "-m", "side"], { ...old, cwd: wandered });
	execFileSync("git", ["checkout", "-q", "wandered"], { ...old, cwd: wandered });
	// reset-expired: its reflog kept the creation and a reset back to main, whose old side is an unlanded commit.
	const logs = join(git(clone, "rev-parse", "--path-format=absolute", "--git-common-dir"), "logs");
	const stamp = `t <t@example.invalid> ${twoDaysAgo.slice(1)}`;
	const unlanded = git(clone, "rev-parse", "unfinished");
	execFileSync("git", ["worktree", "add", "-q", "-b", "reset-expired", join(root, "wt", "reset-expired"), "main"], old);
	writeFileSync(join(logs, "refs/heads/reset-expired"), `${"0".repeat(40)} ${tip} ${stamp}\tbranch: Created from main\n${unlanded} ${tip} ${stamp}\treset: moving to main\n`);
	// wandered-expired: its HEAD log kept only the checkout back from a detached commit, which is that entry's old side.
	const expired = join(root, "wt", "wandered-expired");
	execFileSync("git", ["worktree", "add", "-q", "-b", "wandered-expired", expired, "main"], old);
	writeFileSync(git(expired, "rev-parse", "--path-format=absolute", "--git-path", "logs/HEAD"), `${unlanded} ${tip} ${stamp}\tcheckout: moving from ${unlanded} to wandered-expired\n`);
	// hidden-note: idle too, with an untracked file that this repository's status setting hides.
	execFileSync("git", ["worktree", "add", "-q", "-b", "hidden-note", join(root, "wt", "hidden-note"), "main"], old);
	writeFileSync(join(root, "wt", "hidden-note", "note"), "unsaved");
	git(clone, "config", "status.showUntrackedFiles", "no");
	writeFileSync(join(root, "merged.json"), JSON.stringify([{ number: 7, headRefOid: squashedHead, baseRefName: "main" }, { number: 8, headRefOid: git(clone, "rev-parse", "release-pr"), baseRefName: "release" }]));
});

after(() => rmSync(root, { recursive: true, force: true }));

test("without --apply the sweep lists the landed branches and deletes nothing", () => {
	const all = branches();
	const result = sweep(join(root, "wt", "here"));
	assert.equal(result.status, 0, result.stderr);
	for (const name of ["merged-commit", "squashed", "reviewer", "fast-forwarded", "idle"]) assert.match(result.stdout, new RegExp(`would delete {2}${name}\\b`));
	for (const name of ["dirty", "unfinished", "here", "fresh", "main", "on-release", "release-pr", "reset-long-ago", "reset-expired", "wandered", "wandered-expired", "hidden-note"]) assert.doesNotMatch(result.stdout, new RegExp(`would delete {2}${name}\\b`));
	assert.deepEqual(branches(), all);
	assert.equal(existsSync(join(root, "wt", "merged-commit")), true);
});

test("with --apply it deletes landed branches and their clean worktrees, and keeps everything that may be in use", () => {
	const result = sweep(join(root, "wt", "here"), "--apply");
	assert.equal(result.status, 0, result.stderr);
	assert.deepEqual(branches(), ["dirty", "fresh", "here", "hidden-note", "main", "on-release", "release-pr", "reset-expired", "reset-long-ago", "unfinished", "wandered", "wandered-expired"]);
	for (const name of ["merged-commit", "squashed", "fast-forwarded", "idle"]) assert.equal(existsSync(join(root, "wt", name)), false, name);
	for (const name of ["dirty", "unfinished", "here", "fresh", "reset-long-ago", "reset-expired", "wandered", "wandered-expired", "hidden-note"]) assert.equal(existsSync(join(root, "wt", name)), true, name);
	assert.match(result.stdout, /deleted 5 of 17 local branches/);
});

test("when GitHub cannot be asked, a squashed branch is kept", () => {
	const dir = join(root, "wt", "later");
	git(clone, "worktree", "add", "-q", "-b", "later", dir, "main");
	const head = commit(dir, "f");
	git(clone, "merge", "-q", "--squash", head);
	git(clone, "commit", "-q", "-m", "squashed later");
	git(clone, "push", "-q", "origin", "main");
	writeFileSync(join(root, "bin", "gh"), "#!/bin/sh\nexit 1\n");
	const result = sweep(clone, "--apply");
	assert.equal(result.status, 0, result.stderr);
	assert.match(result.stdout, /could not be read from GitHub/);
	assert.equal(branches().includes("later"), true);
	// Run from the main worktree, `here` is no longer the current worktree and its landed branch goes.
	assert.equal(branches().includes("here"), false);
});

test("a deletion that fails is reported and the sweep exits 1", () => {
	const dir = join(root, "wt", "stuck");
	git(clone, "worktree", "add", "-q", "-b", "stuck", dir, "main");
	git(clone, "merge", "-q", "--no-ff", "-m", "merge stuck", commit(dir, "g"));
	git(clone, "push", "-q", "origin", "main");
	// Git refuses to delete this one ref, as it would when the branch moved after the sweep read it.
	mkdirSync(join(root, "hooks"));
	writeFileSync(join(root, "hooks", "reference-transaction"), "#!/bin/sh\n[ \"$1\" = prepared ] && grep -q ' refs/heads/stuck$' && exit 1\nexit 0\n");
	chmodSync(join(root, "hooks", "reference-transaction"), 0o755);
	git(clone, "config", "core.hooksPath", join(root, "hooks"));
	const result = sweep(clone, "--apply");
	git(clone, "config", "--unset", "core.hooksPath");
	assert.equal(result.status, 1, result.stdout + result.stderr);
	assert.match(result.stdout, /failed {2}stuck/);
	assert.equal(branches().includes("stuck"), true);
});

test("a file that appears after the sweep read the worktree keeps it, even when the repository hides untracked files", () => {
	const dir = join(root, "wt", "racer");
	execFileSync("git", ["worktree", "add", "-q", "-b", "racer", dir, "main"], { cwd: clone, env: { ...env, GIT_COMMITTER_DATE: `@${Math.floor(Date.now() / 1000) - 2 * 86400} +0000` } });
	// The stand-in for GitHub writes the file, which is after the sweep looked at every worktree.
	writeFileSync(join(root, "bin", "gh"), `#!/bin/sh\necho late > "${join(dir, "note")}"\necho '[]'\n`);
	const result = sweep(clone, "--apply");
	assert.equal(result.status, 1, result.stdout + result.stderr);
	assert.match(result.stdout, /failed {2}racer/);
	assert.equal(existsSync(join(dir, "note")), true);
	assert.equal(branches().includes("racer"), true);
});

test("any argument other than --apply is refused", () => {
	assert.equal(sweep(clone, "--force").status, 2);
	assert.equal(sweep(clone, "--apply", "--apply").status, 2);
});
