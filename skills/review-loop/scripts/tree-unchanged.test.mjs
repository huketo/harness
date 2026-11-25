// Contract tests for skills/review-loop/scripts/tree-unchanged.mjs, against a temporary repository with one linked
// worktree. Fixture commits do not inherit the workstation's signer, hooks, or global config.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { appendFileSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
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
	assert.match(result.stdout, /^NOTE config entries that other tools keep \(not a failure\):\nconfig: \+ /);
	for (const line of ["+ branch.feat.merge=refs/heads/feat", "+ branch.review-r1.t3-merge-base=main", "+ remote.origin.glab-resolved-head=head"]) assert.equal(result.stdout.includes(`config: ${line}\n`), true, line);
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
	fails([["core.fsmonitor", `touch ${join(tmp, "pwned")}`]], /config: entries of core\.fsmonitor differ/);
	assert.equal(existsSync(join(tmp, "pwned")), false);
	fails([["core.hooksPath", "/tmp/elsewhere"]], /config: entries of core\.hookspath differ/);
	fails([["alias.status", "!sh -c true"]], /config: entries of alias\.status differ/);
	fails([["include.path", "/tmp/other.config"]], /config: entries of include\.path differ/);
	// An existing branch pointed at another remote is a change of value, not new tracking.
	fails([["branch.main.remote", "elsewhere"]], /config: entries of branch\.main\.remote differ/);
	// glab's note holds "base" or "head"; anything else could name another project.
	fails([["remote.origin.glab-resolved", "other/project"]], /config: entries of remote\.origin\.glab-resolved differ/);
	// A failure names the key and keeps both values out of the transcript: a remote url can hold a credential.
	const url = during(() => withConfig(["remote.origin.url", "https://user:secret@example.invalid/other/repo.git"]), restoreConfig);
	assert.match(url.stdout, /config: entries of remote\.origin\.url differ\n/);
	assert.doesNotMatch(url.stdout, /example\.invalid|secret/);
});

test("a second value, a swapped order, a bare key made empty, and an unreadable config fail", () => {
	const config = join(repo, ".git/config");
	const rewritten = (edit) =>
		during(
			() => {
				copyFileSync(config, join(tmp, "config.bak"));
				edit();
			},
			restoreConfig,
		);
	// git reads the last value, so a second one changes where an existing branch pushes.
	const second = rewritten(() => git(repo, "config", "--add", "branch.main.remote", "elsewhere"));
	assert.match(second.stdout, /config: entries of branch\.main\.remote differ/);
	// With two urls, git fetches from the first.
	git(repo, "config", "--add", "remote.origin.url", "https://example.invalid/mirror/repo.git");
	appendFileSync(config, "[probe]\n\tflag\n");
	writeFileSync(snapshotFile, run("snapshot", repo).stdout);
	const swapped = rewritten(() => {
		git(repo, "config", "--unset-all", "remote.origin.url");
		git(repo, "config", "--add", "remote.origin.url", "https://example.invalid/mirror/repo.git");
		git(repo, "config", "--add", "remote.origin.url", "https://example.invalid/owner/repo.git");
	});
	assert.match(swapped.stdout, /config: entries of remote\.origin\.url differ/);
	// `flag` alone reads as true, `flag =` as false.
	const emptied = rewritten(() => writeFileSync(config, readFileSync(config, "utf8").replace("\tflag\n", "\tflag =\n")));
	assert.match(emptied.stdout, /config: entries of probe\.flag differ/);
	const broken = rewritten(() => appendFileSync(config, "[unterminated\n"));
	assert.equal(broken.stdout, "CHANGED git cannot read this worktree's repository\n");
	// Two values that differ only in bytes that are not UTF-8 are different values.
	git(repo, "config", "probe.path", "x");
	const bytes = (hex) => writeFileSync(config, Buffer.concat([readFileSync(config).subarray(0, readFileSync(config).lastIndexOf("path = ")), Buffer.from("path = "), Buffer.from(hex, "hex"), Buffer.from("\n")]));
	bytes("ff");
	writeFileSync(snapshotFile, run("snapshot", repo).stdout);
	const rebyted = rewritten(() => bytes("fe"));
	assert.match(rebyted.stdout, /config: entries of probe\.path differ/);
	// A note is printed as the text it is.
	const named = rewritten(() => git(repo, "config", "branch.리뷰.t3-merge-base", "main"));
	assert.equal(named.stdout.includes("config: + branch.리뷰.t3-merge-base=main\n"), true, named.stdout);
	const renamed = rewritten(() => git(repo, "config", "remote.리뷰.url", "https://example.invalid/x.git"));
	assert.equal(renamed.stdout.includes("config: entries of remote.리뷰.url differ\n"), true, renamed.stdout);
	for (const result of [second, swapped, emptied, broken, rebyted]) assert.equal(result.status, 1, result.stdout);
	assert.equal(check().status, 0);
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
	assert.match(results[2].stdout, /worktrees\/child\/config\.worktree: absent -> sha256 /);
	// A per-worktree config fails whatever it holds, a note included.
	const noted = during(() => writeFileSync(perWorktree, "[branch \"child\"]\n\tt3-merge-base = main\n"), () => rmSync(perWorktree));
	assert.equal(noted.status, 1, noted.stdout);
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

test("notes come and go in any number; everything else must keep its entries and their order", () => {
	const fetch = ["remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"];
	assert.deepEqual(configChanges([fetch], [fetch, fetch]).failures, ["entries of remote.origin.fetch differ"]);
	assert.deepEqual(configChanges([["a.x", "1"], ["b.y", "2"]], [["b.y", "2"], ["a.x", "1"]]).failures, ["the order of the entries differs"]);
	assert.deepEqual(configChanges([["branch.x.t3-merge-base", "main"], ["remote.origin.glab-resolved", "base"], ["branch.x.remote", "origin"], fetch], [fetch, ["branch.y.gh-merge-base", "main"]]), {
		notes: ["- branch.x.t3-merge-base=main", "- remote.origin.glab-resolved=base", "- branch.x.remote=origin", "+ branch.y.gh-merge-base=main"],
		failures: [],
	});
	// Removing a glab note that named a project is not a note, and neither is tracking that both sides have.
	assert.deepEqual(configChanges([["remote.origin.glab-resolved", "other/project"]], []).failures, ["entries of remote.origin.glab-resolved differ"]);
	assert.deepEqual(configChanges([["branch.x.remote", "origin"]], [["branch.x.remote", "origin"], ["branch.x.remote", "fork"]]).failures, ["entries of branch.x.remote differ"]);
	assert.deepEqual(configChanges([["core.flag", null]], [["core.flag", ""]]).failures, ["entries of core.flag differ"]);
});
