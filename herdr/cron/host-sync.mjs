#!/usr/bin/env bun
import { spawnSync } from "node:child_process";
import {
	lstat,
	mkdir,
	mkdtemp,
	readFile,
	realpath,
	rm,
	writeFile,
} from "node:fs/promises";
import {
	basename,
	dirname,
	isAbsolute,
	join,
	relative,
	resolve,
	sep,
} from "node:path";
import { parseArgs } from "node:util";

const ALLOWED = new Set([
	"omp/config.snapshot.yml",
	"agy/settings.snapshot.json",
	"herdr/cron/jobs.snapshot.yaml",
	"third-party/skills.lock.json",
	"herdr/plugins.manifest.json",
	"README.md",
	"docs/FACTS.md",
	"docs/REPO.md",
]);

function git(repo, args, allowFailure = false) {
	const env = {
		...process.env,
		GIT_OPTIONAL_LOCKS: "0",
		GIT_TERMINAL_PROMPT: "0",
	};
	// The explicit repository argument owns Git routing, not the caller's index/worktree overrides.
	for (const key of Object.keys(env)) {
		if (
			/^GIT_(?:DIR|COMMON_DIR|WORK_TREE|INDEX_FILE|OBJECT_DIRECTORY|ALTERNATE_OBJECT_DIRECTORIES|NAMESPACE|CONFIG_PARAMETERS|CONFIG_COUNT|CONFIG_KEY_\d+|CONFIG_VALUE_\d+)$/.test(
				key,
			)
		)
			delete env[key];
	}
	const result = spawnSync("git", args, {
		cwd: repo,
		encoding: "utf8",
		env,
		timeout: 120_000,
		maxBuffer: 8 * 1024 * 1024,
	});
	if (result.error || (!allowFailure && result.status !== 0)) {
		throw new Error(
			`git ${args[0]} failed (${result.error?.code ?? result.status})`,
		);
	}
	return result;
}

async function exists(path) {
	try {
		return await lstat(path);
	} catch (error) {
		if (error.code === "ENOENT") return null;
		throw error;
	}
}

async function rootState(repo, expectedHead) {
	const top = git(repo, ["rev-parse", "--show-toplevel"], true);
	if (top.status !== 0 || resolve(top.stdout.trim()) !== repo)
		return "not_repository_root";
	const branch = git(
		repo,
		["symbolic-ref", "--quiet", "--short", "HEAD"],
		true,
	);
	if (branch.stdout.trim() !== "main") return "not_main";
	for (const name of [
		"MERGE_HEAD",
		"REBASE_HEAD",
		"CHERRY_PICK_HEAD",
		"REVERT_HEAD",
		"rebase-merge",
		"rebase-apply",
		"sequencer",
		"index.lock",
	]) {
		const path = git(repo, ["rev-parse", "--git-path", name]).stdout.trim();
		if (await exists(resolve(repo, path))) return "git_operation_in_progress";
	}
	if (
		git(repo, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
			.stdout
	)
		return "dirty";
	if (
		expectedHead &&
		git(repo, ["rev-parse", "HEAD"]).stdout.trim() !== expectedHead
	)
		return "head_changed";
	return null;
}

async function regularPath(workspace, path, allowMissing = false) {
	let current = workspace;
	const parts = path.split("/");
	for (let index = 0; index < parts.length; index++) {
		current = join(current, parts[index]);
		const stat = await exists(current);
		if (!stat) return allowMissing;
		if (stat.isSymbolicLink()) return false;
		if (index < parts.length - 1 && !stat.isDirectory()) return false;
		if (index === parts.length - 1 && !stat.isFile()) return false;
	}
	return true;
}

async function canonicalDestination(path) {
	const suffix = [];
	while (!(await exists(path))) {
		suffix.unshift(basename(path));
		path = dirname(path);
	}
	return join(await realpath(path), ...suffix);
}

function remoteHead(workspace) {
	return git(workspace, [
		"ls-remote",
		"--exit-code",
		"origin",
		"refs/heads/main",
	]).stdout.split(/\s+/)[0];
}

export async function prepare({ repo, stateRoot }) {
	repo = await realpath(repo);
	const reason = await rootState(repo);
	if (reason) return { status: "skipped", reason };
	const startHead = git(repo, ["rev-parse", "HEAD"]).stdout.trim();
	const remote = git(repo, ["remote", "get-url", "origin"]).stdout.trim();
	stateRoot = await canonicalDestination(
		resolve(stateRoot ?? join(repo, "var", "host-sync")),
	);
	const inside = relative(repo, stateRoot);
	if (
		inside !== ".." &&
		!inside.startsWith(`..${sep}`) &&
		!isAbsolute(inside) &&
		git(repo, ["check-ignore", "--quiet", "--", join(stateRoot, "probe")], true)
			.status !== 0
	) {
		return { status: "skipped", reason: "state_root_not_ignored" };
	}
	await mkdir(stateRoot, { recursive: true, mode: 0o700 });
	const session = await mkdtemp(join(stateRoot, "run-"));
	const workspace = join(session, "workspace");
	try {
		// Clone the remote, never checkout/rebase/stash the user's working tree.
		git(repo, ["clone", "--no-checkout", "--", remote, workspace]);
		git(workspace, ["fetch", "--no-tags", "origin", "main"]);
		const base = git(workspace, ["rev-parse", "FETCH_HEAD"]).stdout.trim();
		if (
			git(workspace, ["merge-base", "--is-ancestor", startHead, base], true)
				.status !== 0
		) {
			await rm(session, { recursive: true });
			return { status: "skipped", reason: "unpublished_or_diverged_head" };
		}
		git(workspace, ["config", "core.worktree", workspace]);
		git(workspace, ["checkout", "--detach", base]);
		for (const key of [
			"user.name",
			"user.email",
			"user.signingkey",
			"commit.gpgsign",
			"gpg.format",
			"gpg.program",
			"gpg.ssh.program",
		]) {
			const value = git(repo, ["config", "--get", key], true).stdout.trim();
			if (value) git(workspace, ["config", key, value]);
		}
		for (const path of ALLOWED) {
			if (!(await regularPath(workspace, path, true)))
				throw new Error(`Unsafe snapshot destination: ${path}`);
		}
		const changed = await rootState(repo, startHead);
		if (changed) {
			await rm(session, { recursive: true });
			return { status: "skipped", reason: changed };
		}
		await writeFile(
			join(session, "manifest.json"),
			JSON.stringify({
				version: 1,
				status: "prepared",
				repo,
				workspace,
				startHead,
				base,
				remote,
			}),
			{ mode: 0o600 },
		);
		return { status: "ready", session, workspace, base };
	} catch (error) {
		await rm(session, { recursive: true, force: true });
		throw error;
	}
}

function sensitiveKey(key) {
	const normalized = key
		.replace(/([a-z0-9])([A-Z])/g, "$1_$2")
		.replace(/-/g, "_");
	return /(?:^|_)(?:api_key|token|access_token|refresh_token|password|passwd|secret|client_secret|private_key|authorization|secret_access_key)$/i.test(
		normalized,
	);
}

function secretIn(value, key = "") {
	if (typeof value === "string") {
		const placeholder =
			/^(?:\$\{[A-Z_][A-Z0-9_]*\}|\$[A-Z_][A-Z0-9_]*|<[^<>]+>)$/.test(value);
		return (
			(sensitiveKey(key) && value.length > 0 && !placeholder) ||
			/-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|\bglpat-[A-Za-z0-9_-]{20,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}/.test(
				value,
			)
		);
	}
	if (Array.isArray(value)) {
		return value.some((item, index) => {
			const flag =
				typeof item === "string" ? item.match(/^--?([\w-]+)(?:=(.*))?$/) : null;
			return (
				secretIn(item, key) ||
				(flag &&
					sensitiveKey(flag[1]) &&
					secretIn(flag[2] ?? value[index + 1], flag[1]))
			);
		});
	}
	if (value && typeof value === "object")
		return Object.entries(value).some(([name, item]) => secretIn(item, name));
	return false;
}

async function inspectChanges(workspace) {
	const paths = [
		...new Set(
			[
				...git(workspace, ["diff", "--name-only", "-z", "HEAD"]).stdout.split(
					"\0",
				),
				...git(workspace, [
					"ls-files",
					"--others",
					"--exclude-standard",
					"-z",
				]).stdout.split("\0"),
			].filter(Boolean),
		),
	].sort();
	for (const path of paths) {
		if (!ALLOWED.has(path)) return { reason: `unapproved_path:${path}` };
		if (!(await regularPath(workspace, path)))
			return { reason: `non_regular_or_deleted:${path}` };
		const bytes = await readFile(join(workspace, path));
		if (bytes.length === 0 || bytes.length > 2 * 1024 * 1024)
			return { reason: `invalid_size:${path}` };
		try {
			const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
			const parsed = path.endsWith(".json")
				? JSON.parse(text)
				: /\.ya?ml$/.test(path)
					? Bun.YAML.parse(text)
					: text;
			if (secretIn(text) || secretIn(parsed))
				return { reason: `possible_secret:${path}` };
		} catch {
			return { reason: `invalid_format:${path}` };
		}
	}
	return { paths };
}

export async function finalize({ session, push = false, message }) {
	session = await realpath(session);
	const manifestPath = join(session, "manifest.json");
	const state = JSON.parse(await readFile(manifestPath, "utf8"));
	if (
		state.version !== 1 ||
		state.status !== "prepared" ||
		state.workspace !== join(session, "workspace")
	)
		return { status: "blocked", reason: "invalid_session", session };
	const blocked = async (reason) => {
		await writeFile(
			manifestPath,
			JSON.stringify({ ...state, status: "blocked", reason }),
		);
		return { status: "blocked", reason, session };
	};
	const { repo, workspace, startHead, base, remote } = state;
	const reason = await rootState(repo, startHead);
	if (reason) return blocked(reason);
	if (git(workspace, ["rev-parse", "HEAD"]).stdout.trim() !== base)
		return blocked("candidate_head_changed");
	if (git(workspace, ["diff", "--cached", "--name-only", "-z"]).stdout)
		return blocked("candidate_index_not_empty");
	if (
		git(workspace, ["remote", "get-url", "origin"]).stdout.trim() !== remote ||
		git(repo, ["remote", "get-url", "origin"]).stdout.trim() !== remote
	)
		return blocked("origin_changed");
	const changes = await inspectChanges(workspace);
	if (changes.reason) return blocked(changes.reason);
	if (changes.paths.length === 0) {
		await rm(workspace, { recursive: true });
		await writeFile(manifestPath, JSON.stringify({ ...state, status: "noop" }));
		return { status: "noop" };
	}
	if (remoteHead(workspace) !== base) return blocked("remote_advanced");
	if (!message?.trim()) return blocked("missing_commit_message");
	if (secretIn(message)) return blocked("possible_secret:commit_message");
	try {
		git(workspace, ["add", "--", ...changes.paths]);
		git(workspace, ["commit", "-m", message]);
	} catch {
		return blocked("commit_failed");
	}
	const commit = git(workspace, ["rev-parse", "HEAD"]).stdout.trim();
	state.commit = commit;
	const committed = git(workspace, ["diff", "--name-only", "-z", base, commit])
		.stdout.split("\0")
		.filter(Boolean)
		.sort();
	if (
		JSON.stringify(committed) !== JSON.stringify(changes.paths) ||
		git(workspace, ["status", "--porcelain=v1", "--untracked-files=all"]).stdout
	)
		return blocked("candidate_changed_during_commit");
	const changed = await rootState(repo, startHead);
	if (changed) return blocked(changed);
	if (remoteHead(workspace) !== base) return blocked("remote_advanced");
	if (push) {
		try {
			git(workspace, ["push", "origin", `${commit}:refs/heads/main`]);
		} catch {
			return blocked("push_failed");
		}
	}
	await writeFile(
		manifestPath,
		JSON.stringify({
			...state,
			status: push ? "published" : "verified",
			commit,
			paths: committed,
		}),
	);
	if (push) await rm(workspace, { recursive: true });
	return {
		status: push ? "published" : "verified",
		commit,
		paths: committed,
		...(push ? {} : { workspace }),
	};
}

if (import.meta.main) {
	try {
		const { positionals, values } = parseArgs({
			args: process.argv.slice(2),
			allowPositionals: true,
			options: {
				repo: { type: "string" },
				"state-root": { type: "string" },
				session: { type: "string" },
				"message-file": { type: "string" },
				push: { type: "boolean", default: false },
			},
		});
		let result;
		if (
			positionals.length === 1 &&
			positionals[0] === "prepare" &&
			values.repo
		) {
			result = await prepare({
				repo: values.repo,
				stateRoot: values["state-root"],
			});
		} else if (
			positionals.length === 1 &&
			positionals[0] === "finalize" &&
			values.session &&
			values["message-file"]
		) {
			result = await finalize({
				session: values.session,
				push: values.push,
				message: await readFile(values["message-file"], "utf8"),
			});
		} else {
			throw new Error(
				"Use prepare --repo PATH [--state-root PATH], or finalize --session PATH --message-file PATH [--push]",
			);
		}
		console.log(JSON.stringify(result));
		if (result.status === "blocked") process.exitCode = 1;
	} catch (error) {
		console.error(JSON.stringify({ status: "error", message: error.message }));
		process.exitCode = 1;
	}
}
