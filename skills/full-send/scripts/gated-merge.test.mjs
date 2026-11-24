// Contract tests for skills/full-send/scripts/gated-merge.mjs. Repositories, HOME, the allowlist, and the gh
// executable are temporary stand-ins; nothing reads the user's allowlist and nothing contacts a remote.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { parseAllowlist } from "../../../plugin/hooks/merge-guard.mjs";
import { ghChecks, glabChecks, mergeArgs, parseArgs, refusal, reviewApproved } from "./gated-merge.mjs";

const SCRIPT = join(import.meta.dirname, "gated-merge.mjs");
const KEY = "github.com/example-owner/harness";
const ALLOW = parseAllowlist("github.com/example-owner/*\ngitlab.example/team/allowed\n");
const HEAD = "a".repeat(40);
const APPROVED = "Summary\n\nReviewed with review-loop: 2 rounds with a-reviewer on high. Verdict: approved\nmodel line";

test("only a positive number, one merge method, and the two known switches parse", () => {
	assert.deepEqual(parseArgs(["12"]), { number: "12", method: "squash", deleteBranch: false, dryRun: false });
	assert.deepEqual(parseArgs(["12", "--merge", "--delete-branch"]), { number: "12", method: "merge", deleteBranch: true, dryRun: false });
	for (const argv of [[], ["0"], ["!12"], ["#12"], ["12", "13"], ["branch"], ["12", "--admin"], ["12", "--auto"], ["12", "-R", "x/y"], ["12", "--squash", "--merge"], ["https://github.com/a/b/pull/12"]])
		assert.equal(parseArgs(argv), null, JSON.stringify(argv));
});

test("every condition must hold before a merge", () => {
	const ok = { repo: KEY, state: "open", head: HEAD, ci: "pass", review: true };
	const r = (over = {}, view = ok) => refusal({ key: KEY, allow: ALLOW, mode: "none", cli: "gh", method: "squash", view, ...over });
	assert.equal(r(), null);
	assert.equal(r({ mode: "full-send" }), null);
	assert.match(r({ mode: "full-stop" }), /full-stop/);
	assert.match(r({ key: "github.com/someone-else/repo" }), /allowlist/);
	assert.match(r({ allow: [] }), /allowlist/);
	assert.match(r({}, null), /could not be read/);
	// A fork whose CLI default is its upstream, or any other redirection, answers for another repository.
	assert.match(r({}, { ...ok, repo: "github.com/upstream-owner/harness" }), /resolves in/);
	assert.match(r({}, { ...ok, state: "merged" }), /not open/);
	assert.match(r({}, { ...ok, head: undefined }), /head commit/);
	for (const ci of ["pending", "fail", "missing"]) assert.match(r({}, { ...ok, ci }), /not passing/);
	assert.match(r({}, { ...ok, review: false }), /review-loop/);
	const gitlab = { key: "gitlab.example/team/allowed", cli: "glab" };
	assert.equal(r(gitlab, { ...ok, repo: gitlab.key }), null);
	assert.match(r({ ...gitlab, method: "rebase" }, { ...ok, repo: gitlab.key }), /rebase/);
});

test("the merge is pinned to the checked repository and head, and GitLab never auto-merges", () => {
	assert.deepEqual(mergeArgs({ cli: "gh", key: KEY, number: "12", method: "squash", deleteBranch: true, head: HEAD }), ["pr", "merge", "12", "-R", KEY, "--squash", "--match-head-commit", HEAD, "--delete-branch"]);
	const glab = mergeArgs({ cli: "glab", key: "gitlab.example/team/allowed", number: "7", method: "squash", deleteBranch: false, head: HEAD });
	assert.deepEqual(glab, ["mr", "merge", "7", "-R", "gitlab.example/team/allowed", "--sha", HEAD, "--auto-merge=false", "--yes", "--squash"]);
});

test("CI and review state: anything short of a success on the current head is not a pass", () => {
	assert.equal(ghChecks([]), "missing");
	assert.equal(ghChecks(undefined), "missing");
	assert.equal(ghChecks([{ status: "COMPLETED", conclusion: "SUCCESS" }, { state: "SUCCESS" }, { conclusion: "SKIPPED" }]), "pass");
	assert.equal(ghChecks([{ conclusion: "SUCCESS" }, { status: "IN_PROGRESS", conclusion: "" }]), "pending");
	assert.equal(ghChecks([{ conclusion: "SUCCESS" }, { conclusion: "FAILURE" }]), "fail");
	assert.equal(ghChecks([{ conclusion: "SKIPPED" }, { conclusion: "NEUTRAL" }]), "missing");
	assert.equal(glabChecks({}), "missing");
	assert.equal(glabChecks({ sha: "aaa", head_pipeline: { status: "success", sha: "aaa" } }), "pass");
	assert.equal(glabChecks({ sha: "aaa", head_pipeline: { status: "running", sha: "aaa" } }), "pending");
	assert.equal(glabChecks({ sha: "aaa", head_pipeline: { status: "failed", sha: "aaa" } }), "fail");
	assert.equal(glabChecks({ sha: "bbb", head_pipeline: { status: "success", sha: "aaa" } }), "missing");
	assert.equal(glabChecks({ sha: "bbb", head_pipeline: { status: "success", sha: "mmm" } }, ["ttt", "bbb"]), "pass");
	assert.equal(glabChecks({ sha: "bbb", head_pipeline: { status: "success", sha: "mmm" } }, ["ttt", "aaa"]), "missing");
	assert.equal(reviewApproved(APPROVED), true);
	assert.equal(reviewApproved("Reviewed with review-loop: 5 rounds with a-reviewer. Verdict: deadlock"), false);
	assert.equal(reviewApproved("quote: > Reviewed with review-loop: 1 rounds with x. Verdict: approved"), false);
	assert.equal(reviewApproved(null), false);
});

// End to end with a stand-in `gh` that answers the view from a file and records every call.
let root, env, repo, calls;
const view = (over = {}) =>
	writeFileSync(
		join(root, "view.json"),
		JSON.stringify({ url: `https://${KEY}/pull/12`, state: "OPEN", headRefOid: HEAD, body: APPROVED, statusCheckRollup: [{ conclusion: "SUCCESS" }], ...over }),
	);
const merge = (...argv) => spawnSync("node", [SCRIPT, ...argv], { cwd: repo, env, encoding: "utf8" });
const recorded = () => readFileSync(calls, "utf8").trim().split("\n").filter(Boolean);

before(() => {
	root = mkdtempSync(join(tmpdir(), "gated-merge-test-"));
	const config = join(root, "config");
	const bin = join(root, "bin");
	repo = join(root, "repo");
	calls = join(root, "calls.txt");
	mkdirSync(join(config, "harness"), { recursive: true });
	mkdirSync(bin);
	mkdirSync(repo);
	writeFileSync(join(config, "harness/full-send-repos"), "github.com/example-owner/*\n");
	writeFileSync(join(bin, "gh"), `#!/bin/sh\necho "$*" >> "${calls}"\n[ "$2" = view ] && cat "${join(root, "view.json")}"\nexit 0\n`);
	chmodSync(join(bin, "gh"), 0o755);
	env = { ...process.env, HOME: join(root, "home"), XDG_CONFIG_HOME: config, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1", PATH: `${bin}:${process.env.PATH}` };
	execFileSync("git", ["init", "-q", repo], { env });
	execFileSync("git", ["-C", repo, "remote", "add", "origin", "git@github.com:example-owner/harness.git"], { env });
});
after(() => rmSync(root, { recursive: true, force: true }));

test("end to end: a passing, approved PR merges with the pinned command and nothing else does", () => {
	writeFileSync(calls, "");
	view();
	const ok = merge("12", "--delete-branch");
	assert.equal(ok.status, 0, ok.stdout + ok.stderr);
	assert.deepEqual(recorded(), [
		`pr view 12 -R ${KEY} --json statusCheckRollup,body,url,headRefOid,state`,
		`pr merge 12 -R ${KEY} --squash --match-head-commit ${HEAD} --delete-branch`,
	]);

	const denied = (over, pattern) => {
		writeFileSync(calls, "");
		view(over);
		const out = merge("12");
		assert.equal(out.status, 1, out.stdout);
		assert.match(out.stdout, pattern);
		assert.equal(recorded().some((line) => line.startsWith("pr merge")), false);
	};
	denied({ statusCheckRollup: [{ status: "IN_PROGRESS" }] }, /pending/);
	denied({ statusCheckRollup: [] }, /missing/);
	denied({ body: "no trailer" }, /review-loop/);
	denied({ url: "https://github.com/upstream-owner/harness/pull/12" }, /resolves in/);
	denied({ state: "MERGED" }, /not open/);

	writeFileSync(calls, "");
	view();
	const dry = merge("12", "--dry-run");
	assert.equal(dry.status, 0);
	assert.match(dry.stdout, /would run: gh pr merge 12/);
	assert.equal(recorded().length, 1);

	writeFileSync(join(repo, ".git/harness-mode"), "mode=full-stop\n");
	writeFileSync(calls, "");
	const stopped = merge("12");
	assert.equal(stopped.status, 1);
	assert.match(stopped.stdout, /full-stop/);
	assert.deepEqual(recorded(), []);
	rmSync(join(repo, ".git/harness-mode"));

	execFileSync("git", ["-C", repo, "remote", "set-url", "origin", "git@github.com:someone-else/repo.git"], { env });
	writeFileSync(calls, "");
	const foreign = merge("12");
	assert.equal(foreign.status, 1);
	assert.match(foreign.stdout, /allowlist/);
	assert.deepEqual(recorded(), []);
	assert.equal(merge("12", "--admin").status, 2);
});
