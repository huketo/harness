// Contract tests for plugin/hooks/merge-guard.mjs and skills/full-send/scripts/harness-mode.
// Repositories, HOME, and the allowlist are temporary; nothing reads the real worktree's mode or the user's
// allowlist, and nothing contacts a remote. Owners and hosts are synthetic.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import {
	allowedRepo,
	allowlistFile,
	decide,
	mergeCommand,
	mergeRepo,
	parseAllowlist,
	parseState,
	readPayload,
	render,
	repoKey,
	sameRepo,
	targetRepo,
} from "./merge-guard.mjs";

const GUARD = join(import.meta.dirname, "merge-guard.mjs");
const MODE = join(import.meta.dirname, "../../skills/full-send/scripts/harness-mode");
const NOW = 1_800_000_000;
const ALLOW = parseAllowlist("# synthetic allowlist\ngithub.com/example-owner/*\ngitlab.example/team/allowed.git\n");
let root, env;

before(() => {
	root = mkdtempSync(join(tmpdir(), "merge-guard-test-"));
	const config = join(root, "config");
	mkdirSync(join(config, "harness"), { recursive: true });
	writeFileSync(join(config, "harness/full-send-repos"), "# synthetic allowlist\ngithub.com/example-owner/*\ngitlab.example/team/allowed.git\n");
	env = { ...process.env, HOME: join(root, "home"), XDG_CONFIG_HOME: config, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1" };
});
after(() => rmSync(root, { recursive: true, force: true }));

function repo(name, origin) {
	const dir = join(root, name);
	execFileSync("git", ["init", "-q", dir], { env });
	execFileSync("git", ["-C", dir, "remote", "add", "origin", origin], { env });
	return dir;
}

function mode(dir, ...args) {
	return spawnSync(MODE, args, { cwd: dir, encoding: "utf8", env });
}

function modeWith(dir, extra, ...args) {
	return spawnSync(MODE, args, { cwd: dir, encoding: "utf8", env: { ...env, ...extra } });
}

function hook(format, payload, cwd, extra = {}) {
	return spawnSync("node", [GUARD, "--format", format], { cwd, input: JSON.stringify(payload), encoding: "utf8", env: { ...env, ...extra } });
}

test("merge commands are recognized through shell composition", () => {
	assert.equal(mergeCommand("gh pr merge 12 --squash"), "gh");
	assert.equal(mergeCommand("cd /x && glab mr merge 5 --sha abc"), "glab");
	assert.equal(mergeCommand("FOO=1 gh pr merge"), "gh");
	assert.equal(mergeCommand("echo $(glab mr merge 3)"), "glab");
	assert.equal(mergeCommand("gh api -X PUT repos/o/r/pulls/7/merge"), "gh");
	assert.equal(mergeCommand("glab api --method PUT projects/1/merge_requests/9/merge"), "glab");
	assert.equal(mergeCommand("glab mr \\\n  merge 4"), "glab");
	assert.equal(mergeCommand("glab mr view 5"), null);
	assert.equal(mergeCommand("gh pr view 5 --json mergeable"), null);
	assert.equal(mergeCommand("git merge main"), null);
	assert.equal(mergeCommand("echo 'mygh pr merge'"), null);
	assert.equal(mergeCommand("/usr/bin/gh pr merge 3"), "gh");
	assert.equal(mergeCommand('"glab" mr merge 3'), "glab");
	assert.equal(mergeCommand("gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'"), "gh");
	assert.equal(mergeCommand("glab --repo x mr merge 3"), "glab");
	assert.equal(mergeCommand("gh api -X POST graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'"), "gh");
	assert.equal(mergeCommand("glab api --method POST graphql -f query='mutation { mergeRequestAccept(input: {}) { errors } }'"), "glab");
	assert.equal(mergeCommand("gh api -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }' graphql"), "gh");
	assert.equal(mergeCommand("gh api graphql -F query=@mutation.graphql"), "gh");
	assert.equal(mergeCommand("gh api graphql -F query='@mutation.graphql'"), "gh");
	assert.equal(mergeCommand('gh api graphql -F "query=@mutation.graphql"'), "gh");
	assert.equal(mergeCommand("glab api graphql -F 'query'=@mutation.graphql"), "glab");
	assert.equal(mergeCommand("glab api graphql --input body.json"), "glab");
	assert.equal(mergeCommand("gh api graphql -f query='query { viewer { login } }'"), null);
	assert.equal(mergeCommand("gh pr list --search merge"), "gh");
});

test("decisions follow the mode table", () => {
	const personal = "git@github.com:example-owner/harness.git";
	const company = "ssh://git@gitlab.example:2222/group/proj.git";
	const d = (command, state, origin = personal, allow = ALLOW) => decide({ command, state, origin, now: NOW, allow }).action;
	assert.equal(d("ls", {}), "pass");
	assert.equal(d("gh pr merge 1", {}), "deny");
	assert.equal(d("gh pr merge 1", { mode: "full-send" }), "allow");
	assert.equal(d("gh pr merge 1 --admin", { mode: "full-send" }), "deny");
	assert.equal(d("gh pr merge 1 -R other/repo", { mode: "full-send" }), "deny");
	assert.equal(d("gh pr merge 1 --repo example-owner/x", { mode: "full-send" }, company), "allow");
	assert.equal(d("glab mr merge 1", { mode: "full-send" }, company), "deny");
	assert.equal(d("glab mr merge 1", { mode: "full-send" }, "https://gitlab.example/team/allowed.git"), "allow");
	assert.equal(d("glab mr merge 1 -R team/allowed", { mode: "full-send" }, "https://gitlab.example/team/allowed.git"), "allow");
	assert.equal(d("glab mr merge 1 -R team/other", { mode: "full-send" }, "https://gitlab.example/team/allowed.git"), "deny");
	assert.equal(d("gh pr merge 1", { mode: "full-send" }, personal, []), "deny");
	assert.equal(d("gh api --hostname other.example -X PUT repos/example-owner/x/pulls/7/merge", { mode: "full-send" }), "deny");
	assert.equal(d("glab api --hostname=other.example -X PUT projects/team%2Fallowed/merge_requests/7/merge", { mode: "full-send" }, "https://gitlab.example/team/allowed.git"), "deny");
	assert.equal(d("gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", { mode: "full-send" }), "deny");
	assert.equal(d("gh api -X POST graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", { mode: "full-send" }), "deny");
	assert.equal(d("gh api -X POST graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", {}, personal, []), "deny");
	assert.equal(d("gh api -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }' graphql", { mode: "full-stop" }), "deny");
	assert.equal(d("gh api graphql -F query=@mutation.graphql", { mode: "full-send" }), "deny");
	assert.equal(d("gh api graphql -f query='mutation { disablePullRequestAutoMerge(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", { mode: "full-stop" }), "pass");
	assert.equal(d("glab api -X POST projects/1/merge_requests/7/cancel_merge_when_pipeline_succeeds", { mode: "full-stop" }), "pass");
	assert.equal(d("gh pr merge 1", { mode: "full-send" }, "https://github.com/example-owner-two/x.git"), "deny");
	assert.equal(d("gh pr merge 1", { mode: "full-send" }, "https://github.com/someone/x.git"), "deny");
	assert.equal(d("gh pr merge 1", { mode: "full-stop" }), "deny");
	assert.equal(d("glab mr merge 1", { mode: "full-stop", grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab mr merge 1", { grant: "!1", grant_expires: String(NOW + 60) }, company), "allow");
	assert.equal(d("glab mr merge 1", { grant: "!1", grant_expires: String(NOW - 1) }, company), "deny");
	assert.equal(d("glab mr merge 1 --admin", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("gh pr merge 1 '--admin'", { mode: "full-send" }), "deny");
	assert.equal(d("glab mr merge 2", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab mr merge", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab mr merge 1 && glab mr merge 2", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab api -X PUT projects/group%2Fproj/merge_requests/1/merge", { grant: "!1", grant_expires: String(NOW + 60) }, company), "allow");
	assert.equal(d("glab api -X PUT projects/9/merge_requests/1/merge", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab mr merge 1 -R other/proj", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab mr merge 1 -R group/proj", { grant: "!1", grant_expires: String(NOW + 60) }, company), "allow");
	assert.equal(d("glab mr merge 1 -Rother/proj", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("gh pr merge 1 -Rother/x", { mode: "full-send" }), "deny");
	assert.equal(d("GITLAB_HOST=evil.example glab mr merge 1", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("export GH_HOST=x; gh pr merge 1", { mode: "full-send" }), "deny");
	assert.equal(d("glab mr merge 7 1", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab api -X PUT projects/group%2Fproj/merge_requests/7/merge -f x=1", { grant: "!1", grant_expires: String(NOW + 60) }, company), "deny");
	assert.equal(d("glab mr merge 1 --sha abc --squash", { grant: "!1", grant_expires: String(NOW + 60) }, company), "allow");
	const g = { grant: "!1", grant_expires: String(NOW + 60) };
	assert.equal(d("glab mr merge mybranch 1", g, company), "deny");
	assert.equal(d('glab mr merge "7" 1', g, company), "deny");
	assert.equal(d("glab mr merge mybranch", g, company), "deny");
	assert.equal(d('glab mr merge 1 -m "merge 7 now"', g, company), "allow");
	assert.equal(d("glab mr merge '1' --squash", g, company), "allow");
	assert.equal(d("glab mr merge https://gitlab.example/group/proj/-/merge_requests/1", g, company), "allow");
	assert.equal(d("glab mr merge 1 # 7", g, company), "allow");
	assert.equal(d("glab mr merge 1; eval \"$NEXT\"", g, company), "deny");
	assert.equal(d("glab mr merge 1 -m \"$(cat msg)\"", g, company), "deny");
	assert.equal(d("glab mr merge 1 -m 'a; b | c'", g, company), "allow");
	assert.equal(d("bash -c 'glab mr merge 1'", g, company), "deny");
	assert.equal(d("echo mr merge 1 && glab mr merge 7", g, company), "deny");
	assert.equal(d("glab mr view 7 --output json | grep merge_requests/1 && glab mr merge 7", g, company), "deny");
	assert.equal(d("glab mr merge -sd 1", g, company), "deny");
	assert.equal(d("glab mr merge 1 --unknown-flag 7", g, company), "deny");
	assert.equal(d("glab mr merge 1 < /tmp/x", g, company), "deny");
	assert.equal(d("glab mr merge -d -s 1", g, company), "allow");
	assert.equal(d("glab mr merge -- 1", g, company), "allow");
	assert.equal(d("gh api -X PUT repos/company/project/pulls/7/merge", { mode: "full-send" }), "deny");
	assert.equal(d("gh api -X PUT repos/example-owner/x/pulls/7/merge", { mode: "full-send" }), "allow");
	assert.equal(d("gh pr merge https://github.com/company/project/pull/7 --repo example-owner/demo", { mode: "full-send" }), "deny");
	assert.equal(d("glab mr merge 7 -R group/proj", { grant: "!7", grant_expires: String(NOW + 60) }, "https://gitlab.example/department/group/proj.git"), "deny");
	assert.equal(d("GH_REPO=other/x gh pr merge 1", { mode: "full-send" }), "deny");
	assert.equal(d("cd /elsewhere && gh pr merge 1", { mode: "full-send" }), "deny");
	assert.equal(d("gh pr merge https://github.com/other/x/pull/1", { mode: "full-send" }), "deny");
	assert.equal(d("gh pr merge https://github.com/example-owner/x/pull/1", { mode: "full-send" }), "allow");
});

test("payloads and outputs follow each CLI's hook protocol", () => {
	assert.deepEqual(readPayload("claude", { tool_name: "Bash", tool_input: { command: "gh pr merge" }, cwd: "/r" }), { command: "gh pr merge", cwd: "/r" });
	assert.equal(readPayload("codex", { tool_input: { command: ["bash", "-lc", "glab mr merge 2"] }, cwd: "/r" }).command, "bash -lc glab mr merge 2");
	assert.deepEqual(readPayload("agy", { toolCall: { name: "run_command", args: { CommandLine: "glab mr merge 2", Cwd: "/w" } } }), { command: "glab mr merge 2", cwd: "/w" });
	const deny = { action: "deny", reason: "r" };
	assert.equal(JSON.parse(render("claude", deny).stdout).hookSpecificOutput.permissionDecision, "deny");
	assert.deepEqual(JSON.parse(render("agy", deny).stdout), { decision: "deny", reason: "r" });
	assert.equal(render("agy", { action: "allow" }).stdout, "");
	assert.equal(render("claude", { action: "pass" }).stdout, "");
});

test("harness-mode degrades full-send outside the allowlist", () => {
	const company = repo("company", "ssh://git@gitlab.example:2222/group/proj.git");
	const set = mode(company, "set", "full-send");
	assert.equal(set.status, 0);
	assert.ok(set.stdout.includes("mode=full-stop"));
	assert.equal(parseState(mode(company, "show").stdout).mode, "full-stop");
	const personal = repo("personal", "https://github.com/example-owner/demo.git");
	const missing = modeWith(personal, { XDG_CONFIG_HOME: join(root, "no-config") }, "set", "full-send");
	assert.ok(missing.stdout.includes("runs as full-stop"));
	assert.equal(missing.stdout.trim().endsWith("mode=full-stop"), true);
	assert.equal(mode(personal, "set", "full-send").stdout.trim(), "mode=full-send");
	assert.ok(mode(personal, "allowlist").stdout.includes("allowed: github.com/example-owner/demo"));
	const gitlab = repo("gitlab-allowed", "git@gitlab.example:team/allowed.git");
	assert.equal(mode(gitlab, "set", "full-send").stdout.trim(), "mode=full-send");
	assert.equal(mode(personal, "set", "yolo").status, 2);
	assert.equal(mode(personal, "clear").stdout.trim(), "mode=none");
	assert.equal(existsSync(join(personal, ".git", "harness-mode")), false);
});

test("end to end: the hook reads the mode file and consumes a one-shot grant", () => {
	const dir = repo("e2e", "ssh://git@gitlab.example:2222/group/proj.git");
	const payload = { tool_name: "Bash", tool_input: { command: "glab mr merge 7 --sha abc" }, cwd: dir };
	const denied = hook("claude", payload, root);
	assert.equal(denied.status, 0);
	assert.equal(JSON.parse(denied.stdout).hookSpecificOutput.permissionDecision, "deny");
	assert.equal(mode(dir, "set", "full-send").status, 0);
	assert.ok(JSON.parse(hook("claude", payload, root).stdout).hookSpecificOutput.permissionDecisionReason.includes("full-stop"));
	mode(dir, "clear");
	assert.equal(mode(dir, "allow-merge", "!7").status, 0);
	const allowed = hook("codex", payload, root);
	assert.equal(allowed.status, 0);
	assert.equal(allowed.stdout, "");
	const stateFile = join(dir, ".git", "harness-mode");
	assert.equal(existsSync(stateFile) && readFileSync(stateFile, "utf8").includes("grant="), false);
	assert.equal(JSON.parse(hook("claude", payload, root).stdout).hookSpecificOutput.permissionDecision, "deny");
	const agy = hook("agy", { toolCall: { name: "run_command", args: { CommandLine: "glab mr merge 7", Cwd: dir } } }, root);
	assert.equal(JSON.parse(agy.stdout).decision, "deny");
	assert.equal(hook("claude", { tool_name: "Bash", tool_input: { command: "ls" }, cwd: dir }, root).stdout, "");
});

test("an unparsable payload naming a merge fails closed even where full-send is set", () => {
	const dir = repo("unparsable", "https://github.com/example-owner/demo.git");
	assert.equal(mode(dir, "set", "full-send").status, 0);
	const run = spawnSync("node", [GUARD, "--format", "claude"], { cwd: dir, input: "not json gh pr merge 1", encoding: "utf8" });
	assert.equal(JSON.parse(run.stdout).hookSpecificOutput.permissionDecision, "deny");
	assert.equal(spawnSync("node", [GUARD, "--format", "claude"], { cwd: dir, input: "not json", encoding: "utf8" }).stdout, "");
});

test("a malformed encoded project path denies instead of crashing the hook", () => {
	const dir = repo("malformed", "ssh://git@gitlab.example:2222/group/proj.git");
	assert.equal(mode(dir, "allow-merge", "!1").status, 0);
	const run = hook("agy", { toolCall: { name: "run_command", args: { CommandLine: "glab api -X PUT projects/%E0%A4/merge_requests/1/merge", Cwd: dir } } }, root);
	assert.equal(run.status, 0);
	assert.equal(JSON.parse(run.stdout).decision, "deny");
});

test("repository refs normalize across URL, SSH, and flag forms", () => {
	assert.equal(repoKey("ssh://git@gitlab.example:2222/group/proj.git"), "gitlab.example/group/proj");
	assert.equal(repoKey("git@github.com:example-owner/x.git"), "github.com/example-owner/x");
	assert.equal(targetRepo("gh pr merge https://github.com/example-owner/x/pull/3"), "github.com/example-owner/x");
	assert.equal(targetRepo("glab mr merge https://gitlab.example/a/b/c/-/merge_requests/4"), "gitlab.example/a/b/c");
	assert.equal(targetRepo("glab mr merge 4"), null);
	assert.equal(targetRepo("glab api -X PUT projects/%E0%A4/merge_requests/1/merge"), "?");
	assert.equal(sameRepo("group/proj", "ssh://git@gitlab.example:2222/group/proj.git"), true);
	assert.equal(sameRepo("other/proj", "ssh://git@gitlab.example:2222/group/proj.git"), false);
	assert.equal(sameRepo("group/proj", "https://gitlab.example/department/group/proj.git"), false);
	assert.equal(sameRepo("gitlab.example/department/group/proj", "https://gitlab.example/department/group/proj.git"), true);
	assert.equal(targetRepo("gh pr merge https://github.com/company/p/pull/7 --repo example-owner/demo"), "conflict");
	assert.equal(targetRepo("gh pr merge https://github.com/example-owner/demo/pull/7 --repo example-owner/demo"), "github.com/example-owner/demo");
});

test("the allowlist reads exact repositories and owner prefixes the way harness-mode does", () => {
	assert.deepEqual(ALLOW, ["github.com/example-owner/*", "gitlab.example/team/allowed"]);
	assert.equal(allowedRepo("github.com/example-owner/demo", ALLOW), true);
	assert.equal(allowedRepo("github.com/example-owner", ALLOW), false);
	assert.equal(allowedRepo("github.com/example-owner-two/demo", ALLOW), false);
	assert.equal(allowedRepo("gitlab.example/team/allowed", ALLOW), true);
	assert.equal(allowedRepo("gitlab.example/team/allowed-two", ALLOW), false);
	assert.equal(allowedRepo(null, ALLOW), false);
	assert.deepEqual(parseAllowlist(""), []);
	assert.equal(mergeRepo(null, "git@github.com:example-owner/x.git", "gh"), "github.com/example-owner/x");
	assert.equal(mergeRepo("other/x", "https://gitlab.example/team/allowed.git", "gh"), "github.com/other/x");
	assert.equal(mergeRepo("other/x", "https://gitlab.example/team/allowed.git", "glab"), null);
	assert.equal(mergeRepo("?", "https://gitlab.example/team/allowed.git", "glab"), null);
	assert.equal(allowlistFile({ XDG_CONFIG_HOME: "/c", HOME: "/h" }), "/c/harness/full-send-repos");
	assert.equal(allowlistFile({ XDG_CONFIG_HOME: "rel", HOME: "/h" }), "/h/.config/harness/full-send-repos");
	for (const [origin, want] of [
		["https://GitHub.com/Example-Owner/Demo.git", "allowed"],
		["ssh://git@gitlab.example:2222/team/allowed.git", "allowed"],
		["git@gitlab.example:team/allowed-two.git", "not allowed"],
	]) {
		const dir = repo(`agree-${want.replace(" ", "-")}-${repoKey(origin).replaceAll("/", "-")}`, origin);
		assert.equal(mode(dir, "allowlist").stdout.startsWith(`${want}:`), true);
		assert.equal(allowedRepo(repoKey(origin), ALLOW), want === "allowed");
	}
});

test("end to end: full-send merges only when the hook finds the repository on the allowlist", () => {
	const dir = repo("e2e-send", "https://github.com/example-owner/demo.git");
	assert.equal(mode(dir, "set", "full-send").stdout.trim(), "mode=full-send");
	const payload = { tool_name: "Bash", tool_input: { command: "gh pr merge 3 --squash" }, cwd: dir };
	assert.equal(hook("claude", payload, root).stdout, "");
	const without = hook("claude", payload, root, { XDG_CONFIG_HOME: join(root, "no-config") });
	assert.equal(JSON.parse(without.stdout).hookSpecificOutput.permissionDecision, "deny");
	mode(dir, "clear");
});

test("every host a merge command names must be the host of the repository it merges", () => {
	const allowed = "https://gitlab.example/team/allowed.git";
	const personal = "git@github.com:example-owner/x.git";
	const send = { mode: "full-send" };
	const g = { grant: "!7", grant_expires: String(NOW + 60) };
	const d = (command, state = send, origin = allowed) => decide({ command, state, origin, now: NOW, allow: ALLOW }).action;
	// The allowlisted repository, named by path, URL, or the origin itself.
	assert.equal(d("glab api -X PUT projects/team%2Fallowed/merge_requests/7/merge"), "allow");
	assert.equal(d("glab api -X PUT https://gitlab.example/api/v4/projects/team%2Fallowed/merge_requests/7/merge"), "allow");
	assert.equal(d("glab mr merge 7 -R gitlab.example/team/allowed"), "allow");
	// The same path on another host, an absolute endpoint, or a lookalike domain.
	assert.equal(d("glab api -X PUT https://other.example/api/v4/projects/team%2Fallowed/merge_requests/7/merge"), "deny");
	assert.equal(d("glab api -X PUT https://gitlab.example.evil.example/api/v4/projects/team%2Fallowed/merge_requests/7/merge"), "deny");
	assert.equal(d("glab api -X PUT https://other.example/api/v4/projects/team%2Fallowed/merge_requests/7/merge", g), "deny");
	assert.equal(d("gh api -X PUT https://ghe.example/api/v3/repos/example-owner/x/pulls/7/merge", send, personal), "deny");
	// Environment that points glab at another host.
	assert.equal(d("GITLAB_URL=https://other.example glab mr merge 7"), "deny");
	assert.equal(d("GITLAB_API_HOST=other.example glab mr merge 7"), "deny");
	// A percent-encoded numeric project id is still an unresolvable id.
	assert.equal(targetRepo("glab api -X PUT projects/%31%32/merge_requests/7/merge"), "?");
	assert.equal(d("glab api -X PUT projects/%31%32/merge_requests/7/merge", g), "deny");
	// URLs inside a merge message or PR body are prose, not targets.
	assert.equal(d('glab mr merge 7 -m "see https://other.example/x"'), "allow");
	assert.equal(d('gh pr merge 7 --body "see https://other.example/x"', send, personal), "allow");
	// gh's -m is --merge and takes no value, so the word after it is still a target.
	assert.equal(d("gh pr merge -m https://ghe.example/example-owner/x/pull/7", send, personal), "deny");
});
