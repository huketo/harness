#!/usr/bin/env bun
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

/**
 * Model family used when --model is omitted. The exact slug is resolved from
 * `codex debug models` at run time, so a new Sol release needs no edit here.
 */
const DEFAULT_FAMILY = "sol";
const DEFAULT_EFFORT = "high";
export const REVIEW_SANDBOX = "read-only";
/**
 * Built-in permission profile that `--sandbox read-only` resolves to; codex
 * 0.164.0 renders the same filesystem policy for both in `codex debug prompt-input`.
 * `codex sandbox` accepts only a named profile, so the probes use this one.
 */
const REVIEW_PERMISSION_PROFILE = ":read-only";
export const REVIEW_APPROVAL_POLICY = "never";

/**
 * Feature flags turned off for the reviewer, grouped by the capability they
 * gate. Names come from `codex features list` (codex-cli 0.164.0).
 */
export const DISABLED_FEATURES = [
	// sub-agents
	"multi_agent",
	"multi_agent_v2",
	// apps and plugins (tool_suggest exposes request_plugin_install)
	"apps",
	"plugins",
	"remote_plugin",
	"tool_suggest",
	"skill_mcp_dependency_install",
	"hooks",
	// browser and computer use
	"browser_use",
	"browser_use_external",
	"in_app_browser",
	"computer_use",
	"image_generation",
	"memories",
	"standalone_web_search",
] as const;

const REVIEW_SYSTEM_PROMPT = `You are a capability-restricted code reviewer. Find concrete bugs introduced by the change described in the review brief. Inspect the named repository files and artifacts, trace values across producer/consumer boundaries, and report only actionable findings with provable impact. For each finding give severity, path, and the narrowest relevant line range. If there are no findings, say so plainly. Do not ask a human or attempt any mutation; put unresolved questions in the review output.`;

/** Replaced by the real temporary path when a review runs. */
const OUTPUT_PLACEHOLDER = "<output-last-message>";
const PROBE_TIMEOUT_MS = 5_000;

export interface ReviewRequest {
	brief?: string;
	cwd: string;
	inspectTools: boolean;
	/** Exact catalog slug; undefined means the current default family model. */
	model?: string;
	effort: string;
}

export type ProbeResult = "denied" | "allowed";

export interface ReviewBoundarySnapshot {
	codexVersion: string;
	model: string;
	effort: string;
	sandbox: string;
	permissionProfile: string;
	approvalPolicy: string;
	argv: string[];
	/** Requested features whose effective state is off. */
	disabledFeatures: string[];
	mcpServers: string[];
	probes: { write: ProbeResult; network: ProbeResult };
}

interface CodexResult {
	stdout: string;
	stderr: string;
	exitCode: number;
}

function fail(message: string): never {
	throw new Error(message);
}

function errorMessage(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

function valueAfter(argv: string[], index: number): string {
	const value = argv[index + 1];
	if (!value || value.startsWith("--")) fail(`${argv[index]} requires a value`);
	return value;
}

function usage(): string {
	return [
		"Usage: bun --no-install codex/review.ts [options] --brief TEXT",
		"       bun --no-install codex/review.ts [options] -- TEXT",
		"       bun --no-install codex/review.ts [options] --inspect-tools",
		"",
		`  --model ID       Exact slug from \`codex debug models\` (default: the listed "-${DEFAULT_FAMILY}" model with the best priority)`,
		`  --effort LEVEL   Reasoning effort the model supports (default: ${DEFAULT_EFFORT})`,
		"  --cwd DIR        Git repository to review (default: current directory)",
		"  --brief TEXT     Review assignment; positional text after -- is also accepted",
		"  --inspect-tools  Probe the read-only boundary and print it as JSON; no model call",
		"  --help           Show this help",
	].join("\n");
}

export function parseReviewArgs(
	argv: string[],
): ReviewRequest | { help: true } {
	const result: ReviewRequest = {
		cwd: process.cwd(),
		inspectTools: false,
		effort: DEFAULT_EFFORT,
	};
	const positional: string[] = [];
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		if (arg === "--help" || arg === "-h") return { help: true };
		if (arg === "--") {
			positional.push(...argv.slice(i + 1));
			break;
		}
		if (arg === "--model") result.model = valueAfter(argv, i++);
		else if (arg === "--effort") result.effort = valueAfter(argv, i++);
		else if (arg === "--cwd") result.cwd = resolve(valueAfter(argv, i++));
		else if (arg === "--brief") {
			if (result.brief !== undefined) fail("Supply --brief only once");
			result.brief = valueAfter(argv, i++);
		}
		else if (arg === "--inspect-tools") result.inspectTools = true;
		else if (arg.startsWith("--")) fail(`Unknown option: ${arg}`);
		else positional.push(arg);
	}
	if (positional.length > 0) {
		if (result.brief)
			fail(
				"Supply the review brief either with --brief or as positional text, not both",
			);
		result.brief = positional.join(" ");
	}
	if (!result.inspectTools && !result.brief?.trim())
		fail("A non-empty review brief is required");
	return result;
}

function catalogModels(catalog: unknown): any[] {
	const models =
		typeof catalog === "object" && catalog !== null && "models" in catalog
			? catalog.models
			: undefined;
	if (!Array.isArray(models)) fail("codex debug models returned no model list");
	return models;
}

/**
 * The default reviewer: among listed catalog models whose slug ends in
 * `-sol`, the one Codex ranks first (lowest `priority`).
 */
export function resolveDefaultModel(catalog: unknown): string {
	const candidates = catalogModels(catalog).filter(
		(entry) =>
			typeof entry?.slug === "string" &&
			entry.slug.endsWith(`-${DEFAULT_FAMILY}`) &&
			entry.visibility !== "hide",
	);
	if (candidates.length === 0)
		fail(
			`No listed "-${DEFAULT_FAMILY}" model in the codex catalog; pass --model with an exact slug`,
		);
	const rank = (entry: { priority?: unknown }) =>
		typeof entry.priority === "number" ? entry.priority : Number.POSITIVE_INFINITY;
	return candidates.reduce((best, entry) => (rank(entry) < rank(best) ? entry : best)).slug;
}

/** Check the selection against `codex debug models` output; exact slug only. */
export function validateModelSelection(
	catalog: unknown,
	model: string,
	effort: string,
): void {
	const models = catalogModels(catalog);
	const slugs = models
		.map((entry) => entry?.slug)
		.filter((slug) => typeof slug === "string");
	const entry = models.find((candidate) => candidate?.slug === model);
	if (!entry) {
		fail(
			`Reviewer requires exact model "${model}"; codex catalog slugs: ${slugs.join(", ")}`,
		);
	}
	const levels: unknown[] = Array.isArray(entry.supported_reasoning_levels)
		? entry.supported_reasoning_levels.map(
				(level: { effort?: unknown }) => level?.effort,
			)
		: [];
	if (!levels.includes(effort)) {
		fail(
			`Model "${model}" does not support effort "${effort}". Supported values: ${levels.join(", ")}`,
		);
	}
}

/**
 * Overrides shared by every codex invocation, so the inspection reads the same
 * effective configuration the review runs with. Catalog models with
 * `multi_agent_version: v2` keep their collaboration tools even with both
 * multi-agent features off, so the thread caps are also set to their minimum.
 * The table form disables the feature and sets its cap in one value, which a
 * separate `--disable multi_agent_v2` would replace.
 */
export function reviewConfigArgs(effort: string): string[] {
	const args = [
		"-c",
		`approval_policy=${JSON.stringify(REVIEW_APPROVAL_POLICY)}`,
		"-c",
		'web_search="disabled"',
		"-c",
		`model_reasoning_effort=${JSON.stringify(effort)}`,
		// JSON string escapes are valid TOML basic-string escapes.
		"-c",
		`developer_instructions=${JSON.stringify(REVIEW_SYSTEM_PROMPT)}`,
		"-c",
		"agents.max_threads=1",
		"-c",
		"features.multi_agent_v2={enabled=false,max_concurrent_threads_per_session=1}",
	];
	for (const feature of DISABLED_FEATURES) {
		if (feature !== "multi_agent_v2") args.push("--disable", feature);
	}
	return args;
}

export function buildCodexExecArgs(options: {
	cwd: string;
	model: string;
	effort: string;
	outputFile: string;
}): string[] {
	return [
		"exec",
		"--sandbox",
		REVIEW_SANDBOX,
		...reviewConfigArgs(options.effort),
		"--ephemeral",
		"--ignore-user-config",
		"--ignore-rules",
		"--color",
		"never",
		"-m",
		options.model,
		"-C",
		options.cwd,
		"-o",
		options.outputFile,
		// Read the brief from stdin; it may exceed one argv string.
		"-",
	];
}

const FORBIDDEN_EXEC_ARGS = [
	"--dangerously-bypass-approvals-and-sandbox",
	"--dangerously-bypass-hook-trust",
	"--approve-for-me",
	"--add-dir",
	"--skip-git-repo-check",
	"--worktree",
	"--enable",
	"--profile",
	"-p",
];
const REQUIRED_EXEC_ARGS = [
	"--ephemeral",
	"--ignore-user-config",
	"--ignore-rules",
];

export function assertRestrictedReviewBoundary(
	snapshot: ReviewBoundarySnapshot,
): void {
	if (snapshot.sandbox !== REVIEW_SANDBOX)
		fail(`Restricted reviewer sandbox changed: ${snapshot.sandbox}`);
	if (snapshot.approvalPolicy !== REVIEW_APPROVAL_POLICY)
		fail(
			`Restricted reviewer approval policy changed: ${snapshot.approvalPolicy}`,
		);
	const forbidden = snapshot.argv.filter((arg) =>
		FORBIDDEN_EXEC_ARGS.includes(arg),
	);
	if (forbidden.length > 0)
		fail(
			`Restricted reviewer argv widens the boundary: ${forbidden.join(", ")}`,
		);
	const missing = REQUIRED_EXEC_ARGS.filter(
		(arg) => !snapshot.argv.includes(arg),
	);
	const sandboxIndex = snapshot.argv.indexOf("--sandbox");
	if (sandboxIndex < 0 || snapshot.argv[sandboxIndex + 1] !== REVIEW_SANDBOX)
		missing.push(`--sandbox ${REVIEW_SANDBOX}`);
	if (missing.length > 0)
		fail(`Restricted reviewer argv lacks: ${missing.join(", ")}`);
	const enabled = DISABLED_FEATURES.filter(
		(feature) => !snapshot.disabledFeatures.includes(feature),
	);
	if (enabled.length > 0)
		fail(
			`Restricted reviewer features are not disabled: ${enabled.join(", ")}`,
		);
	if (snapshot.mcpServers.length > 0)
		fail(`Restricted reviewer MCP servers: ${snapshot.mcpServers.join(", ")}`);
	for (const [probe, result] of Object.entries(snapshot.probes)) {
		if (result !== "denied")
			fail(`Restricted reviewer sandbox allowed the ${probe} probe`);
	}
}

function codexExecutable(): string {
	const codex = Bun.which("codex");
	if (!codex)
		fail("The restricted reviewer requires an installed codex executable");
	return codex;
}

async function runCodex(
	codex: string,
	args: string[],
	options: { cwd: string; env?: Record<string, string | undefined> },
): Promise<CodexResult> {
	const child = Bun.spawn([codex, ...args], {
		cwd: options.cwd,
		env: options.env ?? process.env,
		stdin: "ignore",
		stdout: "pipe",
		stderr: "pipe",
	});
	const [stdout, stderr, exitCode] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	return { stdout, stderr, exitCode };
}

function checked(label: string, result: CodexResult): string {
	if (result.exitCode !== 0)
		fail(
			`${label} exited with code ${result.exitCode}: ${result.stderr.trim()}`,
		);
	return result.stdout;
}

async function loadModelCatalog(codex: string, cwd: string): Promise<unknown> {
	const stdout = checked(
		"codex debug models",
		await runCodex(codex, ["debug", "models"], { cwd }),
	);
	try {
		return JSON.parse(stdout);
	} catch {
		fail("codex debug models did not print JSON");
	}
}

/** Parse `codex features list` rows: name, stage (may contain spaces), effective state. */
export function parseFeatureStates(output: string): Map<string, boolean> {
	const states = new Map<string, boolean>();
	for (const line of output.split("\n")) {
		const match = /^(\S+)\s+.*\s(true|false)\s*$/.exec(line);
		if (match) states.set(match[1], match[2] === "true");
	}
	return states;
}

async function probeWrite(
	codex: string,
	cwd: string,
	config: string[],
	env: Record<string, string | undefined>,
): Promise<ProbeResult> {
	const target = join(cwd, `.codex-review-probe-${randomUUID()}`);
	try {
		const result = await runCodex(
			codex,
			sandboxArgs(cwd, config, [
				"/bin/sh",
				"-c",
				'echo started; : > "$1"',
				"sh",
				target,
			]),
			{ cwd, env },
		);
		if (!result.stdout.includes("started"))
			fail(`Write probe did not start in the sandbox: ${result.stderr.trim()}`);
		return existsSync(target) ? "allowed" : "denied";
	} finally {
		await rm(target, { force: true });
	}
}

/**
 * Connect to a listener on host loopback. A sandbox that keeps the host network
 * namespace reaches it; the read-only profile gets a private, empty one.
 */
async function probeNetwork(
	codex: string,
	cwd: string,
	config: string[],
	env: Record<string, string | undefined>,
): Promise<ProbeResult> {
	let accepted = 0;
	const server = Bun.listen({
		hostname: "127.0.0.1",
		port: 0,
		socket: {
			open(socket) {
				accepted++;
				socket.end();
			},
			data() {},
		},
	});
	try {
		const script = [
			'const net = require("node:net");',
			'console.log("started");',
			`setTimeout(() => { console.log("timeout"); process.exit(4); }, ${PROBE_TIMEOUT_MS});`,
			`const socket = net.connect(${server.port}, "127.0.0.1");`,
			'socket.on("connect", () => { console.log("connected"); socket.end(); process.exit(0); });',
			'socket.on("error", (error) => { console.log("error", error.code); process.exit(3); });',
		].join("\n");
		const result = await runCodex(
			codex,
			sandboxArgs(cwd, config, [
				process.execPath,
				"--no-install",
				"-e",
				script,
			]),
			{ cwd, env },
		);
		if (!result.stdout.includes("started"))
			fail(
				`Network probe did not start in the sandbox: ${result.stderr.trim()}`,
			);
		return result.stdout.includes("connected") || accepted > 0
			? "allowed"
			: "denied";
	} finally {
		server.stop(true);
	}
}

function sandboxArgs(
	cwd: string,
	config: string[],
	command: string[],
): string[] {
	return [
		"sandbox",
		"--permission-profile",
		REVIEW_PERMISSION_PROFILE,
		...config,
		"-C",
		cwd,
		"--",
		...command,
	];
}

/**
 * Observe the boundary without calling a model. `features list`, `mcp list`,
 * and `sandbox` have no `--ignore-user-config`, so they run against an empty
 * CODEX_HOME: the same configuration stack as the review minus user config.
 */
export async function inspectReviewBoundary(
	codex: string,
	request: Pick<ReviewRequest, "cwd" | "effort"> & { model: string },
): Promise<ReviewBoundarySnapshot> {
	const codexVersion = checked(
		"codex --version",
		await runCodex(codex, ["--version"], { cwd: request.cwd }),
	).trim();
	const home = await mkdtemp(join(tmpdir(), "harness-codex-review-"));
	try {
		const env = { ...process.env, CODEX_HOME: home };
		const config = reviewConfigArgs(request.effort);
		const features = parseFeatureStates(
			checked(
				"codex features list",
				await runCodex(codex, ["features", "list", ...config], {
					cwd: request.cwd,
					env,
				}),
			),
		);
		const servers: unknown = JSON.parse(
			checked(
				"codex mcp list",
				await runCodex(codex, ["mcp", "list", "--json", ...config], {
					cwd: request.cwd,
					env,
				}),
			),
		);
		if (!Array.isArray(servers))
			fail("codex mcp list did not print a JSON list");
		return {
			codexVersion,
			model: request.model,
			effort: request.effort,
			sandbox: REVIEW_SANDBOX,
			permissionProfile: REVIEW_PERMISSION_PROFILE,
			approvalPolicy: REVIEW_APPROVAL_POLICY,
			argv: buildCodexExecArgs({
				cwd: request.cwd,
				model: request.model,
				effort: request.effort,
				outputFile: OUTPUT_PLACEHOLDER,
			}),
			disabledFeatures: DISABLED_FEATURES.filter(
				(feature) => features.get(feature) === false,
			),
			mcpServers: servers.map((server) => String(server?.name)),
			probes: {
				write: await probeWrite(codex, request.cwd, config, env),
				network: await probeNetwork(codex, request.cwd, config, env),
			},
		};
	} finally {
		await rm(home, { recursive: true, force: true });
	}
}

async function reviewOnce(
	codex: string,
	request: ReviewRequest & { brief: string; model: string },
): Promise<string> {
	const outputDir = await mkdtemp(join(tmpdir(), "harness-codex-review-out-"));
	try {
		const outputFile = join(outputDir, "last-message.txt");
		const child = Bun.spawn(
			[
				codex,
				...buildCodexExecArgs({
					cwd: request.cwd,
					model: request.model,
					effort: request.effort,
					outputFile,
				}),
			],
			{
				cwd: request.cwd,
				stdin: new Blob([`Review brief:\n${request.brief.trim()}\n`]),
				stdout: "ignore",
				// codex exec streams progress here; show it only on failure.
				stderr: "pipe",
			},
		);
		const stderr = new Response(child.stderr).text();
		// Stop the reviewer turn with the launcher rather than finishing it unseen.
		const stop = () => child.kill("SIGTERM");
		const signals = ["SIGINT", "SIGTERM", "SIGHUP"] as const;
		for (const signal of signals) process.on(signal, stop);
		let exitCode: number;
		try {
			exitCode = await child.exited;
		} finally {
			for (const signal of signals) process.off(signal, stop);
		}
		let output = "";
		try {
			output = (await readFile(outputFile, "utf8")).trim();
		} catch {}
		if (exitCode === 0 && output) return output;
		process.stderr.write(await stderr);
		if (exitCode !== 0) fail(`codex exec exited with code ${exitCode}`);
		fail("The reviewer returned no text output");
	} finally {
		await rm(outputDir, { recursive: true, force: true });
	}
}

/** Validate, inspect, and either print the boundary or run one review. */
export async function runReview(request: ReviewRequest): Promise<string> {
	const codex = codexExecutable();
	const catalog = await loadModelCatalog(codex, request.cwd);
	const model = request.model ?? resolveDefaultModel(catalog);
	validateModelSelection(catalog, model, request.effort);
	const resolved = { ...request, model };
	const snapshot = await inspectReviewBoundary(codex, resolved);
	assertRestrictedReviewBoundary(snapshot);
	if (request.inspectTools) return JSON.stringify(snapshot, null, 2);
	if (!request.brief?.trim()) fail("A non-empty review brief is required");
	return await reviewOnce(codex, { ...resolved, brief: request.brief });
}

async function main(): Promise<void> {
	const parsed = parseReviewArgs(process.argv.slice(2));
	if ("help" in parsed) {
		process.stdout.write(`${usage()}\n`);
		return;
	}
	process.stdout.write(`${await runReview(parsed)}\n`);
}

if (import.meta.main) {
	main().catch((error) => {
		process.stderr.write(`${errorMessage(error)}\n`);
		process.exitCode = 1;
	});
}
