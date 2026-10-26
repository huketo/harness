// Contract tests for plugin/hooks/merge-guard.mjs and skills/full-send/scripts/harness-mode.
// Repositories, HOME, and the allowlist are temporary; nothing reads the real worktree's mode or the user's
// allowlist, and nothing contacts a remote. Owners and hosts are synthetic.
import { afterAll, beforeAll, expect, test } from "bun:test";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
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

const GUARD = join(import.meta.dir, "merge-guard.mjs");
const MODE = join(import.meta.dir, "../../skills/full-send/scripts/harness-mode");
const NOW = 1_800_000_000;
const ALLOW = parseAllowlist("# synthetic allowlist\ngithub.com/example-owner/*\ngitlab.example/team/allowed.git\n");
let root, env;

beforeAll(() => {
	root = mkdtempSync(join(tmpdir(), "merge-guard-test-"));
	const config = join(root, "config");
	mkdirSync(join(config, "harness"), { recursive: true });
	writeFileSync(join(config, "harness/full-send-repos"), "# synthetic allowlist\ngithub.com/example-owner/*\ngitlab.example/team/allowed.git\n");
	env = { ...process.env, HOME: join(root, "home"), XDG_CONFIG_HOME: config, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1" };
});
afterAll(() => rmSync(root, { recursive: true, force: true }));

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
	expect(mergeCommand("gh pr merge 12 --squash")).toBe("gh");
	expect(mergeCommand("cd /x && glab mr merge 5 --sha abc")).toBe("glab");
	expect(mergeCommand("FOO=1 gh pr merge")).toBe("gh");
	expect(mergeCommand("echo $(glab mr merge 3)")).toBe("glab");
	expect(mergeCommand("gh api -X PUT repos/o/r/pulls/7/merge")).toBe("gh");
	expect(mergeCommand("glab api --method PUT projects/1/merge_requests/9/merge")).toBe("glab");
	expect(mergeCommand("glab mr \\\n  merge 4")).toBe("glab");
	expect(mergeCommand("glab mr view 5")).toBeNull();
	expect(mergeCommand("gh pr view 5 --json mergeable")).toBeNull();
	expect(mergeCommand("git merge main")).toBeNull();
	expect(mergeCommand("echo 'mygh pr merge'")).toBeNull();
	expect(mergeCommand("/usr/bin/gh pr merge 3")).toBe("gh");
	expect(mergeCommand('"glab" mr merge 3')).toBe("glab");
	expect(mergeCommand("gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'")).toBe("gh");
	expect(mergeCommand("glab --repo x mr merge 3")).toBe("glab");
	expect(mergeCommand("gh api -X POST graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'")).toBe("gh");
	expect(mergeCommand("glab api --method POST graphql -f query='mutation { mergeRequestAccept(input: {}) { errors } }'")).toBe("glab");
	expect(mergeCommand("gh api -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }' graphql")).toBe("gh");
	expect(mergeCommand("gh api graphql -F query=@mutation.graphql")).toBe("gh");
	expect(mergeCommand("glab api graphql --input body.json")).toBe("glab");
	expect(mergeCommand("gh api graphql -f query='query { viewer { login } }'")).toBeNull();
	expect(mergeCommand("gh pr list --search merge")).toBe("gh");
});

test("decisions follow the mode table", () => {
	const personal = "git@github.com:example-owner/harness.git";
	const company = "ssh://git@gitlab.example:2222/group/proj.git";
	const d = (command, state, origin = personal, allow = ALLOW) => decide({ command, state, origin, now: NOW, allow }).action;
	expect(d("ls", {})).toBe("pass");
	expect(d("gh pr merge 1", {})).toBe("deny");
	expect(d("gh pr merge 1", { mode: "full-send" })).toBe("allow");
	expect(d("gh pr merge 1 --admin", { mode: "full-send" })).toBe("deny");
	expect(d("gh pr merge 1 -R other/repo", { mode: "full-send" })).toBe("deny");
	expect(d("gh pr merge 1 --repo example-owner/x", { mode: "full-send" }, company)).toBe("allow");
	expect(d("glab mr merge 1", { mode: "full-send" }, company)).toBe("deny");
	expect(d("glab mr merge 1", { mode: "full-send" }, "https://gitlab.example/team/allowed.git")).toBe("allow");
	expect(d("glab mr merge 1 -R team/allowed", { mode: "full-send" }, "https://gitlab.example/team/allowed.git")).toBe("allow");
	expect(d("glab mr merge 1 -R team/other", { mode: "full-send" }, "https://gitlab.example/team/allowed.git")).toBe("deny");
	expect(d("gh pr merge 1", { mode: "full-send" }, personal, [])).toBe("deny");
	expect(d("gh api --hostname other.example -X PUT repos/example-owner/x/pulls/7/merge", { mode: "full-send" })).toBe("deny");
	expect(d("glab api --hostname=other.example -X PUT projects/team%2Fallowed/merge_requests/7/merge", { mode: "full-send" }, "https://gitlab.example/team/allowed.git")).toBe("deny");
	expect(d("gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", { mode: "full-send" })).toBe("deny");
	expect(d("gh api -X POST graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", { mode: "full-send" })).toBe("deny");
	expect(d("gh api -X POST graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", {}, personal, [])).toBe("deny");
	expect(d("gh api -f query='mutation { mergePullRequest(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }' graphql", { mode: "full-stop" })).toBe("deny");
	expect(d("gh api graphql -F query=@mutation.graphql", { mode: "full-send" })).toBe("deny");
	expect(d("gh api graphql -f query='mutation { disablePullRequestAutoMerge(input: {pullRequestId: \"PR_x\"}) { clientMutationId } }'", { mode: "full-stop" })).toBe("pass");
	expect(d("glab api -X POST projects/1/merge_requests/7/cancel_merge_when_pipeline_succeeds", { mode: "full-stop" })).toBe("pass");
	expect(d("gh pr merge 1", { mode: "full-send" }, "https://github.com/example-owner-two/x.git")).toBe("deny");
	expect(d("gh pr merge 1", { mode: "full-send" }, "https://github.com/someone/x.git")).toBe("deny");
	expect(d("gh pr merge 1", { mode: "full-stop" })).toBe("deny");
	expect(d("glab mr merge 1", { mode: "full-stop", grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab mr merge 1", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("allow");
	expect(d("glab mr merge 1", { grant: "!1", grant_expires: String(NOW - 1) }, company)).toBe("deny");
	expect(d("glab mr merge 1 --admin", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("gh pr merge 1 '--admin'", { mode: "full-send" })).toBe("deny");
	expect(d("glab mr merge 2", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab mr merge", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab mr merge 1 && glab mr merge 2", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab api -X PUT projects/group%2Fproj/merge_requests/1/merge", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("allow");
	expect(d("glab api -X PUT projects/9/merge_requests/1/merge", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab mr merge 1 -R other/proj", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab mr merge 1 -R group/proj", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("allow");
	expect(d("glab mr merge 1 -Rother/proj", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("gh pr merge 1 -Rother/x", { mode: "full-send" })).toBe("deny");
	expect(d("GITLAB_HOST=evil.example glab mr merge 1", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("export GH_HOST=x; gh pr merge 1", { mode: "full-send" })).toBe("deny");
	expect(d("glab mr merge 7 1", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab api -X PUT projects/group%2Fproj/merge_requests/7/merge -f x=1", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("deny");
	expect(d("glab mr merge 1 --sha abc --squash", { grant: "!1", grant_expires: String(NOW + 60) }, company)).toBe("allow");
	const g = { grant: "!1", grant_expires: String(NOW + 60) };
	expect(d("glab mr merge mybranch 1", g, company)).toBe("deny");
	expect(d('glab mr merge "7" 1', g, company)).toBe("deny");
	expect(d("glab mr merge mybranch", g, company)).toBe("deny");
	expect(d('glab mr merge 1 -m "merge 7 now"', g, company)).toBe("allow");
	expect(d("glab mr merge '1' --squash", g, company)).toBe("allow");
	expect(d("glab mr merge https://gitlab.example/group/proj/-/merge_requests/1", g, company)).toBe("allow");
	expect(d("glab mr merge 1 # 7", g, company)).toBe("allow");
	expect(d("glab mr merge 1; eval \"$NEXT\"", g, company)).toBe("deny");
	expect(d("glab mr merge 1 -m \"$(cat msg)\"", g, company)).toBe("deny");
	expect(d("glab mr merge 1 -m 'a; b | c'", g, company)).toBe("allow");
	expect(d("bash -c 'glab mr merge 1'", g, company)).toBe("deny");
	expect(d("echo mr merge 1 && glab mr merge 7", g, company)).toBe("deny");
	expect(d("glab mr view 7 --output json | grep merge_requests/1 && glab mr merge 7", g, company)).toBe("deny");
	expect(d("glab mr merge -sd 1", g, company)).toBe("deny");
	expect(d("glab mr merge 1 --unknown-flag 7", g, company)).toBe("deny");
	expect(d("glab mr merge 1 < /tmp/x", g, company)).toBe("deny");
	expect(d("glab mr merge -d -s 1", g, company)).toBe("allow");
	expect(d("glab mr merge -- 1", g, company)).toBe("allow");
	expect(d("gh api -X PUT repos/company/project/pulls/7/merge", { mode: "full-send" })).toBe("deny");
	expect(d("gh api -X PUT repos/example-owner/x/pulls/7/merge", { mode: "full-send" })).toBe("allow");
	expect(d("gh pr merge https://github.com/company/project/pull/7 --repo example-owner/demo", { mode: "full-send" })).toBe("deny");
	expect(d("glab mr merge 7 -R group/proj", { grant: "!7", grant_expires: String(NOW + 60) }, "https://gitlab.example/department/group/proj.git")).toBe("deny");
	expect(d("GH_REPO=other/x gh pr merge 1", { mode: "full-send" })).toBe("deny");
	expect(d("cd /elsewhere && gh pr merge 1", { mode: "full-send" })).toBe("deny");
	expect(d("gh pr merge https://github.com/other/x/pull/1", { mode: "full-send" })).toBe("deny");
	expect(d("gh pr merge https://github.com/example-owner/x/pull/1", { mode: "full-send" })).toBe("allow");
});

test("payloads and outputs follow each CLI's hook protocol", () => {
	expect(readPayload("claude", { tool_name: "Bash", tool_input: { command: "gh pr merge" }, cwd: "/r" })).toEqual({ command: "gh pr merge", cwd: "/r" });
	expect(readPayload("codex", { tool_input: { command: ["bash", "-lc", "glab mr merge 2"] }, cwd: "/r" }).command).toBe("bash -lc glab mr merge 2");
	expect(readPayload("agy", { toolCall: { name: "run_command", args: { CommandLine: "glab mr merge 2", Cwd: "/w" } } })).toEqual({ command: "glab mr merge 2", cwd: "/w" });
	const deny = { action: "deny", reason: "r" };
	expect(JSON.parse(render("claude", deny).stdout).hookSpecificOutput.permissionDecision).toBe("deny");
	expect(JSON.parse(render("agy", deny).stdout)).toEqual({ decision: "deny", reason: "r" });
	expect(render("agy", { action: "allow" }).stdout).toBe("");
	expect(render("claude", { action: "pass" }).stdout).toBe("");
});

test("harness-mode degrades full-send outside the allowlist", () => {
	const company = repo("company", "ssh://git@gitlab.example:2222/group/proj.git");
	const set = mode(company, "set", "full-send");
	expect(set.status).toBe(0);
	expect(set.stdout).toContain("mode=full-stop");
	expect(parseState(mode(company, "show").stdout).mode).toBe("full-stop");
	const personal = repo("personal", "https://github.com/example-owner/demo.git");
	const missing = modeWith(personal, { XDG_CONFIG_HOME: join(root, "no-config") }, "set", "full-send");
	expect(missing.stdout).toContain("runs as full-stop");
	expect(missing.stdout.trim().endsWith("mode=full-stop")).toBe(true);
	expect(mode(personal, "set", "full-send").stdout.trim()).toBe("mode=full-send");
	expect(mode(personal, "allowlist").stdout).toContain("allowed: github.com/example-owner/demo");
	const gitlab = repo("gitlab-allowed", "git@gitlab.example:team/allowed.git");
	expect(mode(gitlab, "set", "full-send").stdout.trim()).toBe("mode=full-send");
	expect(mode(personal, "set", "yolo").status).toBe(2);
	expect(mode(personal, "clear").stdout.trim()).toBe("mode=none");
	expect(existsSync(join(personal, ".git", "harness-mode"))).toBe(false);
});

test("end to end: the hook reads the mode file and consumes a one-shot grant", () => {
	const dir = repo("e2e", "ssh://git@gitlab.example:2222/group/proj.git");
	const payload = { tool_name: "Bash", tool_input: { command: "glab mr merge 7 --sha abc" }, cwd: dir };
	const denied = hook("claude", payload, root);
	expect(denied.status).toBe(0);
	expect(JSON.parse(denied.stdout).hookSpecificOutput.permissionDecision).toBe("deny");
	expect(mode(dir, "set", "full-send").status).toBe(0);
	expect(JSON.parse(hook("claude", payload, root).stdout).hookSpecificOutput.permissionDecisionReason).toContain("full-stop");
	mode(dir, "clear");
	expect(mode(dir, "allow-merge", "!7").status).toBe(0);
	const allowed = hook("codex", payload, root);
	expect(allowed.status).toBe(0);
	expect(allowed.stdout).toBe("");
	const stateFile = join(dir, ".git", "harness-mode");
	expect(existsSync(stateFile) && readFileSync(stateFile, "utf8").includes("grant=")).toBe(false);
	expect(JSON.parse(hook("claude", payload, root).stdout).hookSpecificOutput.permissionDecision).toBe("deny");
	const agy = hook("agy", { toolCall: { name: "run_command", args: { CommandLine: "glab mr merge 7", Cwd: dir } } }, root);
	expect(JSON.parse(agy.stdout).decision).toBe("deny");
	expect(hook("claude", { tool_name: "Bash", tool_input: { command: "ls" }, cwd: dir }, root).stdout).toBe("");
});

test("an unparsable payload naming a merge fails closed even where full-send is set", () => {
	const dir = repo("unparsable", "https://github.com/example-owner/demo.git");
	expect(mode(dir, "set", "full-send").status).toBe(0);
	const run = spawnSync("node", [GUARD, "--format", "claude"], { cwd: dir, input: "not json gh pr merge 1", encoding: "utf8" });
	expect(JSON.parse(run.stdout).hookSpecificOutput.permissionDecision).toBe("deny");
	expect(spawnSync("node", [GUARD, "--format", "claude"], { cwd: dir, input: "not json", encoding: "utf8" }).stdout).toBe("");
});

test("a malformed encoded project path denies instead of crashing the hook", () => {
	const dir = repo("malformed", "ssh://git@gitlab.example:2222/group/proj.git");
	expect(mode(dir, "allow-merge", "!1").status).toBe(0);
	const run = hook("agy", { toolCall: { name: "run_command", args: { CommandLine: "glab api -X PUT projects/%E0%A4/merge_requests/1/merge", Cwd: dir } } }, root);
	expect(run.status).toBe(0);
	expect(JSON.parse(run.stdout).decision).toBe("deny");
});

test("repository refs normalize across URL, SSH, and flag forms", () => {
	expect(repoKey("ssh://git@gitlab.example:2222/group/proj.git")).toBe("gitlab.example/group/proj");
	expect(repoKey("git@github.com:example-owner/x.git")).toBe("github.com/example-owner/x");
	expect(targetRepo("gh pr merge https://github.com/example-owner/x/pull/3")).toBe("github.com/example-owner/x");
	expect(targetRepo("glab mr merge https://gitlab.example/a/b/c/-/merge_requests/4")).toBe("gitlab.example/a/b/c");
	expect(targetRepo("glab mr merge 4")).toBeNull();
	expect(targetRepo("glab api -X PUT projects/%E0%A4/merge_requests/1/merge")).toBe("?");
	expect(sameRepo("group/proj", "ssh://git@gitlab.example:2222/group/proj.git")).toBe(true);
	expect(sameRepo("other/proj", "ssh://git@gitlab.example:2222/group/proj.git")).toBe(false);
	expect(sameRepo("group/proj", "https://gitlab.example/department/group/proj.git")).toBe(false);
	expect(sameRepo("gitlab.example/department/group/proj", "https://gitlab.example/department/group/proj.git")).toBe(true);
	expect(targetRepo("gh pr merge https://github.com/company/p/pull/7 --repo example-owner/demo")).toBe("conflict");
	expect(targetRepo("gh pr merge https://github.com/example-owner/demo/pull/7 --repo example-owner/demo")).toBe("github.com/example-owner/demo");
});

test("the allowlist reads exact repositories and owner prefixes the way harness-mode does", () => {
	expect(ALLOW).toEqual(["github.com/example-owner/*", "gitlab.example/team/allowed"]);
	expect(allowedRepo("github.com/example-owner/demo", ALLOW)).toBe(true);
	expect(allowedRepo("github.com/example-owner", ALLOW)).toBe(false);
	expect(allowedRepo("github.com/example-owner-two/demo", ALLOW)).toBe(false);
	expect(allowedRepo("gitlab.example/team/allowed", ALLOW)).toBe(true);
	expect(allowedRepo("gitlab.example/team/allowed-two", ALLOW)).toBe(false);
	expect(allowedRepo(null, ALLOW)).toBe(false);
	expect(parseAllowlist("")).toEqual([]);
	expect(mergeRepo(null, "git@github.com:example-owner/x.git", "gh")).toBe("github.com/example-owner/x");
	expect(mergeRepo("other/x", "https://gitlab.example/team/allowed.git", "gh")).toBe("github.com/other/x");
	expect(mergeRepo("other/x", "https://gitlab.example/team/allowed.git", "glab")).toBeNull();
	expect(mergeRepo("?", "https://gitlab.example/team/allowed.git", "glab")).toBeNull();
	expect(allowlistFile({ XDG_CONFIG_HOME: "/c", HOME: "/h" })).toBe("/c/harness/full-send-repos");
	expect(allowlistFile({ XDG_CONFIG_HOME: "rel", HOME: "/h" })).toBe("/h/.config/harness/full-send-repos");
	for (const [origin, want] of [
		["https://GitHub.com/Example-Owner/Demo.git", "allowed"],
		["ssh://git@gitlab.example:2222/team/allowed.git", "allowed"],
		["git@gitlab.example:team/allowed-two.git", "not allowed"],
	]) {
		const dir = repo(`agree-${want.replace(" ", "-")}-${repoKey(origin).replaceAll("/", "-")}`, origin);
		expect(mode(dir, "allowlist").stdout.startsWith(`${want}:`)).toBe(true);
		expect(allowedRepo(repoKey(origin), ALLOW)).toBe(want === "allowed");
	}
});

test("end to end: full-send merges only when the hook finds the repository on the allowlist", () => {
	const dir = repo("e2e-send", "https://github.com/example-owner/demo.git");
	expect(mode(dir, "set", "full-send").stdout.trim()).toBe("mode=full-send");
	const payload = { tool_name: "Bash", tool_input: { command: "gh pr merge 3 --squash" }, cwd: dir };
	expect(hook("claude", payload, root).stdout).toBe("");
	const without = hook("claude", payload, root, { XDG_CONFIG_HOME: join(root, "no-config") });
	expect(JSON.parse(without.stdout).hookSpecificOutput.permissionDecision).toBe("deny");
	mode(dir, "clear");
});
