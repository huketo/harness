#!/usr/bin/env node
// gated-merge — merge one GitHub PR of this worktree's own repository without a work mode, after checking the
// conditions docs/agents/authority.md lists under "Actions that need no question":
//   the origin repository is on github.com and on the full-send allowlist, the worktree is not in full-stop,
//   CI on the PR's current head passed, and its description carries the review-loop approval line.
// The check and the merge are one program with fixed arguments: the repository is always the origin, the number
// is the one checked, and the merge goes through GitHub's immediate merge endpoint pinned to the head commit that
// was checked, so nothing a shell command could reinterpret sits between the check and the merge.
// GitLab is refused: its server-side rebase, merged-results pipelines, and squash settings need checks this
// script does not make yet, so a GitLab merge stays a separate decision.
// Usage: gated-merge.mjs <number> [--squash | --merge | --rebase] [--dry-run]
// An error answer from the merge call does not say whether GitHub merged: the PR is read once more, and it counts
// as merged only when GitHub reports it merged at the head that was checked.
// It never deletes the head branch: a deletion cannot be pinned to the checked repository and commit the way the
// merge is, so the branch is left to the repository's own setting or to an ordinary `git push --delete`.
// After GitHub confirms the merge it runs sweep-landed.mjs --apply in this worktree, so the local branches and
// worktrees of landed work do not wait for someone to remember them. The merge already stands by then: a sweep
// that fails is reported and leaves the exit status 0.
// Like the merge guard, this guards against accidental merges; it is not an authorization system.
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { allowedRepo, allowlistFile, parseAllowlist, parseState, repoKey } from "../../../plugin/hooks/merge-guard.mjs";

const HOST = "github.com";

/** CI state of a PR from the `statusCheckRollup` field of a PR view: pass, fail, pending, or missing. */
export function ghChecks(rollup) {
	if (!Array.isArray(rollup) || rollup.length === 0) return "missing";
	const states = rollup.map((check) => String(check.conclusion || check.state || check.status || "").toUpperCase());
	if (states.some((state) => ["FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"].includes(state))) return "fail";
	if (!states.every((state) => ["SUCCESS", "SKIPPED", "NEUTRAL"].includes(state))) return "pending";
	return states.includes("SUCCESS") ? "pass" : "missing";
}

/** Whether a PR description carries the line review-loop writes after an approval. */
export function reviewApproved(body) {
	return /^Reviewed with review-loop: .*Verdict: approved\s*$/m.test(body ?? "");
}

/** `<number> [method] [--dry-run]`, or null when anything else is given. */
export function parseArgs(argv) {
	const out = { number: null, method: "squash", dryRun: false };
	let methods = 0;
	for (const arg of argv) {
		if (/^[1-9]\d{0,8}$/.test(arg) && out.number === null) out.number = arg;
		else if (["--squash", "--merge", "--rebase"].includes(arg)) {
			out.method = arg.slice(2);
			methods++;
		} else if (arg === "--dry-run") out.dryRun = true;
		else return null;
	}
	return out.number && methods <= 1 ? out : null;
}

/** The refusal decided from this machine alone, before any platform call, or null. */
export function localRefusal({ key, allow, mode }) {
	if (mode === "full-stop") return "this worktree is in full-stop, which never merges";
	if (!key || key.split("/")[0] !== HOST || key.split("/").length !== 3) return `${key ?? "this repository"} is not a github.com repository, and only GitHub PRs merge without a question`;
	if (!allowedRepo(key, allow)) return `${key} is not on the full-send allowlist`;
	return null;
}

/** The refusal for what GitHub answered about the number, or null when every condition holds. */
export function viewRefusal({ key, number, view }) {
	if (!view) return "the PR's state could not be read";
	if (String(view.number) !== number) return `GitHub answered for #${view.number ?? "?"}, not #${number}`;
	if (view.repo !== key) return `the number resolves in ${view.repo ?? "an unknown repository"}, not in ${key}`;
	if (view.state !== "open") return `the PR is ${view.state || "in an unknown state"}, not open`;
	if (!/^[0-9a-f]{40,64}$/.test(view.head ?? "")) return "the PR's head commit could not be read";
	if (view.ci !== "pass") return `CI on the PR's head is ${view.ci}, not passing`;
	if (!view.review) return "the description has no `Reviewed with review-loop: ... Verdict: approved` line";
	return null;
}

/** The merge commit when a second read shows this PR merged at the head that was checked, or null. */
export function landedAnyway({ key, number, head, view }) {
	const same = view && String(view.number) === number && view.repo === key && view.state === "merged" && view.head === head;
	return same && /^[0-9a-f]{40,64}$/.test(view.merge ?? "") ? view.merge : null;
}

/** The immediate merge call: GitHub merges the checked head now or fails; it never queues or schedules. */
export function mergeArgs({ key, number, method, head }) {
	const path = key.slice(HOST.length + 1);
	return ["api", "--hostname", HOST, "-X", "PUT", `repos/${path}/pulls/${number}/merge`, "-f", `sha=${head}`, "-f", `merge_method=${method}`];
}

/** `host/owner/repo` of a PR URL whose whole path is `/<owner>/<repo>/pull/<number>`, or null. */
export function prRepo(url, number) {
	let parsed;
	try {
		parsed = new URL(url);
	} catch {
		return null;
	}
	const route = /^\/([^/]+)\/([^/]+)\/pull\/(\d+)$/.exec(parsed.pathname);
	return route && route[3] === String(number) ? `${parsed.host}/${route[1]}/${route[2]}`.toLowerCase() : null;
}

function run(file, args, cwd) {
	return execFileSync(file, args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 60_000 });
}

function readView(key, number, cwd) {
	try {
		const fields = "number,url,state,headRefOid,body,statusCheckRollup,mergeCommit";
		const pr = JSON.parse(run("gh", ["pr", "view", number, "-R", key, "--json", fields], cwd));
		return {
			number: pr.number,
			repo: prRepo(pr.url, pr.number),
			state: String(pr.state ?? "").toLowerCase(),
			head: pr.headRefOid,
			ci: ghChecks(pr.statusCheckRollup),
			review: reviewApproved(pr.body),
			merge: pr.mergeCommit?.oid,
		};
	} catch {
		return null;
	}
}

function main() {
	const args = parseArgs(process.argv.slice(2));
	if (!args) {
		process.stderr.write("usage: gated-merge.mjs <number> [--squash | --merge | --rebase] [--dry-run]\n");
		process.exit(2);
	}
	const cwd = process.cwd();
	const git = (argv) => run("git", ["-c", "core.fsmonitor=false", ...argv], cwd).trim();
	let origin, gitDir;
	try {
		gitDir = git(["rev-parse", "--path-format=absolute", "--git-dir"]);
		origin = git(["remote", "get-url", "origin"]);
	} catch {
		process.stderr.write("gated-merge: not inside a git worktree with an origin remote\n");
		process.exit(2);
	}
	const read = (file) => {
		try {
			return readFileSync(file, "utf8");
		} catch {
			return "";
		}
	};
	const refuse = (reason) => {
		process.stdout.write(`gated-merge: not merged: ${reason}. Report the PR as ready instead, or ask the person for this merge.\n`);
		process.exit(1);
	};
	const key = repoKey(origin);
	const local = localRefusal({ key, allow: parseAllowlist(read(allowlistFile())), mode: parseState(read(join(gitDir, "harness-mode"))).mode ?? "none" });
	if (local) refuse(local);
	const view = readView(key, args.number, cwd);
	const remote = viewRefusal({ key, number: args.number, view });
	if (remote) refuse(remote);
	const command = mergeArgs({ key, number: args.number, method: args.method, head: view.head });
	if (args.dryRun) {
		process.stdout.write(`gated-merge: would run: gh ${command.join(" ")}\n`);
		return;
	}
	let merged = null;
	try {
		merged = JSON.parse(run("gh", command, cwd));
	} catch (error) {
		const sha = landedAnyway({ key, number: args.number, head: view.head, view: readView(key, args.number, cwd) });
		if (!sha) refuse(`GitHub did not merge it now (${String(error.stderr || error.message).trim().split("\n")[0]})`);
		merged = { merged: true, sha };
	}
	if (merged?.merged !== true) refuse("GitHub did not confirm the merge");
	process.stdout.write(`gated-merge: merged ${key} #${args.number} at ${view.head} as ${merged.sha} (CI passed, review approved)\n`);
	const sweeper = fileURLToPath(new URL("./sweep-landed.mjs", import.meta.url));
	const sweep = spawnSync(process.execPath, [sweeper, "--apply"], { cwd, encoding: "utf8", timeout: 300_000 });
	process.stdout.write(`${sweep.stdout ?? ""}${sweep.stderr ?? ""}`);
	if (sweep.status !== 0) process.stdout.write(`gated-merge: the merge stands, but the sweep of landed branches did not finish; retry it with: node '${sweeper.replaceAll("'", "'\\''")}' --apply\n`);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
