// Contract regression tests for t3/scheduled/host-sync.mjs.
//
// Every fixture is a fresh temporary Git repository (a "bare remote" plus a
// "main checkout"); nothing here touches the real $HOME, a real remote, or
// the actual repo this file lives in. Git's global/system config is
// redirected to a throwaway file for the whole process so a developer
// machine's `commit.gpgsign`, credential helpers, or `init.defaultBranch`
// can never leak into these fixtures (or into the module under test, which
// inherits the same environment when it shells out to `git`).
//
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
	existsSync,
	lstatSync,
	mkdirSync,
	mkdtempSync,
	readFileSync,
	realpathSync,
	rmSync,
	symlinkSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
	after,
	afterEach,
	before,
	beforeEach,
	describe,
	test,
} from "node:test";

import { finalize, prepare } from "./host-sync.mjs";

// The exact allowlist from the module contract: paths the agent may edit in
// the private clone. Kept here (not imported) because the test asserts the
// module's *behavior* against this list, not its internal representation.
const ALLOWLIST = [
	"agy/settings.snapshot.json",
	"third-party/skills.lock.json",
	"README.md",
	"docs/FACTS.md",
	"docs/REPO.md",
];

function git(cwd, args) {
	return execFileSync("git", args, { cwd, encoding: "utf8" }).trim();
}

function seedRepoFiles(dir) {
	for (const rel of ALLOWLIST) {
		const parts = rel.split("/");
		const fileName = parts.pop();
		const dirPath = parts.length ? join(dir, ...parts) : dir;
		mkdirSync(dirPath, { recursive: true });
		writeFileSync(join(dirPath, fileName), `${rel} initial\n`);
	}
	// A representative non-allowlisted path, mirroring the real repo's
	// `skills/<name>/SKILL.md` layout that must stay off-limits.
	mkdirSync(join(dir, "skills", "example"), { recursive: true });
	writeFileSync(
		join(dir, "skills", "example", "SKILL.md"),
		"# example skill\n",
	);
}

function treeSnapshot(dir) {
	return {
		head: git(dir, ["rev-parse", "HEAD"]),
		branch: git(dir, ["rev-parse", "--abbrev-ref", "HEAD"]),
		status: git(dir, ["status", "--porcelain=v1", "--untracked-files=all"]),
	};
}

function remoteSnapshot(bareDir) {
	return git(bareDir, ["for-each-ref", "--format=%(refname) %(objectname)"]);
}

function editAllowlisted(
	workspace,
	rel = "docs/REPO.md",
	suffix = "agent edit\n",
) {
	const target = join(workspace, ...rel.split("/"));
	writeFileSync(target, readFileSync(target, "utf8") + suffix);
	return target;
}

let sandboxHome;
const savedEnvironment = Object.fromEntries(
	[
		"HOME",
		"GIT_CONFIG_GLOBAL",
		"GIT_CONFIG_SYSTEM",
		"GIT_CONFIG_NOSYSTEM",
		"GIT_TERMINAL_PROMPT",
	].map((key) => [key, process.env[key]]),
);

before(() => {
	// One throwaway HOME + git config file for the whole suite, so no fixture
	// ever consults the real user's global git config or credentials.
	sandboxHome = realpathSync(mkdtempSync(join(tmpdir(), "host-sync-home-")));
	const gitConfigPath = join(sandboxHome, ".gitconfig");
	writeFileSync(
		gitConfigPath,
		"[user]\n\tname = Host Sync Test\n\temail = host-sync-test@example.invalid\n" +
			"[commit]\n\tgpgsign = false\n[tag]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n",
	);
	process.env.HOME = sandboxHome;
	process.env.GIT_CONFIG_GLOBAL = gitConfigPath;
	process.env.GIT_CONFIG_SYSTEM = "/dev/null";
	process.env.GIT_CONFIG_NOSYSTEM = "1";
	process.env.GIT_TERMINAL_PROMPT = "0";
});

after(() => {
	try {
		rmSync(sandboxHome, { recursive: true, force: true });
	} finally {
		for (const [key, value] of Object.entries(savedEnvironment)) {
			if (value === undefined) delete process.env[key];
			else process.env[key] = value;
		}
	}
});

describe("t3/scheduled/host-sync contract", () => {
	let root;

	beforeEach(() => {
		root = realpathSync(mkdtempSync(join(tmpdir(), "host-sync-case-")));
	});

	afterEach(() => {
		rmSync(root, { recursive: true, force: true });
	});

	function makeBareRemote() {
		const dir = realpathSync(mkdtempSync(join(root, "remote-")));
		git(dir, ["init", "--bare", "-b", "main"]);
		return dir;
	}

	function makeOriginalRepo(remoteUrl, { push = true } = {}) {
		const dir = realpathSync(mkdtempSync(join(root, "original-")));
		git(dir, ["init", "-b", "main"]);
		seedRepoFiles(dir);
		git(dir, ["add", "-A"]);
		git(dir, ["commit", "-m", "initial"]);
		if (remoteUrl) {
			git(dir, ["remote", "add", "origin", remoteUrl]);
			if (push) git(dir, ["push", "-u", "origin", "main"]);
		}
		return dir;
	}

	function makeStateRoot() {
		const dir = join(root, "state");
		mkdirSync(dir, { recursive: true });
		return dir;
	}

	async function prepareFixture() {
		const remote = makeBareRemote();
		const original = makeOriginalRepo(remote);
		const stateRoot = makeStateRoot();
		const prepared = await prepare({ repo: original, stateRoot });
		return { remote, original, stateRoot, prepared };
	}

	test("prepare skips a feature branch even at the same SHA as main", async () => {
		const remote = makeBareRemote();
		const original = makeOriginalRepo(remote);
		git(original, ["checkout", "-b", "feature"]);
		const before = treeSnapshot(original);
		const beforeRemote = remoteSnapshot(remote);

		const result = await prepare({
			repo: original,
			stateRoot: makeStateRoot(),
		});

		assert.equal(result.status, "skipped");
		assert.equal(result.reason, "not_main");
		assert.deepEqual(treeSnapshot(original), before);
		assert.equal(remoteSnapshot(remote), beforeRemote);
	});

	for (const kind of ["staged", "unstaged", "untracked"]) {
		test(`prepare skips ${kind}-only dirt before any remote access`, async () => {
			const invalidRemote = join(root, "does-not-exist", "origin.git");
			const original = makeOriginalRepo(invalidRemote, { push: false });
			const path = kind === "untracked" ? "new-file.txt" : "README.md";
			writeFileSync(join(original, path), "user work\n");
			if (kind === "staged") git(original, ["add", path]);
			const before = treeSnapshot(original);

			const result = await prepare({
				repo: original,
				stateRoot: makeStateRoot(),
			});

			assert.equal(result.status, "skipped");
			assert.equal(result.reason, "dirty");
			assert.deepEqual(treeSnapshot(original), before);
			assert.equal(existsSync(join(original, ".git", "FETCH_HEAD")), false);
		});
	}

	test("prepare creates an isolated private clone and leaves the original checkout untouched", async () => {
		const { remote, original, prepared } = await prepareFixture();

		assert.equal(prepared.status, "ready");
		assert.equal(prepared.base, git(original, ["rev-parse", "HEAD"]));
		assert.equal(existsSync(join(prepared.workspace, ".git")), true);
		assert.equal(git(prepared.workspace, ["rev-parse", "HEAD"]), prepared.base);
		assert.equal(git(prepared.workspace, ["remote", "get-url", "origin"]), remote);
		assert.equal(existsSync(join(prepared.session, "manifest.json")), true);

		const beforeOriginalContent = readFileSync(
			join(original, "docs", "REPO.md"),
			"utf8",
		);
		editAllowlisted(prepared.workspace);
		assert.equal(readFileSync(join(original, "docs", "REPO.md"), "utf8"), beforeOriginalContent);
	});

	test("finalize commits allowlisted edits and publishes to the bare remote when push is requested", async () => {
		const { remote, original, prepared } = await prepareFixture();
		editAllowlisted(prepared.workspace, "docs/REPO.md", "appended by agent\n");
		const originalBefore = treeSnapshot(original);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "host-sync: update docs/REPO.md",
		});

		assert.equal(result.status, "published");
		assert.deepEqual(result.paths, ["docs/REPO.md"]);
		assert.equal(git(remote, ["rev-parse", "refs/heads/main"]), result.commit);

		const published = execFileSync(
			"git",
			["--git-dir", remote, "show", `${result.commit}:docs/REPO.md`],
			{
				encoding: "utf8",
			},
		);
		assert.ok(published.includes("appended by agent"));
		// The original checkout is never fast-forwarded, even on a successful publish.
		assert.deepEqual(treeSnapshot(original), originalBefore);
	});

	test("finalize is a no-op when the workspace has no candidate changes", async () => {
		const { remote, original, prepared } = await prepareFixture();
		const remoteBefore = remoteSnapshot(remote);
		const originalBefore = treeSnapshot(original);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "nothing to publish",
		});

		assert.equal(result.status, "noop");
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.deepEqual(treeSnapshot(original), originalBefore);
	});

	test("finalize blocks edits outside the snapshot allowlist and preserves them privately", async () => {
		const { remote, original, prepared } = await prepareFixture();
		const forbidden = join(prepared.workspace, "skills", "example", "SKILL.md");
		writeFileSync(forbidden, "forbidden edit\n");
		const originalBefore = treeSnapshot(original);
		const remoteBefore = remoteSnapshot(remote);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "attempt forbidden path",
		});

		assert.equal(result.status, "blocked");
		assert.deepEqual(treeSnapshot(original), originalBefore);
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.equal(git(prepared.workspace, ["rev-parse", "HEAD"]), prepared.base);
		assert.equal(readFileSync(forbidden, "utf8"), "forbidden edit\n");
	});

	test("finalize blocks when the original checkout becomes dirty after prepare", async () => {
		const { remote, original, prepared } = await prepareFixture();
		const target = editAllowlisted(prepared.workspace);
		writeFileSync(
			join(original, "unexpected.txt"),
			"someone touched the original\n",
		);
		const remoteBefore = remoteSnapshot(remote);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "should be blocked",
		});

		assert.equal(result.status, "blocked");
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.equal(git(prepared.workspace, ["rev-parse", "HEAD"]), prepared.base);
		assert.ok(readFileSync(target, "utf8").includes("agent edit"));
		assert.equal(existsSync(join(original, "unexpected.txt")), true);
	});

	test("finalize blocks when the original checkout switches branches after prepare", async () => {
		const { remote, original, prepared } = await prepareFixture();
		editAllowlisted(prepared.workspace);
		git(original, ["checkout", "-b", "other"]);
		const remoteBefore = remoteSnapshot(remote);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "should be blocked",
		});

		assert.equal(result.status, "blocked");
		assert.equal(git(original, ["rev-parse", "--abbrev-ref", "HEAD"]), "other");
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.equal(git(prepared.workspace, ["rev-parse", "HEAD"]), prepared.base);
	});

	test("finalize blocks when the private clone already has staged changes before it runs", async () => {
		const { remote, original, prepared } = await prepareFixture();
		editAllowlisted(prepared.workspace);
		git(prepared.workspace, ["add", "docs/REPO.md"]);
		const originalBefore = treeSnapshot(original);
		const remoteBefore = remoteSnapshot(remote);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "should be blocked",
		});

		assert.equal(result.status, "blocked");
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.deepEqual(treeSnapshot(original), originalBefore);
		// The pre-staged change is preserved for inspection, not silently reset.
		assert.ok(git(prepared.workspace, ["status", "--porcelain=v1"]).includes("docs/REPO.md"));
	});

	test("finalize blocks when origin/main advances past base before it runs", async () => {
		const { remote, original, prepared } = await prepareFixture();
		editAllowlisted(prepared.workspace);

		const interloper = realpathSync(mkdtempSync(join(root, "interloper-")));
		git(interloper, ["clone", remote, "."]);
		writeFileSync(join(interloper, "README.md"), "external update\n");
		git(interloper, ["add", "README.md"]);
		git(interloper, ["commit", "-m", "external change"]);
		git(interloper, ["push", "origin", "main"]);
		const advancedRemote = remoteSnapshot(remote);
		const originalBefore = treeSnapshot(original);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "should be blocked",
		});

		assert.equal(result.status, "blocked");
		// The interloper's push stands; finalize must not touch the remote further.
		assert.equal(remoteSnapshot(remote), advancedRemote);
		assert.deepEqual(treeSnapshot(original), originalBefore);
		assert.equal(git(prepared.workspace, ["rev-parse", "HEAD"]), prepared.base);
	});

	test("finalize rejects a candidate path replaced with a symlink", async () => {
		const { remote, original, prepared } = await prepareFixture();
		const target = join(prepared.workspace, "docs", "REPO.md");
		rmSync(target);
		symlinkSync(join(prepared.workspace, "README.md"), target);
		const remoteBefore = remoteSnapshot(remote);
		const originalBefore = treeSnapshot(original);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "should be blocked",
		});

		assert.equal(result.status, "blocked");
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.deepEqual(treeSnapshot(original), originalBefore);
		assert.equal(git(prepared.workspace, ["rev-parse", "HEAD"]), prepared.base);
		// Rejected work is preserved privately, not converted or committed.
		assert.equal(lstatSync(target).isSymbolicLink(), true);
	});

	test("finalize rejects a candidate path deletion", async () => {
		const { remote, original, prepared } = await prepareFixture();
		const target = join(prepared.workspace, "README.md");
		rmSync(target);
		const remoteBefore = remoteSnapshot(remote);
		const originalBefore = treeSnapshot(original);

		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "should be blocked",
		});

		assert.equal(result.status, "blocked");
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.deepEqual(treeSnapshot(original), originalBefore);
		assert.equal(git(prepared.workspace, ["rev-parse", "HEAD"]), prepared.base);
		assert.equal(existsSync(target), false);
		assert.equal(existsSync(join(original, "README.md")), true);
	});

	test("prepare preserves an active index lock without contacting the remote", async () => {
		const original = makeOriginalRepo(join(root, "missing.git"), {
			push: false,
		});
		const lock = join(original, ".git", "index.lock");
		writeFileSync(lock, "owned by another process\n");
		const result = await prepare({
			repo: original,
			stateRoot: makeStateRoot(),
		});
		assert.equal(result.status, "skipped");
		assert.equal(result.reason, "git_operation_in_progress");
		assert.equal(readFileSync(lock, "utf8"), "owned by another process\n");
	});

	test("prepare refuses a clean but unpublished local main commit", async () => {
		const remote = makeBareRemote();
		const original = makeOriginalRepo(remote);
		editAllowlisted(original);
		git(original, ["add", "docs/REPO.md"]);
		git(original, ["commit", "-m", "user unpublished work"]);
		const before = treeSnapshot(original);
		const remoteBefore = remoteSnapshot(remote);
		const result = await prepare({
			repo: original,
			stateRoot: makeStateRoot(),
		});
		assert.equal(result.status, "skipped");
		assert.equal(result.reason, "unpublished_or_diverged_head");
		assert.deepEqual(treeSnapshot(original), before);
		assert.equal(remoteSnapshot(remote), remoteBefore);
	});

	test("default finalize verifies JSON snapshot and doc changes without publishing", async () => {
		const { remote, original, prepared } = await prepareFixture();
		const remoteBefore = remoteSnapshot(remote);
		const originalBefore = treeSnapshot(original);
		writeFileSync(
			join(prepared.workspace, "third-party/skills.lock.json"),
			'{"skills":{}}',
		);
		editAllowlisted(prepared.workspace);
		const result = await finalize({
			session: prepared.session,
			message: "verify private candidate",
		});
		assert.equal(result.status, "verified");
		assert.deepEqual(result.paths, [
			"docs/REPO.md",
			"third-party/skills.lock.json",
		]);
		assert.equal(
			git(prepared.workspace, [
				"show",
				`${result.commit}:third-party/skills.lock.json`,
			]),
			'{"skills":{}}',
		);
		assert.deepEqual(treeSnapshot(original), originalBefore);
		assert.equal(remoteSnapshot(remote), remoteBefore);
	});

	test("finalize refuses a credential value in an otherwise valid JSON snapshot", async () => {
		const { remote, original, prepared } = await prepareFixture();
		const remoteBefore = remoteSnapshot(remote);
		const originalBefore = treeSnapshot(original);
		writeFileSync(
			join(prepared.workspace, "agy/settings.snapshot.json"),
			'{"token":"synthetic-test-credential"}',
		);
		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "must not publish credential",
		});
		assert.equal(result.status, "blocked");
		assert.equal(result.reason, "possible_secret:agy/settings.snapshot.json");
		assert.deepEqual(treeSnapshot(original), originalBefore);
		assert.equal(remoteSnapshot(remote), remoteBefore);
	});

	test("a symlinked state root still produces a finalizable owned session", async () => {
		const remote = makeBareRemote();
		const original = makeOriginalRepo(remote);
		const stateRoot = makeStateRoot();
		const alias = join(root, "state-alias");
		symlinkSync(stateRoot, alias, "dir");
		const prepared = await prepare({ repo: original, stateRoot: alias });
		editAllowlisted(prepared.workspace);
		const result = await finalize({
			session: prepared.session,
			message: "verify alias",
		});
		assert.equal(result.status, "verified");
		assert.equal(git(original, ["status", "--porcelain"]), "");
	});

	test("an in-repo ..cache name cannot bypass ignored-state ownership", async () => {
		const original = makeOriginalRepo(join(root, "missing.git"), {
			push: false,
		});
		const stateRoot = join(original, "..cache", "host-sync");
		const result = await prepare({ repo: original, stateRoot });
		assert.equal(result.status, "skipped");
		assert.equal(result.reason, "state_root_not_ignored");
		assert.equal(existsSync(stateRoot), false);
	});

	for (const [shape, value] of [
		["environment-map", { env: { GITLAB_TOKEN: "synthetic-credential" } }],
		["sensitive-key array", { apiKey: ["synthetic-array-credential"] }],
		[
			"CLI argument array",
			{ args: ["--api-key", "synthetic-argument-credential"] },
		],
	]) {
		test(`${shape} credentials are blocked before publication`, async () => {
			const { remote, prepared } = await prepareFixture();
			const before = remoteSnapshot(remote);
			writeFileSync(
				join(prepared.workspace, "agy/settings.snapshot.json"),
				JSON.stringify(value),
			);
			const result = await finalize({
				session: prepared.session,
				push: true,
				message: "reject credential shape",
			});
			assert.equal(result.status, "blocked");
			assert.equal(result.reason, "possible_secret:agy/settings.snapshot.json");
			assert.equal(remoteSnapshot(remote), before);
		});
	}

	test("raw document text cannot bypass known-token detection", async () => {
		const { remote, prepared } = await prepareFixture();
		const before = remoteSnapshot(remote);
		writeFileSync(
			join(prepared.workspace, "docs/FACTS.md"),
			"# Facts\n\nglpat-synthetic_token_for_test_123456\n",
		);
		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "reject comment token",
		});
		assert.equal(result.status, "blocked");
		assert.equal(result.reason, "possible_secret:docs/FACTS.md");
		assert.equal(remoteSnapshot(remote), before);
	});

	test("signing failure stays fail-closed with its original cause and private candidate", async () => {
		const { remote, original, prepared } = await prepareFixture();
		editAllowlisted(prepared.workspace);
		git(prepared.workspace, ["config", "commit.gpgsign", "true"]);
		git(prepared.workspace, ["config", "gpg.program", "/bin/false"]);
		git(prepared.workspace, [
			"config",
			"user.signingkey",
			"synthetic-signing-key",
		]);
		const before = treeSnapshot(original);
		const remoteBefore = remoteSnapshot(remote);
		const result = await finalize({
			session: prepared.session,
			push: true,
			message: "signed candidate",
		});
		assert.equal(result.status, "blocked");
		assert.equal(result.reason, "commit_failed");
		assert.equal(
			JSON.parse(readFileSync(join(prepared.session, "manifest.json"), "utf8"))
				.reason,
			"commit_failed",
		);
		assert.deepEqual(treeSnapshot(original), before);
		assert.equal(remoteSnapshot(remote), remoteBefore);
		assert.ok(readFileSync(join(prepared.workspace, "docs/REPO.md"), "utf8").includes("agent edit"));
	});

	test("an inherited alternate index cannot redirect candidate staging into the original", async () => {
		const { remote, original, prepared } = await prepareFixture();
		editAllowlisted(prepared.workspace);
		const index = join(original, ".git", "index");
		const before = readFileSync(index);
		const previous = process.env.GIT_INDEX_FILE;
		let result;
		try {
			process.env.GIT_INDEX_FILE = index;
			result = await finalize({
				session: prepared.session,
				push: true,
				message: "isolated index",
			});
		} finally {
			if (previous === undefined) delete process.env.GIT_INDEX_FILE;
			else process.env.GIT_INDEX_FILE = previous;
		}
		assert.equal(result.status, "published");
		assert.deepEqual(readFileSync(index), before);
		assert.equal(git(original, ["status", "--porcelain"]), "");
		assert.equal(git(remote, ["rev-parse", "main"]), result.commit);
	});
});
