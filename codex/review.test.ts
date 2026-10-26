import { expect, test } from "bun:test";
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
import {
	assertRestrictedReviewBoundary,
	buildCodexExecArgs,
	DISABLED_FEATURES,
	parseFeatureStates,
	parseReviewArgs,
	resolveDefaultModel,
	type ReviewBoundarySnapshot,
	validateModelSelection,
} from "./review";

const REVIEW_ENTRY = join(import.meta.dir, "review.ts");
const REAL_CODEX = Bun.which("codex");

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
 * test reaches a model, optionally replaces `mcp list`, and forwards every
 * other subcommand to the installed codex.
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
if (args[0] === "mcp" && process.env.FAKE_MCP_JSON) {
	process.stdout.write(process.env.FAKE_MCP_JSON);
	process.exit(0);
}
const child = Bun.spawnSync([process.env.REAL_CODEX, ...args], { stdio: ["inherit", "inherit", "inherit"] });
process.exit(child.exitCode ?? 1);
`;

type LogEntry = { args: string[] } | { stdin: string };

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
		Bun.spawnSync(["git", "init", "-q", repo]);
		const child = Bun.spawn(
			[process.execPath, "--no-install", REVIEW_ENTRY, "--cwd", repo, ...args],
			{
				env: {
					...process.env,
					PATH: `${bin}:${process.env.PATH}`,
					REAL_CODEX,
					FAKE_CODEX_LOG: logFile,
					...env,
				},
				stdout: "pipe",
				stderr: "pipe",
			},
		);
		const [stdout, stderr, exitCode] = await Promise.all([
			new Response(child.stdout).text(),
			new Response(child.stderr).text(),
			child.exited,
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
	expect(parseReviewArgs(["--cwd", "sub/dir", "--inspect-tools"])).toEqual({
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
	expect(
		resolveDefaultModel({
			models: [
				entry("gpt-6-astra", 1),
				entry("gpt-6-sol", 4),
				entry("gpt-7-sol", 2),
				entry("gpt-8-sol", 0, "hide"),
				entry("gpt-6-solar", 0),
			],
		}),
	).toBe("gpt-7-sol");
	expect(() => resolveDefaultModel({ models: [entry("gpt-6-astra", 1)] })).toThrow(
		/pass --model/,
	);
});

test("the brief comes from exactly one source and must be non-empty", () => {
	expect(parseReviewArgs(["--", "look", "here"])).toMatchObject({
		brief: "look here",
	});
	expect(() => parseReviewArgs(["--brief", "a", "--", "b"])).toThrow(
		/not both/,
	);
	expect(() => parseReviewArgs(["--brief", "a", "b"])).toThrow(/not both/);
	expect(() => parseReviewArgs(["--brief", "a", "--brief", "b"])).toThrow(
		/only once/,
	);
	expect(() => parseReviewArgs([])).toThrow(/non-empty review brief/);
	expect(() => parseReviewArgs(["--brief", " ", "--model", "x"])).toThrow(
		/non-empty/,
	);
	expect(() => parseReviewArgs(["--model", "--inspect-tools"])).toThrow(
		/requires a value/,
	);
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
	expect(() =>
		validateModelSelection(catalog, "gpt-6.1-sol", "high"),
	).not.toThrow();
	expect(() => validateModelSelection(catalog, "gpt-6.1", "high")).toThrow(
		/exact model "gpt-6\.1"/,
	);
	expect(() => validateModelSelection(catalog, "GPT-6.1-sol", "high")).toThrow(
		/exact model/,
	);
	expect(() => validateModelSelection(catalog, "gpt-6.1-sol", "max")).toThrow(
		/does not support effort "max"/,
	);
});

test("feature rows parse with multi-word stages", () => {
	const states = parseFeatureStates(
		"hooks                                    stable             false\n" +
			"code_mode                                under development  true\n",
	);
	expect(states.get("hooks")).toBe(false);
	expect(states.get("code_mode")).toBe(true);
});

test("boundary guard accepts only the read-only, offline, MCP-free boundary", () => {
	expect(() => assertRestrictedReviewBoundary(restricted)).not.toThrow();
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
		expect(() =>
			assertRestrictedReviewBoundary({ ...restricted, ...change }),
		).toThrow(/Restricted reviewer/);
	}
});

test("installed codex --inspect-tools reports a denied boundary without running exec", async () => {
	const run = await runReviewer(["--inspect-tools"]);
	expect(run.stderr).toBe("");
	expect(run.exitCode).toBe(0);
	const snapshot = JSON.parse(run.stdout);
	expect(snapshot).toMatchObject({
		model: "gpt-6.1-sol",
		effort: "high",
		sandbox: "read-only",
		approvalPolicy: "never",
		disabledFeatures: [...DISABLED_FEATURES],
		mcpServers: [],
		probes: { write: "denied", network: "denied" },
	});
	expect(snapshot.argv).toEqual(
		expect.arrayContaining(["exec", "--ignore-user-config"]),
	);
	expect(run.subcommands).toContain("sandbox");
	expect(run.subcommands).not.toContain("exec");
	// The write probe left nothing behind.
	expect(run.repoFiles).toEqual([".git"]);
}, 60_000);

test("installed codex rejects a partial model ID instead of a sibling model", async () => {
	const run = await runReviewer(["--model", "gpt-6.1", "--inspect-tools"]);
	expect(run.exitCode).toBe(1);
	expect(run.stdout).toBe("");
	expect(run.stderr).toMatch(/exact model "gpt-6\.1"/);
	expect(run.subcommands).not.toContain("sandbox");
}, 60_000);

test("a review prints only the last message and sends the brief on stdin", async () => {
	const run = await runReviewer(["--brief", "check the diff"], {
		FAKE_EXEC_OUTPUT: "No findings.\n",
	});
	expect(run.stderr).toBe("");
	expect(run.exitCode).toBe(0);
	expect(run.stdout).toBe("No findings.\n");
	expect(run.stdin).toBe("Review brief:\ncheck the diff\n");
	// The boundary was inspected before the model process started.
	expect(run.subcommands.indexOf("sandbox")).toBeLessThan(
		run.subcommands.indexOf("exec"),
	);
	const outputFile = run.execArgs?.[run.execArgs.indexOf("-o") + 1] ?? "";
	expect(outputFile).toStartWith(tmpdir());
	expect(existsSync(outputFile)).toBe(false);
}, 60_000);

test("a widened boundary is refused before codex exec starts", async () => {
	const run = await runReviewer(["--brief", "check the diff"], {
		FAKE_MCP_JSON: JSON.stringify([{ name: "planted", enabled: true }]),
		FAKE_EXEC_OUTPUT: "should not appear",
	});
	expect(run.exitCode).toBe(1);
	expect(run.stdout).toBe("");
	expect(run.stderr).toMatch(/MCP servers: planted/);
	expect(run.subcommands).not.toContain("exec");
}, 60_000);

test("failed or empty codex exec runs exit 1 without stdout", async () => {
	for (const env of [
		{ FAKE_EXEC_OUTPUT: "partial", FAKE_EXEC_EXIT: "2" },
		{ FAKE_EXEC_OUTPUT: "  \n" },
		{},
	]) {
		const run = await runReviewer(["--brief", "check the diff"], env);
		expect(run.exitCode).toBe(1);
		expect(run.stdout).toBe("");
		expect(run.stderr).toMatch(/codex exec exited with code 2|no text output/);
	}
}, 60_000);
