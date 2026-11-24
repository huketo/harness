#!/usr/bin/env node
// gated-merge — merge one PR/MR of this worktree's own repository without a work mode, after checking the
// conditions docs/agents/authority.md lists under "Actions that need no question":
//   the origin repository is on the full-send allowlist, the worktree is not in full-stop,
//   CI on the PR/MR's current head passed, and its description carries the review-loop approval line.
// The check and the merge are one program with fixed arguments: the repository is always the origin, the number
// is the one checked, and the merge is pinned to the head commit that was checked, so nothing a shell command
// could reinterpret sits between the check and the merge.
// Usage: gated-merge.mjs <number> [--squash | --merge | --rebase] [--delete-branch] [--dry-run]
// Like the merge guard, this guards against accidental merges; it is not an authorization system.
import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { allowedRepo, allowlistFile, parseAllowlist, parseState, repoKey } from "../../../plugin/hooks/merge-guard.mjs";

/** CI state of a PR from the `statusCheckRollup` field of a PR view: pass, fail, pending, or missing. */
export function ghChecks(rollup) {
	if (!Array.isArray(rollup) || rollup.length === 0) return "missing";
	const states = rollup.map((check) => String(check.conclusion || check.state || check.status || "").toUpperCase());
	if (states.some((state) => ["FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"].includes(state))) return "fail";
	if (!states.every((state) => ["SUCCESS", "SKIPPED", "NEUTRAL"].includes(state))) return "pending";
	return states.includes("SUCCESS") ? "pass" : "missing";
}

/**
 * CI state of an MR from its JSON view: the head pipeline's status, counted only when that pipeline ran on the
 * MR's current head. `parents` are the parent commits of the pipeline's commit, for a merged-results pipeline
 * whose temporary merge commit has the head as a parent.
 */
export function glabChecks(mr, parents = []) {
	const pipeline = mr?.head_pipeline ?? mr?.pipeline;
	const status = pipeline?.status;
	if (!status || !mr.sha) return "missing";
	if (pipeline.sha !== mr.sha && !parents.includes(mr.sha)) return "missing";
	if (status === "success") return "pass";
	return ["failed", "canceled"].includes(status) ? "fail" : "pending";
}

/** Whether a PR/MR description carries the line review-loop writes after an approval. */
export function reviewApproved(body) {
	return /^Reviewed with review-loop: .*Verdict: approved\s*$/m.test(body ?? "");
}

/** `<number> [method] [--delete-branch] [--dry-run]`, or null when anything else is given. */
export function parseArgs(argv) {
	const out = { number: null, method: "squash", deleteBranch: false, dryRun: false };
	let methods = 0;
	for (const arg of argv) {
		if (/^[1-9]\d*$/.test(arg) && out.number === null) out.number = arg;
		else if (["--squash", "--merge", "--rebase"].includes(arg)) {
			out.method = arg.slice(2);
			methods++;
		} else if (arg === "--delete-branch") out.deleteBranch = true;
		else if (arg === "--dry-run") out.dryRun = true;
		else return null;
	}
	return out.number && methods <= 1 ? out : null;
}

/**
 * The refusal for a merge, or null when every condition holds. `view` is what the platform answered for the
 * number: { repo, state, head, ci, review }.
 */
export function refusal({ key, allow, mode, cli, method, view }) {
	if (mode === "full-stop") return "this worktree is in full-stop, which never merges";
	if (!allowedRepo(key, allow)) return `${key ?? "this repository"} is not on the full-send allowlist`;
	// GitLab rebases the source branch before merging, which replaces the head the CI result belongs to.
	if (cli === "glab" && method === "rebase") return "a rebase merge on GitLab replaces the checked head; rebase, let CI pass, then merge";
	if (!view) return "the PR/MR's state could not be read";
	if (view.repo !== key) return `the number resolves in ${view.repo ?? "an unknown repository"}, not in ${key}`;
	if (view.state !== "open") return `the PR/MR is ${view.state ?? "in an unknown state"}, not open`;
	if (!view.head) return "the PR/MR's head commit could not be read";
	if (view.ci !== "pass") return `CI on the PR/MR's head is ${view.ci}, not passing`;
	if (!view.review) return "the description has no `Reviewed with review-loop: ... Verdict: approved` line";
	return null;
}

/** The merge command, pinned to the repository and head commit that were checked. */
export function mergeArgs({ cli, key, number, method, deleteBranch, head }) {
	if (cli === "gh")
		return ["pr", "merge", number, "-R", key, `--${method}`, "--match-head-commit", head, ...(deleteBranch ? ["--delete-branch"] : [])];
	return [
		"mr",
		"merge",
		number,
		"-R",
		key,
		"--sha",
		head,
		"--auto-merge=false",
		"--yes",
		...(method === "squash" ? ["--squash"] : []),
		...(deleteBranch ? ["--remove-source-branch"] : []),
	];
}

function run(file, args, cwd) {
	return execFileSync(file, args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 60_000 });
}

function readView(cli, key, number, cwd) {
	const home = (url, marker) => (typeof url === "string" && url.includes(marker) ? repoKey(url.slice(0, url.indexOf(marker))) : null);
	try {
		if (cli === "gh") {
			const pr = JSON.parse(run("gh", ["pr", "view", number, "-R", key, "--json", "statusCheckRollup,body,url,headRefOid,state"], cwd));
			return {
				repo: home(pr.url, "/pull/"),
				state: String(pr.state ?? "").toLowerCase(),
				head: pr.headRefOid,
				ci: ghChecks(pr.statusCheckRollup),
				review: reviewApproved(pr.body),
			};
		}
		const mr = JSON.parse(run("glab", ["mr", "view", number, "-R", key, "--output", "json"], cwd));
		const pipeline = mr.head_pipeline ?? mr.pipeline;
		let parents = [];
		if (pipeline?.sha && pipeline.sha !== mr.sha && /^[0-9a-f]{7,64}$/.test(pipeline.sha) && Number.isInteger(mr.project_id))
			parents = JSON.parse(run("glab", ["api", "-R", key, `projects/${mr.project_id}/repository/commits/${pipeline.sha}`], cwd)).parent_ids ?? [];
		return {
			repo: home(mr.web_url, "/-/merge_requests/"),
			state: mr.state === "opened" ? "open" : mr.state,
			head: mr.sha,
			ci: glabChecks(mr, parents),
			review: reviewApproved(mr.description),
		};
	} catch {
		return null;
	}
}

function main() {
	const args = parseArgs(process.argv.slice(2));
	if (!args) {
		process.stderr.write("usage: gated-merge.mjs <number> [--squash | --merge | --rebase] [--delete-branch] [--dry-run]\n");
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
	const key = repoKey(origin);
	const cli = key.startsWith("github.com/") ? "gh" : "glab";
	const mode = parseState(read(join(gitDir, "harness-mode"))).mode ?? "none";
	const allow = parseAllowlist(read(allowlistFile()));
	// The cheap refusals come first, so a repository off the allowlist is never looked up.
	let reason = refusal({ key, allow, mode, cli, method: args.method, view: { repo: key, state: "open", head: "-", ci: "pass", review: true } });
	const view = reason ? null : readView(cli, key, args.number, cwd);
	reason ??= refusal({ key, allow, mode, cli, method: args.method, view });
	if (reason) {
		process.stdout.write(`gated-merge: not merged: ${reason}. Report the PR/MR as ready instead, or ask the person for this merge.\n`);
		process.exit(1);
	}
	const command = mergeArgs({ cli, key, ...args, head: view.head });
	if (args.dryRun) {
		process.stdout.write(`gated-merge: would run: ${cli} ${command.join(" ")}\n`);
		return;
	}
	try {
		process.stdout.write(run(cli, command, cwd));
	} catch (error) {
		process.stdout.write(`gated-merge: the merge command failed: ${String(error.stderr || error.message).trim()}\n`);
		process.exit(1);
	}
	process.stdout.write(`gated-merge: merged ${key} #${args.number} at ${view.head} (CI passed, review approved)\n`);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
