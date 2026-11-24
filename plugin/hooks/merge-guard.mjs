#!/usr/bin/env node
// PreToolUse merge guard for Claude Code, Codex, and Antigravity.
// Blocks `gh pr merge`, `glab mr merge`, and their REST equivalents unless the worktree's
// harness mode allows it (skills/full-send/scripts/harness-mode writes the mode file):
//   full-send  + a repository on the full-send allowlist → allow (never with --admin)
//   full-stop                                            → deny
//   no mode    + an unexpired one-shot grant             → allow once, then the grant is consumed
//   no mode    + an allowlisted repository whose PR/MR has passing CI and a review-loop approval line → allow
//   otherwise                                            → deny
// The allowlist is ${XDG_CONFIG_HOME:-~/.config}/harness/full-send-repos, the file harness-mode reads: one
// `host/path` or `host/owner/*` entry per line. A missing or empty allowlist means full-send never merges.
// It guards against accidental merges; the agent can edit the mode file, so it is not an authorization system.
// Usage: merge-guard.mjs --format claude|codex|agy   (hook JSON on stdin)
import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { isAbsolute, join } from "node:path";
import { fileURLToPath } from "node:url";

// A command word may carry a path prefix or quotes (`/usr/bin/gh`, `"glab"`).
const START = String.raw`(?:^|[\s;&|(\x60]|\$\()(?:[\w./~-]*/)?["']?`;
const END = String.raw`["']?`;
const MERGE_PATTERNS = [
	{ cli: "gh", re: new RegExp(`${START}gh${END}\\s+pr\\s+merge\\b`) },
	{ cli: "glab", re: new RegExp(`${START}glab${END}\\s+mr\\s+merge\\b`) },
	{ cli: "gh", re: new RegExp(`${START}gh${END}\\s+api\\b[^;&|]*/pulls/\\d+/merge\\b`) },
	{ cli: "glab", re: new RegExp(`${START}glab${END}\\s+api\\b[^;&|]*merge_requests/\\d+/merge\\b`) },
	// GraphQL in any argument order. A query read from a file or stdin hides its mutation, so it counts as a merge.
	{ cli: "gh", re: new RegExp(`${START}gh${END}\\s+api\\b(?=[^;&|]*\\bgraphql\\b)(?=[^;&|]*(?:mergePullRequest|enablePullRequestAutoMerge|query["']?=["']?@|--input\\b))`) },
	{ cli: "glab", re: new RegExp(`${START}glab${END}\\s+api\\b(?=[^;&|]*\\bgraphql\\b)(?=[^;&|]*(?:mergeRequestAccept|mergeRequestSetAutoMerge|query["']?=["']?@|--input\\b))`) },
];

// Fallback when the exact patterns miss an unusual spelling: gh or glab plus a standalone merge word counts.
const FUZZY_CLI = /(?:^|[^\w-])["']?(gh|glab)["']?(?:\s|$)/;
const FUZZY_MERGE = /(?:^|\s)["']?merge["']?(?:\s|$)/;

/** Which merge CLI a shell command invokes, or null. Unsure spellings count as a merge. */
export function mergeCommand(command) {
	const text = command.replace(/\\\n/g, " ");
	const hit = MERGE_PATTERNS.find(({ re }) => re.test(text));
	if (hit) return hit.cli;
	return FUZZY_MERGE.test(text) ? (FUZZY_CLI.exec(text)?.[1] ?? null) : null;
}

function mergeCount(command) {
	const text = command.replace(/\\\n/g, " ");
	return MERGE_PATTERNS.reduce((n, { re }) => n + (text.match(new RegExp(re.source, "g"))?.length ?? 0), 0);
}

/** The MR or PR number a merge command names (`merge 12`, `!12`, `#12`, `.../merge_requests/12`, `.../pull/12`). */
// Flags of `gh pr merge` and `glab mr merge`, by whether they take a separate value word. Any other flag,
// a combined short flag (`-sd`), or a redirection makes the target unknown, which a grant never matches.
const FLAGS = {
	gh: {
		value: new Set(["-R", "--repo", "-b", "--body", "-F", "--body-file", "-t", "--subject", "-A", "--author-email", "--match-head-commit"]),
		bool: new Set(["-m", "--merge", "-s", "--squash", "-r", "--rebase", "-d", "--delete-branch", "--auto", "--disable-auto", "--admin"]),
	},
	glab: {
		value: new Set(["-R", "--repo", "-m", "--message", "--sha", "--squash-message"]),
		bool: new Set(["-d", "--remove-source-branch", "-r", "--rebase", "-s", "--squash", "-y", "--yes", "--auto-merge"]),
	},
};

/** Shell words of `text` up to the first unquoted control operator, with quotes removed; null on a redirection. */
export function shellWords(text) {
	const words = [];
	let word = null;
	let quote = null;
	for (let i = 0; i < text.length; i++) {
		const c = text[i];
		if (quote) {
			if (c === quote) quote = null;
			else if (c === "\\" && quote === '"' && i + 1 < text.length) word += text[++i];
			else word += c;
			continue;
		}
		if (c === "'" || c === '"') {
			quote = c;
			word ??= "";
		} else if (c === "\\" && i + 1 < text.length) {
			word = (word ?? "") + text[++i];
		} else if (/\s/.test(c)) {
			if (word !== null) words.push(word);
			word = null;
		} else if (c === "<" || c === ">") {
			return null;
		} else if (";&|)`\n".includes(c) || (c === "#" && word === null)) {
			break;
		} else word = (word ?? "") + c;
	}
	if (word !== null) words.push(word);
	return words;
}

/**
 * The MR or PR number a merge command targets: the REST path of a merge API call, or the single positional
 * argument of the `gh pr merge` / `glab mr merge` invocation (`N`, `!N`, `#N`, or an MR/PR URL). Anything
 * else (a branch name, several positionals, an unknown flag, numbers that disagree) is null.
 */
export function mergeTarget(command) {
	const text = command.replace(/\\\n/g, " ");
	const paths = new Set([...text.matchAll(/(?:merge_requests|pulls?)\/(\d+)/g)].map((m) => m[1]));
	const api = MERGE_PATTERNS.slice(2).some(({ re }) => re.test(text));
	if (api) return paths.size === 1 ? [...paths][0] : null;
	const invocation = [MERGE_PATTERNS[0], MERGE_PATTERNS[1]].map(({ cli, re }) => ({ cli, m: re.exec(text) })).find(({ m }) => m);
	if (!invocation) return null;
	const words = shellWords(text.slice(invocation.m.index + invocation.m[0].length));
	if (!words) return null;
	const flags = FLAGS[invocation.cli];
	const positional = [];
	for (let i = 0; i < words.length; i++) {
		const word = words[i];
		if (word === "--") {
			positional.push(...words.slice(i + 1));
			break;
		}
		if (word.startsWith("-")) {
			const name = word.split("=")[0];
			if (flags.value.has(name)) {
				if (!word.includes("=")) i++;
			} else if (!flags.bool.has(name)) return null;
			continue;
		}
		positional.push(word);
	}
	if (positional.length !== 1) return null;
	const match = /^[!#]?(\d+)$/.exec(positional[0]) ?? /\/(?:-\/merge_requests|pull)\/(\d+)(?:[/?#].*)?$/.exec(positional[0]);
	if (!match) return null;
	return [...paths].every((n) => n === match[1]) ? match[1] : null;
}

export function parseState(text) {
	const state = {};
	for (const line of (text ?? "").split("\n")) {
		const at = line.indexOf("=");
		if (at > 0) state[line.slice(0, at)] = line.slice(at + 1);
	}
	return state;
}

/** `host/path` of a remote URL or `path` of an owner/name ref, without scheme, user, port, quotes, or `.git`. */
export function repoKey(ref) {
	return ref
		.replace(/^["']|["']$/g, "")
		.replace(/^[a-z+]+:\/\/(?:[^@/]+@)?/, "")
		.replace(/^[^@/]+@([^:]+):/, "$1/")
		.replace(/^([^/:]+):\d+\//, "$1/")
		.replace(/\.git$/, "")
		.replace(/\/+$/, "")
		.toLowerCase();
}

/**
 * The repository a merge command names explicitly: -R/--repo flags, MR or PR URLs, and REST paths. Returns
 * null when the command relies on the working directory, "?" when it names a project by numeric id, and
 * "conflict" when its references disagree.
 */
export function targetRepo(command) {
	const refs = new Set();
	for (const m of command.matchAll(/(?:^|\s)(?:-R|--repo)(?:\s+|=)?(\S+)/g)) refs.add(repoKey(m[1]));
	for (const m of command.matchAll(/https?:\/\/([^\s"']+?)\/(?:-\/merge_requests|pull)\/\d+/g)) refs.add(repoKey(m[1]));
	for (const m of command.matchAll(/\brepos\/([^/\s]+\/[^/\s]+)\/pulls\//g)) refs.add(repoKey(m[1]));
	for (const m of command.matchAll(/\bprojects\/([^/\s]+)\/merge_requests\//g)) {
		const key = decodedKey(m[1]);
		refs.add(/^\d+$/.test(key) ? "?" : key);
	}
	// A flag gives owner/name and a URL gives host/owner/name; both naming github.com/<same> is one repository.
	const bare = new Set([...refs].map((ref) => ref.replace(/^github\.com\//, "")));
	if (bare.size === 0) return null;
	if (bare.size > 1) return "conflict";
	return [...refs].sort((x, y) => y.length - x.length)[0];
}

function decodedKey(encoded) {
	try {
		return repoKey(decodeURIComponent(encoded));
	} catch {
		return "?"; // undecodable path: treated like an unresolvable project id, which never matches
	}
}

/** Whether an explicit repository ref names the same repository as the origin URL (full path, host optional). */
export function sameRepo(repo, origin) {
	if (!origin || repo === "?" || repo === "conflict") return false;
	const home = repoKey(origin);
	return repo === home || repo === home.slice(home.indexOf("/") + 1);
}

export function allowlistFile(env = process.env) {
	const config = env.XDG_CONFIG_HOME && isAbsolute(env.XDG_CONFIG_HOME) ? env.XDG_CONFIG_HOME : join(env.HOME || homedir(), ".config");
	return join(config, "harness/full-send-repos");
}

/** Allowlist entries: repository keys, or `<prefix>/*` for every repository under a prefix. */
export function parseAllowlist(text) {
	return (text ?? "")
		.split("\n")
		.map((line) => line.replace(/#.*/, "").replace(/\s+/g, "").toLowerCase())
		.filter(Boolean)
		.map((entry) => (entry.endsWith("/*") ? entry : repoKey(entry)));
}

export function allowedRepo(key, entries) {
	if (!key) return false;
	return entries.some((entry) => (entry.endsWith("/*") ? key.length > entry.length - 1 && key.startsWith(entry.slice(0, -1)) : key === entry));
}

/**
 * The full `host/path` a merge acts on: the explicit reference when it names a host, the origin when the command
 * names none or names the origin's own path, and github.com for another owner/name given to gh. Otherwise null.
 */
export function mergeRepo(repo, origin, cli) {
	if (repo === "?" || repo === "conflict") return null;
	if (!repo) return origin ? repoKey(origin) : null;
	if (repo.split("/")[0].includes(".")) return repo;
	if (sameRepo(repo, origin)) return repoKey(origin);
	return cli === "gh" ? `github.com/${repo}` : null;
}

/** Whether the command chains, substitutes, or evaluates anything outside quotes (`;`, `&`, `|`, `$(`, backticks, eval). */
export function compound(command) {
	const bare = command.replace(/'[^']*'/g, "''").replace(/"(?:[^"\\$`]|\\.)*"/g, '""');
	return /[;&|`\n]|\$\(|(?:^|\s)(?:eval|source|\.)\s|(?:^|\s)(?:bash|sh|zsh)\s+-c\b/.test(bare);
}

function ambiguous(command) {
	// Environment that redirects gh or glab to another repository or host counts as ambiguous too.
	return (
		mergeCount(command) > 1 ||
		/(?:^|[\s;&|])(?:export\s+)?(?:GH_REPO|GH_HOST|GITLAB_HOST|GITLAB_URI|GITLAB_URL|GITLAB_API_HOST|GL_HOST)=|(?:^|[\s;&|])cd\s|git\s+-C\s|(?:^|\s)["']?--hostname\b/.test(command)
	);
}

// Flags whose value is prose (a merge message or PR body), per CLI. gh's -m is --merge and takes no value.
const PROSE_FLAGS = { gh: "-b|--body|-t|--subject", glab: "-m|--message|--squash-message" };

/**
 * Hosts a command names explicitly: URL and scp-style hosts anywhere outside prose flag values, and the dotted
 * first segment of a -R/--repo ref with three or more segments. Any other ref resolves on the CLI's configured host.
 */
export function namedHosts(text, cli) {
	// An unbalanced quote leaves the rest scanned, which only denies more.
	const prose = new RegExp(`(?:^|\\s)(?:${PROSE_FLAGS[cli] ?? "(?!)"})(?:\\s+|=)(?:"(?:[^"\\\\]|\\\\.)*"|'[^']*'|[^\\s"']+)`, "g");
	const command = text.replace(prose, " ");
	const hosts = new Set();
	for (const m of command.matchAll(/[a-z][a-z+.-]*:\/\/(?:[^@/\s"']+@)?([^/:\s"']+)/gi)) hosts.add(m[1].toLowerCase());
	for (const m of command.matchAll(/(?:^|[\s="'])[^@\s"'/:]+@([^:\s"'/]+):/g)) hosts.add(m[1].toLowerCase());
	for (const m of command.matchAll(/(?:^|\s)(?:-R|--repo)(?:\s+|=)?["']?([^\s"'/:]+)\/[^\s"'/]+\/[^\s"']/g))
		if (m[1].includes(".")) hosts.add(m[1].toLowerCase());
	return hosts;
}

/** Whether every host the command names is `host`; a command that names no host passes. */
function onlyHost(command, cli, host) {
	return [...namedHosts(command, cli)].every((named) => named === host);
}

/**
 * The decision for one command. `state` is the parsed mode file, `origin` the
 * worktree's origin URL, `now` seconds since the epoch.
 * Returns { action: "pass" | "allow" | "deny", reason, consumeGrant }.
 */
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

export function decide({ command, state, origin, now, allow = [], gate = null }) {
	const cli = mergeCommand(command);
	if (!cli) return { action: "pass" };
	const mode = state.mode ?? "none";
	const deny = (reason) => ({
		action: "deny",
		reason: `harness merge guard: ${reason} (mode=${mode}). Merging needs passing CI and a review-loop approval line on the PR/MR in a repository on the full-send allowlist, or the person's explicit request for this merge followed by \`harness-mode allow-merge <ref>\`. Report the PR/MR as ready instead.`,
	});
	if (/--admin\b/.test(command)) return deny("--admin bypasses branch protection and is never allowed");
	if (mode === "full-stop") return deny("full-stop never merges");
	if (ambiguous(command)) return deny("merge one MR or PR per command, from the worktree, without GH_REPO, --hostname, cd, or git -C");
	if (compound(command)) return deny("run the merge as a single command, without chaining, substitution, or eval");
	const repo = targetRepo(command);
	if (repo === "conflict") return deny("the command names more than one repository");
	// The allowlisted repository a merge acts on, or a denial.
	const allowlisted = () => {
		// A GraphQL merge names an opaque node id, so its repository cannot be read from the command.
		if (MERGE_PATTERNS.slice(4).some(({ re }) => re.test(command)))
			return { denied: deny("a GraphQL merge does not name its repository; use the CLI or REST merge") };
		const key = mergeRepo(repo, origin, cli);
		// A path-only ref resolves against the origin, so an endpoint URL on another host must not inherit it.
		if (key && !onlyHost(command, cli, key.split("/")[0])) return { denied: deny(`the command names a host other than ${key.split("/")[0]}`) };
		if (allowedRepo(key, allow)) return { key };
		return { denied: deny(`${mode === "full-send" ? "full-send merges" : "merging without a question covers"} only repositories on the allowlist, and ${key ?? "this target"} is not on it`) };
	};
	if (mode === "full-send") {
		const { key, denied } = allowlisted();
		return denied ?? { action: "allow", reason: `full-send in allowlisted ${key}` };
	}
	const expires = Number(state.grant_expires);
	if (state.grant && Number.isFinite(expires) && expires > now) {
		const granted = /(\d+)\D*$/.exec(state.grant)?.[1];
		if (repo && !sameRepo(repo, origin)) return deny("a one-shot grant covers only this worktree's repository");
		if (!onlyHost(command, cli, origin ? repoKey(origin).split("/")[0] : null))
			return deny("a one-shot grant covers only this worktree's repository, and the command names another host");
		if (!granted || mergeTarget(command) !== granted)
			return deny(`the one-shot grant names ${state.grant}; name that MR or PR number in the merge command`);
		return { action: "allow", reason: `one-shot grant for ${state.grant}`, consumeGrant: true };
	}
	if (mode !== "none") return deny("no work mode allows merging");
	const { key, denied } = allowlisted();
	if (denied) return denied;
	if (repo && !sameRepo(repo, origin)) return deny("without a mode, a merge covers only this worktree's repository");
	const target = mergeTarget(command);
	if (!target) return deny("without a mode, name the PR/MR number in the merge command");
	if (!gate) return { ...deny("the PR/MR's CI and review state could not be read"), needsGate: true };
	if (gate.repo !== key) return deny(`the PR/MR number resolves in ${gate.repo ?? "an unknown repository"}, not in ${key}`);
	if (gate.ci !== "pass") return deny(`CI on the PR/MR is ${gate.ci}, not passing`);
	if (!gate.review) return deny("the PR/MR description has no `Reviewed with review-loop: ... Verdict: approved` line");
	return { action: "allow", reason: `passing CI and an approved review in allowlisted ${key}` };
}

/**
 * CI and review state of the PR/MR a merge command targets, read from the platform; null when unreadable. The
 * lookup resolves its repository the way the merge will (the command's own -R, else the CLI's default), and `repo`
 * is the repository the platform answered for, so a fork whose CLI default is its upstream cannot borrow origin.
 */
function readGate(cli, command, dir) {
	const target = mergeTarget(command);
	const named = /(?:^|\s)(?:-R|--repo)(?:\s+|=)?["']?([^\s"']+)/.exec(command)?.[1];
	const where = named ? ["-R", named] : [];
	// Two lookups at most, inside the 10 s the hook is given.
	const run = (file, args) => JSON.parse(execFileSync(file, args, { cwd: dir, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"], timeout: 4_000 }));
	const home = (url, marker) => (typeof url === "string" && url.includes(marker) ? repoKey(url.slice(0, url.indexOf(marker))) : null);
	try {
		if (!target) return null;
		if (cli === "gh") {
			const pr = run("gh", ["pr", "view", target, ...where, "--json", "statusCheckRollup,body,url"]);
			return { ci: ghChecks(pr.statusCheckRollup), review: reviewApproved(pr.body), repo: home(pr.url, "/pull/") };
		}
		const mr = run("glab", ["mr", "view", target, ...where, "--output", "json"]);
		const pipeline = mr.head_pipeline ?? mr.pipeline;
		let parents = [];
		if (pipeline?.sha && pipeline.sha !== mr.sha && /^[0-9a-f]{7,64}$/.test(pipeline.sha) && Number.isInteger(mr.project_id))
			parents = run("glab", ["api", ...where, `projects/${mr.project_id}/repository/commits/${pipeline.sha}`]).parent_ids ?? [];
		return { ci: glabChecks(mr, parents), review: reviewApproved(mr.description), repo: home(mr.web_url, "/-/merge_requests/") };
	} catch {
		return null;
	}
}

/** The shell command and working directory from each CLI's PreToolUse payload. */
export function readPayload(format, payload) {
	if (format === "agy") {
		const args = payload?.toolCall?.args ?? {};
		const command = args.CommandLine ?? args.commandLine ?? "";
		return { command: String(command), cwd: args.Cwd ?? args.cwd ?? payload?.workspacePaths?.[0] };
	}
	const raw = payload?.tool_input?.command ?? payload?.tool_input?.cmd ?? "";
	const command = Array.isArray(raw) ? raw.join(" ") : String(raw);
	return { command, cwd: payload?.tool_input?.workdir ?? payload?.cwd };
}

/** stdout text and exit code for a decision in each CLI's hook protocol. */
export function render(format, decision) {
	if (decision.action !== "deny") return { stdout: "", code: 0 };
	if (format === "agy") return { stdout: JSON.stringify({ decision: "deny", reason: decision.reason }), code: 0 };
	return {
		stdout: JSON.stringify({
			hookSpecificOutput: {
				hookEventName: "PreToolUse",
				permissionDecision: "deny",
				permissionDecisionReason: decision.reason,
			},
		}),
		code: 0,
	};
}

function git(cwd, args) {
	try {
		return execFileSync("git", ["-c", "core.fsmonitor=false", "-C", cwd, ...args], {
			encoding: "utf8",
			stdio: ["ignore", "pipe", "ignore"],
		}).trim();
	} catch {
		return null;
	}
}

function main() {
	const format = process.argv[process.argv.indexOf("--format") + 1];
	if (!["claude", "codex", "agy"].includes(format)) {
		process.stderr.write("usage: merge-guard.mjs --format claude|codex|agy\n");
		process.exit(2);
	}
	let input = "";
	try {
		input = readFileSync(0, "utf8");
	} catch {}
	let payload = null;
	try {
		payload = JSON.parse(input);
	} catch {}
	// A payload that cannot be parsed but names a merge is denied outright, so a schema change fails closed.
	if (!payload && mergeCommand(input)) {
		const out = render(format, { action: "deny", reason: "harness merge guard: unreadable hook payload that names a merge" });
		process.stdout.write(`${out.stdout}\n`);
		process.exit(out.code);
	}
	const { command, cwd } = payload ? readPayload(format, payload) : { command: "", cwd: undefined };
	const dir = cwd || process.cwd();
	const gitDir = mergeCommand(command) ? git(dir, ["rev-parse", "--path-format=absolute", "--git-dir"]) : null;
	const file = gitDir ? join(gitDir, "harness-mode") : null;
	let stateText = "";
	if (file) {
		try {
			stateText = readFileSync(file, "utf8");
		} catch {}
	}
	const state = parseState(stateText);
	let allowText = "";
	if (state.mode !== "full-stop") {
		try {
			allowText = readFileSync(allowlistFile(), "utf8");
		} catch {}
	}
	const facts = {
		command,
		state,
		origin: gitDir ? git(dir, ["remote", "get-url", "origin"]) : null,
		now: Math.floor(Date.now() / 1000),
		allow: parseAllowlist(allowText),
	};
	let decision = decide(facts);
	// Only a merge that every other rule allows reads the platform, so every other denial stays offline.
	if (decision.needsGate) {
		const gate = readGate(mergeCommand(command), command, dir);
		if (gate) decision = decide({ ...facts, gate });
	}
	let final = decision;
	if (decision.consumeGrant && file) {
		// Claim the grant by renaming the mode file; a concurrent hook that loses the rename denies.
		const claim = `${file}.claim-${process.pid}`;
		try {
			renameSync(file, claim);
			const kept = readFileSync(claim, "utf8").split("\n").filter((line) => line && !/^grant(_expires)?=/.test(line));
			if (kept.length) {
				writeFileSync(`${file}.tmp-${process.pid}`, `${kept.join("\n")}\n`);
				renameSync(`${file}.tmp-${process.pid}`, file);
			}
			rmSync(claim, { force: true });
		} catch {
			final = { action: "deny", reason: "harness merge guard: the one-shot grant was already used" };
		}
	}
	const out = render(format, final);
	if (out.stdout) process.stdout.write(`${out.stdout}\n`);
	process.exit(out.code);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
	try {
		main();
	} catch (error) {
		// Fail closed: an unexpected error denies the call instead of depending on each CLI's failure handling.
		const format = process.argv[process.argv.indexOf("--format") + 1];
		const out = render(format === "agy" ? "agy" : "claude", { action: "deny", reason: `harness merge guard: internal error (${error?.message ?? error})` });
		process.stdout.write(`${out.stdout}\n`);
		process.exit(0);
	}
}
