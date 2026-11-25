// Contract tests for skills/review-loop/scripts/tree-unchanged.mjs, against a temporary repository with one linked
// worktree. Fixture commits do not inherit the workstation's signer, hooks, or global config.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { configChanges } from "./tree-unchanged.mjs";

const SCRIPT = join(import.meta.dirname, "tree-unchanged.mjs");
const env = { ...process.env, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1", GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid" };
let tmp, repo, wt, base, snapshotFile;
const git = (cwd, ...argv) => execFileSync("git", argv, { cwd, encoding: "utf8", env }).trim();
const run = (...argv) => spawnSync(process.execPath, [SCRIPT, ...argv], { encoding: "utf8", env });
const check = () => run("check", wt, base, snapshotFile);

before(() => {
	tmp = mkdtempSync(join(tmpdir(), "tree-unchanged-"));
	repo = join(tmp, "repo");
	wt = join(tmp, "child");
	snapshotFile = join(tmp, "before.json");
	git(tmp, "init", "-q", "-b", "main", repo);
	git(repo, "remote", "add", "origin", "https://example.invalid/owner/repo.git");
	git(repo, "config", "branch.main.remote", "origin");
	git(repo, "config", "branch.main.merge", "refs/heads/main");
	writeFileSync(join(repo, "a"), "a\n");
	writeFileSync(join(repo, ".gitignore"), "out/\n");
	git(repo, "add", "-A");
	git(repo, "commit", "-qm", "base");
	base = git(repo, "rev-parse", "HEAD");
	git(repo, "worktree", "add", "-q", wt, "-b", "child");
	writeFileSync(snapshotFile, run("snapshot", repo).stdout);
});
after(() => rmSync(tmp, { recursive: true, force: true }));

/** Runs the check between a change and its undo, and returns the result. */
function during(change, undo) {
	change();
	try {
		return check();
	} finally {
		undo();
	}
}
const withConfig = (...settings) => {
	copyFileSync(join(repo, ".git/config"), join(tmp, "config.bak"));
	for (const [key, value] of settings) git(wt, "config", key, value);
};
const restoreConfig = () => copyFileSync(join(tmp, "config.bak"), join(repo, ".git/config"));

test("a clean child worktree passes, and ignored build output is only counted", () => {
	assert.match(check().stdout, /^UNCHANGED head [0-9a-f]{12}; ignored entries 0\n$/);
	const built = during(
		() => {
			mkdirSync(join(wt, "out"));
			writeFileSync(join(wt, "out/x"), "");
		},
		() => rmSync(join(wt, "out"), { recursive: true }),
	);
	assert.equal(built.status, 0, built.stdout);
	assert.match(built.stdout, /ignored entries 1/);
});

test("any change to the working tree or to HEAD fails", () => {
	const restore = () => git(wt, "reset", "-q", "--hard", base);
	const edited = during(() => writeFileSync(join(wt, "a"), "b"), restore);
	const untracked = during(() => writeFileSync(join(wt, "new"), ""), () => rmSync(join(wt, "new")));
	const staged = during(() => {
		writeFileSync(join(wt, "a"), "c");
		git(wt, "add", "a");
	}, restore);
	const committed = during(() => git(wt, "commit", "-q", "--allow-empty", "-m", "x"), restore);
	for (const result of [edited, untracked, staged]) {
		assert.equal(result.status, 1, result.stdout);
		assert.match(result.stdout, /^CHANGED working tree\n/);
	}
	assert.equal(committed.status, 1);
	assert.match(committed.stdout, /\nCHANGED head /);
});

test("entries that the agent host, gh, glab, an editor, or a new branch add are noted and pass", () => {
	const result = during(
		() =>
			withConfig(
				["branch.review-r1.t3-merge-base", "main"],
				["branch.review-r1.t3-merge-base-ref", "origin/feat/a"],
				["branch.review-r1.gh-merge-base", "main"],
				["branch.feat.vscode-merge-base", "origin/main"],
				["branch.feat.remote", "origin"],
				["branch.feat.merge", "refs/heads/feat"],
				["remote.origin.glab-resolved", "base"],
				["remote.origin.glab-resolved-head", "head"],
				["remote.origin.glab-resolved-base", "base"],
			),
		restoreConfig,
	);
	assert.equal(result.status, 0, result.stdout);
	assert.match(result.stdout, /^NOTE config entries that other tools keep \(not a failure\):\nconfig: \+ branch\.feat\.merge=refs\/heads\/feat\n/);
	assert.equal(result.stdout.split("\n").filter((line) => line.startsWith("config: + ")).length, 9);
	assert.match(result.stdout, /UNCHANGED head /);
});

test("every other config entry fails, and a command it names does not run during the check", () => {
	const fails = (settings, pattern) => {
		const result = during(() => withConfig(...settings), restoreConfig);
		assert.equal(result.status, 1, result.stdout);
		assert.match(result.stdout, /CHANGED git control files\n/);
		assert.match(result.stdout, pattern);
	};
	fails([["core.fsmonitor", `touch ${join(tmp, "pwned")}`]], /config: \+ core\.fsmonitor=/);
	assert.equal(existsSync(join(tmp, "pwned")), false);
	fails([["core.hooksPath", "/tmp/elsewhere"]], /config: \+ core\.hookspath=/);
	fails([["alias.status", "!sh -c true"]], /config: \+ alias\.status=/);
	fails([["include.path", "/tmp/other.config"]], /config: \+ include\.path=/);
	fails([["remote.origin.url", "https://example.invalid/other/repo.git"]], /config: - remote\.origin\.url=.*\nconfig: \+ remote\.origin\.url=/);
	// An existing branch pointed at another remote is a change of value, not new tracking.
	fails([["branch.main.remote", "elsewhere"]], /config: - branch\.main\.remote=origin\nconfig: \+ branch\.main\.remote=elsewhere/);
	// glab's note holds "base" or "head"; anything else could name another project.
	fails([["remote.origin.glab-resolved", "other/project"]], /config: \+ remote\.origin\.glab-resolved=other\/project/);
});

test("a hook, a per-worktree config, or a redirected .git fails", () => {
	const hook = join(repo, ".git/hooks/post-checkout");
	const linked = join(repo, ".git/hooks/pre-commit");
	const perWorktree = join(repo, ".git/worktrees/child/config.worktree");
	const results = [
		during(() => writeFileSync(hook, "#!/bin/sh\n"), () => rmSync(hook)),
		during(() => symlinkSync("/bin/true", linked), () => rmSync(linked)),
		during(() => writeFileSync(perWorktree, "[core]\n\tfsmonitor = x\n"), () => rmSync(perWorktree)),
		during(
			() => {
				copyFileSync(join(wt, ".git"), join(tmp, "dotgit.bak"));
				git(tmp, "init", "-q", join(tmp, "other"));
				git(join(tmp, "other"), "commit", "-q", "--allow-empty", "-m", "o");
				writeFileSync(join(wt, ".git"), `gitdir: ${join(tmp, "other/.git")}\n`);
			},
			() => copyFileSync(join(tmp, "dotgit.bak"), join(wt, ".git")),
		),
	];
	for (const result of results) {
		assert.equal(result.status, 1, result.stdout);
		assert.match(result.stdout, /CHANGED git control files\n/);
	}
	assert.match(results[2].stdout, /worktrees\/child\/config\.worktree: \+ core\.fsmonitor=x/);
	assert.match(results[3].stdout, /\ncommon-dir .* -> .*other\/\.git\n/);
});

test("another branch that moved is reported and does not fail", () => {
	const result = during(() => git(repo, "commit", "-q", "--allow-empty", "-m", "other"), () => git(repo, "reset", "-q", "--hard", base));
	assert.equal(result.status, 0, result.stdout);
	assert.match(result.stdout, /^NOTE refs moved /);
});

test("a missing snapshot or a wrong argument count exits 2", () => {
	assert.equal(run("check", wt, base).status, 2);
	assert.equal(run("check", wt, base, join(tmp, "nope")).status, 2);
	assert.equal(run("snapshot").status, 2);
});

test("a repeated value counts once per occurrence, and a note that is removed stays a note", () => {
	const fetch = ["remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"];
	assert.deepEqual(configChanges([fetch], [fetch, fetch]).failures, [`+ ${fetch.join("=")}`]);
	assert.deepEqual(configChanges([["branch.x.t3-merge-base", "main"], ["remote.origin.glab-resolved", "other/project"], ["branch.x.remote", "origin"]], []), {
		notes: ["- branch.x.remote=origin", "- branch.x.t3-merge-base=main", "- remote.origin.glab-resolved=other/project"],
		failures: [],
	});
});
