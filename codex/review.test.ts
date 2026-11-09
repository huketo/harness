import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import {
	chmod,
	mkdir,
	mkdtemp,
	readFile,
	rm,
	writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";
import {
	assertRestrictedReviewBoundary,
	buildCodexExecArgs,
	DISABLED_FEATURES,
	findExecutable,
	parseFeatureStates,
	parseReviewArgs,
	resolveDefaultModel,
	validateModelSelection,
} from "./review.ts";
import type { ReviewBoundarySnapshot } from "./review.ts";

const REVIEW_ENTRY = join(import.meta.dirname, "review.ts");
const REAL_CODEX = findExecutable("codex");

const restricted: ReviewBoundarySnapshot = {
	codexVersion: "codex-cli 0.164.0",
	model: "gpt-6.1-sol",
	effort: "high",
	sandbox: "read-only",
	permissionProfile: ":read-only",
	approvalPolicy: "never",
	argv: buildCodexExecArgs({
		cwd: "/repo",
		model: "gpt-6.1-sol",
		effort: "high",
		outputFile: "/tmp/out",
	}),
	disabledFeatures: [...DISABLED_FEATURES],
	mcpServers: [],
	probes: { write: "denied", network: "denied" },
};

/**
 * PATH shim for `codex`: logs every invocation, answers `exec` itself so no
 * test reaches a model, answers `debug models` with a synthetic catalog,
 * optionally replaces `mcp list`, and forwards every other subcommand to the
 * installed codex under a temporary HOME and CODEX_HOME.
 */
const FAKE_CODEX = `#!${process.execPath}
const { appendFileSync, readFileSync, writeFileSync } = require("node:fs");
const log = (entry) => appendFileSync(process.env.FAKE_CODEX_LOG, JSON.stringify(entry) + "\\n");
const args = process.argv.slice(2);
log({ args });
if (args[0] === "exec") {
	log({ stdin: readFileSync(0, "utf8") });
	const output = process.env.FAKE_EXEC_OUTPUT;
	if (output !== undefined) writeFileSync(args[args.indexOf("-o") + 1], output);
	process.stdout.write("exec progress on stdout\\n");
	process.exit(Number(process.env.FAKE_EXEC_EXIT ?? "0"));
}
if (args[0] === "debug" && args[1] === "models") {
	process.stdout.write(process.env.FAKE_MODELS_JSON);
	process.exit(0);
}
if (args[0] === "mcp" && process.env.FAKE_MCP_JSON) {
	process.stdout.write(process.env.FAKE_MCP_JSON);
	process.exit(0);
}
const child = require("node:child_process").spawnSync(process.env.REAL_CODEX, args, { stdio: "inherit" });
process.exit(child.status ?? 1);
`;

type LogEntry = { args: string[] } | { stdin: string };

/** Synthetic catalog: the default resolves to the best-ranked listed `-sol` slug. */
const FAKE_MODELS = JSON.stringify({
	models: [
		{ slug: "gpt-6-sol", priority: 5, visibility: "list", supported_reasoning_levels: [{ effort: "high" }] },
		{ slug: "gpt-6.1-sol", priority: 1, visibility: "list", supported_reasoning_levels: [{ effort: "low" }, { effort: "high" }] },
		{ slug: "gpt-6.1-luna", priority: 0, visibility: "list", supported_reasoning_levels: [{ effort: "high" }] },
	],
});

/** Run the CLI against a fresh git repository with the logging codex shim first on PATH. */
async function runReviewer(args: string[], env: Record<string, string> = {}) {
	if (!REAL_CODEX) throw new Error("codex is not installed");
	const root = await mkdtemp(join(tmpdir(), "harness-codex-review-test-"));
	try {
		const bin = join(root, "bin");
		const repo = join(root, "repo");
		const logFile = join(root, "codex.log");
		await mkdir(bin);
		await writeFile(join(bin, "codex"), FAKE_CODEX);
		await chmod(join(bin, "codex"), 0o755);
		await writeFile(logFile, "");
		await mkdir(join(root, "home"));
		await mkdir(join(root, "codex-home"));
		// No real user home, Git configuration, or Codex configuration is visible to the run.
		const isolated = {
			HOME: join(root, "home"),
			CODEX_HOME: join(root, "codex-home"),
			GIT_CONFIG_GLOBAL: "/dev/null",
			GIT_CONFIG_NOSYSTEM: "1",
		};
		spawnSync("git", ["init", "-q", repo], { env: { ...process.env, ...isolated } });
		const child = spawn(
			process.execPath,
			[REVIEW_ENTRY, "--cwd", repo, ...args],
			{
				env: {
					...process.env,
					PATH: `${bin}:${process.env.PATH}`,
					...isolated,
					REAL_CODEX,
					FAKE_CODEX_LOG: logFile,
					FAKE_MODELS_JSON: FAKE_MODELS,
					...env,
				},
				stdio: ["ignore", "pipe", "pipe"],
			},
		);
		const text = (stream: NodeJS.ReadableStream) =>
			new Promise<string>((done, failed) => {
				const chunks: Buffer[] = [];
				stream.on("data", (chunk: Buffer) => chunks.push(chunk));
				stream.once("error", failed);
				stream.once("end", () => done(Buffer.concat(chunks).toString("utf8")));
			});
		const [stdout, stderr, exitCode] = await Promise.all([
			text(child.stdout),
			text(child.stderr),
			new Promise<number | null>((done, failed) => {
				child.once("error", failed);
				child.once("close", (code) => done(code));
			}),
		]);
		const log = (await readFile(logFile, "utf8"))
			.split("\n")
			.filter(Boolean)
			.map((line) => JSON.parse(line) as LogEntry);
		const subcommands = log.flatMap((entry) =>
			"args" in entry ? [entry.args[0]] : [],
		);
		const execArgs = log.find(
			(entry): entry is { args: string[] } =>
				"args" in entry && entry.args[0] === "exec",
		)?.args;
		const stdin = log.find(
			(entry): entry is { stdin: string } => "stdin" in entry,
		)?.stdin;
		return {
			stdout,
			stderr,
			exitCode,
			subcommands,
			execArgs,
			stdin,
			repoFiles: readdirSync(repo),
		};
	} finally {
		await rm(root, { recursive: true, force: true });
	}
}

test("relative --cwd resolves against the launcher and defaults are the documented ones", () => {
	assert.deepEqual(parseReviewArgs(["--cwd", "sub/dir", "--inspect-tools"]), {
		cwd: resolve("sub/dir"),
		inspectTools: true,
		effort: "high",
	});
});

test("the default model is the listed -sol slug Codex ranks first", () => {
	const entry = (slug: string, priority: number, visibility = "list") => ({
		slug,
		priority,
		visibility,
	});
	assert.equal(
		resolveDefaultModel({
			models: [
				entry("gpt-6-astra", 1),
				entry("gpt-6-sol", 4),
				entry("gpt-7-sol", 2),
				entry("gpt-8-sol", 0, "hide"),
				entry("gpt-6-solar", 0),
			],
		}),
		"gpt-7-sol",
	);
	assert.throws(() => resolveDefaultModel({ models: [entry("gpt-6-astra", 1)] }), /pass --model/);
});

test("the brief comes from exactly one source and must be non-empty", () => {
	const parsed = parseReviewArgs(["--", "look", "here"]);
	assert.ok(!("help" in parsed));
	assert.equal(parsed.brief, "look here");
	assert.throws(() => parseReviewArgs(["--brief", "a", "--", "b"]), /not both/);
	assert.throws(() => parseReviewArgs(["--brief", "a", "b"]), /not both/);
	assert.throws(() => parseReviewArgs(["--brief", "a", "--brief", "b"]), /only once/);
	assert.throws(() => parseReviewArgs([]), /non-empty review brief/);
	assert.throws(() => parseReviewArgs(["--brief", " ", "--model", "x"]), /non-empty/);
	assert.throws(() => parseReviewArgs(["--model", "--inspect-tools"]), /requires a value/);
});

test("model selection accepts only an exact catalog slug and its efforts", () => {
	const catalog = {
		models: [
			{
				slug: "gpt-6.1-sol",
				supported_reasoning_levels: [{ effort: "low" }, { effort: "high" }],
			},
		],
	};
	assert.doesNotThrow(() => validateModelSelection(catalog, "gpt-6.1-sol", "high"));
	assert.throws(() => validateModelSelection(catalog, "gpt-6.1", "high"), /exact model "gpt-6\.1"/);
	assert.throws(() => validateModelSelection(catalog, "GPT-6.1-sol", "high"), /exact model/);
	assert.throws(
		() => validateModelSelection(catalog, "gpt-6.1-sol", "max"),
		/does not support effort "max"/,
	);
});

test("feature rows parse with multi-word stages", () => {
	const states = parseFeatureStates(
		"hooks                                    stable             false\n" +
			"code_mode                                under development  true\n",
	);
	assert.equal(states.get("hooks"), false);
	assert.equal(states.get("code_mode"), true);
});

test("boundary guard accepts only the read-only, offline, MCP-free boundary", () => {
	assert.doesNotThrow(() => assertRestrictedReviewBoundary(restricted));
	const widened: Partial<ReviewBoundarySnapshot>[] = [
		{ probes: { write: "allowed", network: "denied" } },
		{ probes: { write: "denied", network: "allowed" } },
		{ mcpServers: ["korean-law"] },
		{
			disabledFeatures: DISABLED_FEATURES.filter(
				(name) => name !== "multi_agent",
			),
		},
		{ disabledFeatures: [] },
		{ sandbox: "workspace-write" },
		{ approvalPolicy: "on-request" },
		{
			argv: [...restricted.argv, "--dangerously-bypass-approvals-and-sandbox"],
		},
		{ argv: [...restricted.argv, "--add-dir", "/"] },
		{ argv: restricted.argv.filter((arg) => arg !== "--ignore-user-config") },
		{
			argv: restricted.argv.map((arg) =>
				arg === "read-only" ? "workspace-write" : arg,
			),
		},
	];
	for (const change of widened) {
		assert.throws(
			() => assertRestrictedReviewBoundary({ ...restricted, ...change }),
			/Restricted reviewer/,
		);
	}
});

test("installed codex --inspect-tools reports a denied boundary without running exec", { timeout: 60_000 }, async () => {
	const run = await runReviewer(["--inspect-tools"]);
	assert.equal(run.stderr, "");
	assert.equal(run.exitCode, 0);
	const snapshot = JSON.parse(run.stdout);
	assert.equal(snapshot.model, "gpt-6.1-sol");
	assert.equal(snapshot.effort, "high");
	assert.equal(snapshot.sandbox, "read-only");
	assert.equal(snapshot.approvalPolicy, "never");
	assert.deepEqual(snapshot.disabledFeatures, [...DISABLED_FEATURES]);
	assert.deepEqual(snapshot.mcpServers, []);
	assert.deepEqual(snapshot.probes, { write: "denied", network: "denied" });
	assert.ok(snapshot.argv.includes("exec"));
	assert.ok(snapshot.argv.includes("--ignore-user-config"));
	assert.ok(run.subcommands.includes("sandbox"));
	assert.ok(!run.subcommands.includes("exec"));
	// The write probe left nothing behind.
	assert.deepEqual(run.repoFiles, [".git"]);
});

test("installed codex rejects a partial model ID instead of a sibling model", { timeout: 60_000 }, async () => {
	const run = await runReviewer(["--model", "gpt-6.1", "--inspect-tools"]);
	assert.equal(run.exitCode, 1);
	assert.equal(run.stdout, "");
	assert.match(run.stderr, /exact model "gpt-6\.1"/);
	assert.ok(!run.subcommands.includes("sandbox"));
});

test("a review prints only the last message and sends the brief on stdin", { timeout: 60_000 }, async () => {
	const run = await runReviewer(["--brief", "check the diff"], {
		FAKE_EXEC_OUTPUT: "No findings.\n",
	});
	assert.equal(run.stderr, "");
	assert.equal(run.exitCode, 0);
	assert.equal(run.stdout, "No findings.\n");
	assert.equal(run.stdin, "Review brief:\ncheck the diff\n");
	// The boundary was inspected before the model process started.
	assert.ok(run.subcommands.indexOf("sandbox") < run.subcommands.indexOf("exec"));
	const outputFile = run.execArgs?.[run.execArgs.indexOf("-o") + 1] ?? "";
	assert.ok(outputFile.startsWith(tmpdir()));
	assert.equal(existsSync(outputFile), false);
});

test("a widened boundary is refused before codex exec starts", { timeout: 60_000 }, async () => {
	const run = await runReviewer(["--brief", "check the diff"], {
		FAKE_MCP_JSON: JSON.stringify([{ name: "planted", enabled: true }]),
		FAKE_EXEC_OUTPUT: "should not appear",
	});
	assert.equal(run.exitCode, 1);
	assert.equal(run.stdout, "");
	assert.match(run.stderr, /MCP servers: planted/);
	assert.ok(!run.subcommands.includes("exec"));
});

test("failed or empty codex exec runs exit 1 without stdout", { timeout: 60_000 }, async () => {
	const envs: Record<string, string>[] = [
		{ FAKE_EXEC_OUTPUT: "partial", FAKE_EXEC_EXIT: "2" },
		{ FAKE_EXEC_OUTPUT: "  \n" },
		{},
	];
	for (const env of envs) {
		const run = await runReviewer(["--brief", "check the diff"], env);
		assert.equal(run.exitCode, 1);
		assert.equal(run.stdout, "");
		assert.match(run.stderr, /codex exec exited with code 2|no text output/);
	}
});
