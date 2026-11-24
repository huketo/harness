// Contract tests for skills/full-send/scripts/gated-merge.mjs. Repositories, HOME, the allowlist, and the gh
// executable are temporary stand-ins; nothing reads the user's allowlist and nothing contacts a remote.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { parseAllowlist } from "../../../plugin/hooks/merge-guard.mjs";
import { ghChecks, localRefusal, mergeArgs, parseArgs, prRepo, reviewApproved, viewRefusal } from "./gated-merge.mjs";

const SCRIPT = join(import.meta.dirname, "gated-merge.mjs");
const KEY = "github.com/example-owner/harness";
const ALLOW = parseAllowlist("github.com/example-owner/*\ngitlab.example/team/allowed\n");
const HEAD = "a".repeat(40);
const APPROVED = "Summary\n\nReviewed with review-loop: 2 rounds with a-reviewer on high. Verdict: approved\nmodel line";

test("only a positive number in range, one merge method, and the two known switches parse", () => {
	assert.deepEqual(parseArgs(["12"]), { number: "12", method: "squash", deleteBranch: false, dryRun: false });
	assert.deepEqual(parseArgs(["12", "--merge", "--delete-branch"]), { number: "12", method: "merge", deleteBranch: true, dryRun: false });
	for (const argv of [[], ["0"], ["!12"], ["#12"], ["12", "13"], ["branch"], ["99999999999999999999"], ["12", "--admin"], ["12", "--auto"], ["12", "-R", "x/y"], ["12", "--squash", "--merge"], ["https://github.com/a/b/pull/12"]])
		assert.equal(parseArgs(argv), null, JSON.stringify(argv));
});

test("this machine alone refuses full-stop, a repository off the allowlist, and anything not on github.com", () => {
	const r = (over = {}) => localRefusal({ key: KEY, allow: ALLOW, mode: "none", ...over });
	assert.equal(r(), null);
	assert.equal(r({ mode: "full-send" }), null);
	assert.match(r({ mode: "full-stop" }), /full-stop/);
	assert.match(r({ key: "github.com/someone-else/repo" }), /allowlist/);
	assert.match(r({ allow: [] }), /allowlist/);
	assert.match(r({ key: "gitlab.example/team/allowed" }), /only GitHub/);
	assert.match(r({ key: null }), /only GitHub/);
});

test("what GitHub answers must be this open PR in this repository with passing CI and an approval", () => {
	const ok = { number: 12, repo: KEY, state: "open", head: HEAD, ci: "pass", review: true };
	const r = (view) => viewRefusal({ key: KEY, number: "12", view });
	assert.equal(r(ok), null);
	assert.match(r(null), /could not be read/);
	assert.match(r({ ...ok, number: 13 }), /answered for #13/);
	// A fork whose CLI default is its upstream, or any other redirection, answers for another repository.
	assert.match(r({ ...ok, repo: "github.com/upstream-owner/harness" }), /resolves in/);
	assert.match(r({ ...ok, state: "merged" }), /not open/);
	assert.match(r({ ...ok, head: undefined }), /head commit/);
	for (const ci of ["pending", "fail", "missing"]) assert.match(r({ ...ok, ci }), /not passing/);
	assert.match(r({ ...ok, review: false }), /review-loop/);
});

test("the merge is GitHub's immediate endpoint, pinned to the checked repository and head", () => {
	assert.deepEqual(mergeArgs({ key: KEY, number: "12", method: "squash", head: HEAD }), [
		"api",
		"--hostname",
		"github.com",
		"-X",
		"PUT",
		"repos/example-owner/harness/pulls/12/merge",
		"-f",
		`sha=${HEAD}`,
		"-f",
		"merge_method=squash",
	]);
});

test("CI and review state: anything short of a concluded success is not a pass", () => {
	assert.equal(ghChecks([]), "missing");
	assert.equal(ghChecks(undefined), "missing");
	assert.equal(ghChecks([{ status: "COMPLETED", conclusion: "SUCCESS" }, { state: "SUCCESS" }, { conclusion: "SKIPPED" }]), "pass");
	assert.equal(ghChecks([{ conclusion: "SUCCESS" }, { status: "IN_PROGRESS", conclusion: "" }]), "pending");
	assert.equal(ghChecks([{ conclusion: "SUCCESS" }, { conclusion: "FAILURE" }]), "fail");
	assert.equal(ghChecks([{ conclusion: "SKIPPED" }, { conclusion: "NEUTRAL" }]), "missing");
	assert.equal(reviewApproved(APPROVED), true);
	assert.equal(reviewApproved("Reviewed with review-loop: 5 rounds with a-reviewer. Verdict: deadlock"), false);
	assert.equal(reviewApproved("quote: > Reviewed with review-loop: 1 rounds with x. Verdict: approved"), false);
	assert.equal(reviewApproved(null), false);
});

test("a PR URL names its repository only through the full owner/repo/pull/number route", () => {
	assert.equal(prRepo(`https://${KEY}/pull/12`, 12), KEY);
	assert.equal(prRepo("https://github.com/pull/pull/pull/12", 12), "github.com/pull/pull");
	assert.equal(prRepo(`https://${KEY}/pull/13`, 12), null);
	assert.equal(prRepo(`https://${KEY}/pull/12/files`, 12), null);
	assert.equal(prRepo("https://github.com/a/b/c/pull/12", 12), null);
	assert.equal(prRepo(undefined, 12), null);
});

// End to end with a stand-in `gh` that answers the view and the merge from files and records every call.
let root, env, repo, calls;
const answer = (name, value) => writeFileSync(join(root, name), JSON.stringify(value));
const view = (over = {}) =>
	answer("view.json", {
		number: 12,
		url: `https://${KEY}/pull/12`,
		state: "OPEN",
		headRefOid: HEAD,
		headRefName: "feature",
		isCrossRepository: false,
		body: APPROVED,
		statusCheckRollup: [{ conclusion: "SUCCESS" }],
		...over,
	});
const merge = (...argv) => spawnSync("node", [SCRIPT, ...argv], { cwd: repo, env, encoding: "utf8" });
const recorded = () => readFileSync(calls, "utf8").trim().split("\n").filter(Boolean);
const VIEW_CALL = `pr view 12 -R ${KEY} --json number,url,state,headRefOid,headRefName,isCrossRepository,body,statusCheckRollup`;
const MERGE_CALL = `api --hostname github.com -X PUT repos/example-owner/harness/pulls/12/merge -f sha=${HEAD} -f merge_method=squash`;
let remote, HEAD_REAL, OTHER_REAL;

before(() => {
	root = mkdtempSync(join(tmpdir(), "gated-merge-test-"));
	const config = join(root, "config");
	const bin = join(root, "bin");
	repo = join(root, "repo");
	calls = join(root, "calls.txt");
	mkdirSync(join(config, "harness"), { recursive: true });
	mkdirSync(bin);
	mkdirSync(repo);
	writeFileSync(join(config, "harness/full-send-repos"), "github.com/example-owner/*\ngitlab.example/team/*\n");
	writeFileSync(
		join(bin, "gh"),
		`#!/bin/sh\necho "$*" >> "${calls}"\ncase "$*" in\n  "pr view"*) cat "${join(root, "view.json")}" ;;\n  *PUT*) cat "${join(root, "merge.json")}" ;;\nesac\nexit 0\n`,
	);
	chmodSync(join(bin, "gh"), 0o755);
	env = { ...process.env, HOME: join(root, "home"), XDG_CONFIG_HOME: config, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1", PATH: `${bin}:${process.env.PATH}` };
	execFileSync("git", ["init", "-q", repo], { env });
	// A local bare repository stands in for github.com through a URL rewrite, with two branches on one commit.
	remote = join(root, "remote.git");
	const git = (...argv) => execFileSync("git", argv, { env, encoding: "utf8" }).trim();
	git("init", "-q", "--bare", remote);
	git("-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "one");
	HEAD_REAL = git("-C", repo, "rev-parse", "HEAD");
	git("-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "two");
	OTHER_REAL = git("-C", repo, "rev-parse", "HEAD");
	git("-C", repo, "push", "-q", remote, `${HEAD_REAL}:refs/heads/feature`, `${HEAD_REAL}:refs/heads/feature#draft`);
	git("-C", repo, "config", `url.${remote}.pushInsteadOf`, "git@github.com:example-owner/harness.git");
	git("-C", repo, "remote", "add", "origin", "git@github.com:example-owner/harness.git");
});
after(() => rmSync(root, { recursive: true, force: true }));

test("end to end: a passing, approved PR merges through the pinned call and nothing else does", () => {
	writeFileSync(calls, "");
	view({ headRefOid: HEAD_REAL, headRefName: "feature#draft" });
	answer("merge.json", { merged: true, sha: "b".repeat(40) });
	const ok = merge("12", "--delete-branch");
	assert.equal(ok.status, 0, ok.stdout + ok.stderr);
	assert.deepEqual(recorded(), [VIEW_CALL, MERGE_CALL.replace(HEAD, HEAD_REAL)]);
	// The branch goes through git with a lease on the merged head, so a later push or a look-alike name survives.
	assert.match(ok.stdout, /deleted branch feature#draft/);
	assert.equal(execFileSync("git", ["-C", remote, "branch", "--list"], { env, encoding: "utf8" }).trim(), "feature");
	execFileSync("git", ["-C", repo, "push", "-q", remote, `${OTHER_REAL}:refs/heads/feature#draft`], { env });
	view({ headRefOid: HEAD_REAL, headRefName: "feature#draft" });
	const moved = merge("12", "--delete-branch");
	assert.match(moved.stdout, /was not deleted/);
	assert.match(execFileSync("git", ["-C", remote, "branch", "--list"], { env, encoding: "utf8" }), /feature#draft/);
	view();

	// A merge queue or auto-merge would leave the PR open; anything but a confirmed merge is a failure.
	writeFileSync(calls, "");
	answer("merge.json", { merged: false, message: "queued" });
	const queued = merge("12");
	assert.equal(queued.status, 1);
	assert.match(queued.stdout, /did not confirm/);

	writeFileSync(calls, "");
	view({ isCrossRepository: true });
	answer("merge.json", { merged: true, sha: "b".repeat(40) });
	assert.match(merge("12", "--delete-branch").stdout, /another repository/);
	assert.deepEqual(recorded(), [VIEW_CALL, MERGE_CALL]);

	const denied = (over, pattern) => {
		writeFileSync(calls, "");
		view(over);
		const out = merge("12");
		assert.equal(out.status, 1, out.stdout);
		assert.match(out.stdout, pattern);
		assert.deepEqual(recorded(), [VIEW_CALL]);
	};
	denied({ statusCheckRollup: [{ status: "IN_PROGRESS" }] }, /pending/);
	denied({ statusCheckRollup: [] }, /missing/);
	denied({ body: "no trailer" }, /review-loop/);
	denied({ url: "https://github.com/upstream-owner/harness/pull/12" }, /resolves in/);
	denied({ state: "MERGED" }, /not open/);
	denied({ number: 13 }, /answered for #13/);

	writeFileSync(calls, "");
	view();
	const dry = merge("12", "--dry-run");
	assert.equal(dry.status, 0);
	assert.match(dry.stdout, /would run: gh api /);
	assert.deepEqual(recorded(), [VIEW_CALL]);

	const offline = (setup, pattern) => {
		setup();
		writeFileSync(calls, "");
		const out = merge("12");
		assert.equal(out.status, 1);
		assert.match(out.stdout, pattern);
		assert.deepEqual(recorded(), []);
	};
	offline(() => writeFileSync(join(repo, ".git/harness-mode"), "mode=full-stop\n"), /full-stop/);
	rmSync(join(repo, ".git/harness-mode"));
	const origin = (url) => () => execFileSync("git", ["-C", repo, "remote", "set-url", "origin", url], { env });
	offline(origin("git@github.com:someone-else/repo.git"), /allowlist/);
	offline(origin("https://gitlab.example/team/allowed.git"), /only GitHub/);
	assert.equal(merge("12", "--admin").status, 2);
});
