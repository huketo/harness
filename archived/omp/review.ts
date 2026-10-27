#!/usr/bin/env bun
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import type { ThinkingLevel } from "@oh-my-pi/pi-agent-core";
import type * as Sdk from "@oh-my-pi/pi-coding-agent";
import type {
	AgentSession,
	CreateAgentSessionOptions,
	CreateAgentSessionResult,
	Settings,
} from "@oh-my-pi/pi-coding-agent";
import type * as RuntimeInit from "@oh-my-pi/pi-coding-agent/modes/runtime-init";
import {
	loadProfiles,
	loadState,
	type ResolvedProfile,
	resolveProfile,
	validateProfilesFile,
} from "./extensions/profiles/schema";

export const REVIEW_TOOL_NAMES = ["read", "grep", "glob"] as const;
const DEFAULT_PROFILE = "best";

/** Environment variable naming the private request/result directory shared with review-host.ts. */
export const REVIEW_IPC_ENV = "HARNESS_REVIEW_IPC_DIR";
const REQUEST_FILE = "request.json";
const RESULT_FILE = "result.json";
const HOST_EXTENSION_PATH = join(import.meta.dir, "review-host.ts");

const REVIEW_SYSTEM_PROMPT = `You are a capability-restricted code reviewer. Find concrete bugs introduced by the change described in the review brief. Inspect the named repository files and artifacts, trace values across producer/consumer boundaries, and report only actionable findings with provable impact. For each finding give severity, path, and the narrowest relevant line range. If there are no findings, say so plainly. Do not ask a human or attempt any mutation; put unresolved questions in the review output.`;

export type ReviewThinkingLevel = `${ThinkingLevel}` | "auto";

/**
 * SDK surface supplied by review-host.ts from inside the PATH `omp` process, so
 * the reviewer always uses the same runtime and model catalog as `omp models`.
 */
export interface ReviewRuntime {
	sdk: Pick<
		typeof Sdk,
		| "AgentRegistry"
		| "createAgentSession"
		| "getAgentDir"
		| "SessionManager"
		| "Settings"
	>;
	initializeExtensions: typeof RuntimeInit.initializeExtensions;
	thinkingEfforts: readonly string[];
	sanitizeText: (text: string) => string;
}

export interface ReviewSelection {
	profile: string;
	model: string;
	thinking: ReviewThinkingLevel;
	effortSource: ResolvedProfile["effortSource"] | "command-line";
}

export interface ReviewCapabilitySnapshot {
	enabledTools: string[];
	registeredTools: string[];
	mountedTools: string[];
	evalBridgeTools: string[];
	extensions: string[];
	mcpEnabled: boolean;
}

export interface ReviewRequest {
	brief?: string;
	cwd: string;
	inspectTools: boolean;
	model?: string;
	profile: string;
	thinking?: string;
}

type HostResult = { output: string } | { error: string };

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
		"Usage: bun omp/review.ts [options] --brief TEXT",
		"       bun omp/review.ts [options] -- TEXT",
		"",
		`  --profile NAME       Harness purpose profile (default: ${DEFAULT_PROFILE})`,
		"  --model PROVIDER/ID  Exact model override; keep profile effort (if absent, require --thinking)",
		"  --thinking LEVEL     Override profile effort using OMP's native thinking selector",
		"  --cwd DIR            Repository root to review (default: current directory)",
		"  --brief TEXT         Review assignment; positional text after -- is also accepted",
		"  --inspect-tools      Build and initialize the real session, print capabilities, do not call a model",
		"  --help               Show this help",
	].join("\n");
}

export function parseReviewArgs(argv: string[]): ReviewRequest | { help: true } {
	const result: ReviewRequest = {
		cwd: process.cwd(),
		inspectTools: false,
		profile: DEFAULT_PROFILE,
	};
	const positional: string[] = [];
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		if (arg === "--help" || arg === "-h") return { help: true };
		if (arg === "--") {
			positional.push(...argv.slice(i + 1));
			break;
		}
		if (arg === "--profile") result.profile = valueAfter(argv, i++);
		else if (arg === "--model") result.model = valueAfter(argv, i++);
		else if (arg === "--thinking") result.thinking = valueAfter(argv, i++);
		// The host process runs elsewhere; pin the review root to this invocation.
		else if (arg === "--cwd") result.cwd = resolve(valueAfter(argv, i++));
		else if (arg === "--brief") result.brief = valueAfter(argv, i++);
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

export function resolveReviewSelection(options: {
	profile: string;
	model?: string;
	thinking?: string;
	agentDir: string;
	thinkingEfforts: readonly string[];
}): ReviewSelection {
	const profiles = loadProfiles();
	const errors = validateProfilesFile(profiles);
	if (errors.length > 0) fail(`Invalid profiles:\n${errors.join("\n")}`);
	const resolved = resolveProfile(
		profiles,
		loadState(options.agentDir),
		options.profile,
	);
	if (!options.model && resolved.runner !== "omp") {
		fail(
			`Profile "${options.profile}" uses the ${resolved.runner} runner; ` +
				"the restricted reviewer requires an OMP provider/model (override with --model PROVIDER/ID and --thinking LEVEL)",
		);
	}
	const model = options.model ?? `${resolved.provider}/${resolved.model}`;
	if (!model.includes("/") || model.startsWith("/") || model.endsWith("/")) {
		fail(`--model must be an exact PROVIDER/ID selector, got "${model}"`);
	}
	const thinkingText = options.thinking ?? resolved.effort;
	if (thinkingText === null) {
		fail(
			`Profile "${options.profile}" has no effort selector; supply --thinking LEVEL for the OMP model`,
		);
	}
	// The same selectors as `omp --thinking`, minus `inherit`; exact spelling only.
	const levels = ["off", ...options.thinkingEfforts, "auto"];
	if (!levels.includes(thinkingText)) {
		fail(
			`Unknown thinking level "${thinkingText}". Supported values: ${levels.join(", ")}`,
		);
	}
	return {
		profile: options.profile,
		model,
		thinking: thinkingText as ReviewThinkingLevel,
		effortSource: options.thinking ? "command-line" : resolved.effortSource,
	};
}

/**
 * Build the fail-closed SDK boundary. OMP treats restrictToolNames as
 * authoritative: it suppresses extension factories/custom tools, MCP, IRC,
 * eval preludes, memory tools, and discovered extras before registry assembly.
 */
export function buildRestrictedReviewSessionOptions(
	sdk: ReviewRuntime["sdk"],
	options: {
		cwd: string;
		modelPattern?: string;
		thinkingLevel?: ReviewThinkingLevel;
		agentDir?: string;
		settings?: Settings;
	},
): CreateAgentSessionOptions {
	return {
		cwd: options.cwd,
		agentDir: options.agentDir,
		settings: options.settings,
		modelPattern: options.modelPattern,
		thinkingLevel:
			options.thinkingLevel as CreateAgentSessionOptions["thinkingLevel"],
		sessionManager: sdk.SessionManager.inMemory(options.cwd),
		agentRegistry: new sdk.AgentRegistry(),
		agentId: "Reviewer",
		agentDisplayName: "restricted-reviewer",
		agentName: "reviewer",
		appendSystemPrompt: REVIEW_SYSTEM_PROMPT,
		toolNames: [...REVIEW_TOOL_NAMES],
		restrictToolNames: true,
		allowRestrictedCustomTools: false,
		customTools: [],
		extensions: [],
		additionalExtensionPaths: [],
		disableExtensionDiscovery: true,
		enableMCP: false,
		enableIrc: false,
		enableLsp: false,
		lspReadOnly: true,
		spawns: "",
		requireYieldTool: false,
		hasUI: false,
		interactivePrompts: false,
		autoApprove: false,
		skipPythonPreflight: true,
	};
}

export function reviewCapabilitySnapshot(
	result: CreateAgentSessionResult,
): ReviewCapabilitySnapshot {
	return {
		enabledTools: result.session.getEnabledToolNames().sort(),
		registeredTools: result.session
			.getAllToolInfos()
			.map((tool) => tool.name)
			.sort(),
		mountedTools: result.session.getMountedXdevToolNames().sort(),
		evalBridgeTools: result.session.getEvalBridgeToolNames().sort(),
		extensions: result.extensionsResult.extensions
			.map((extension) => extension.path)
			.sort(),
		mcpEnabled: result.mcpManager !== undefined,
	};
}

export function assertRestrictedReviewCapabilities(
	snapshot: ReviewCapabilitySnapshot,
): void {
	const expected = [...REVIEW_TOOL_NAMES].sort();
	for (const [label, actual] of [
		["enabled", snapshot.enabledTools],
		["registered", snapshot.registeredTools],
		// The SDK advertises enabled names here even when eval itself is unavailable.
		["eval-bridge", snapshot.evalBridgeTools],
	] as const) {
		if (
			actual.length !== expected.length ||
			actual.some((name, index) => name !== expected[index])
		) {
			fail(
				`Restricted reviewer ${label} tools changed: expected ${expected.join(", ")}; got ${actual.join(", ")}`,
			);
		}
	}
	if (snapshot.mountedTools.length > 0)
		fail(
			`Restricted reviewer mounted tools: ${snapshot.mountedTools.join(", ")}`,
		);
	if (snapshot.extensions.length > 0)
		fail(
			`Restricted reviewer loaded extensions: ${snapshot.extensions.join(", ")}`,
		);
	if (snapshot.mcpEnabled)
		fail("Restricted reviewer unexpectedly initialized MCP");
}

async function initializeReviewExtensions(
	runtime: ReviewRuntime,
	session: AgentSession,
): Promise<void> {
	await runtime.initializeExtensions(session, {
		mode: "print",
		reportSendError: (action, error) => {
			process.stderr.write(
				`Reviewer extension ${action} failed: ${error.message}\n`,
			);
		},
		reportRuntimeError: (error) => {
			process.stderr.write(
				`Reviewer extension error (${error.extensionPath}): ${error.error}\n`,
			);
		},
	});
}

async function createRestrictedReviewSession(
	runtime: ReviewRuntime,
	options: { cwd: string; selection: ReviewSelection; agentDir: string },
): Promise<{
	result: CreateAgentSessionResult;
	capabilities: ReviewCapabilitySnapshot;
}> {
	const settings = await runtime.sdk.Settings.loadIsolated({
		cwd: options.cwd,
		agentDir: options.agentDir,
		readOnly: true,
		overrides: { "compaction.methodOrder": ["remote", "handoff", "soft"] },
	});
	const result = await runtime.sdk.createAgentSession(
		buildRestrictedReviewSessionOptions(runtime.sdk, {
			cwd: options.cwd,
			agentDir: options.agentDir,
			settings,
			modelPattern: options.selection.model,
			thinkingLevel: options.selection.thinking,
		}),
	);
	try {
		const model = result.session.model;
		const actual = model ? `${model.provider}/${model.id}` : undefined;
		if (actual !== options.selection.model) {
			fail(
				`Reviewer requires exact model "${options.selection.model}"; SDK selected "${actual ?? "none"}"`,
			);
		}
		await initializeReviewExtensions(runtime, result.session);
		const capabilities = reviewCapabilitySnapshot(result);
		assertRestrictedReviewCapabilities(capabilities);
		return { result, capabilities };
	} catch (error) {
		await result.session.dispose();
		throw error;
	}
}

async function reviewOnce(
	runtime: ReviewRuntime,
	session: AgentSession,
	brief: string,
): Promise<string> {
	const unsubscribe = session.subscribe(() => {});
	try {
		const started = await session.prompt(`Review brief:\n${brief.trim()}`);
		if (!started) fail("The review brief did not start a model turn");
		const message = session.getLastAssistantMessage();
		if (!message) fail("The reviewer returned no assistant message");
		if (message.stopReason === "error" || message.stopReason === "aborted") {
			fail(message.errorMessage || `Review request ${message.stopReason}`);
		}
		const output = message.content
			.filter((content) => content.type === "text")
			.map((content) => content.text)
			.join("\n")
			.trim();
		if (!output) fail("The reviewer returned no text output");
		return runtime.sanitizeText(output);
	} finally {
		unsubscribe();
	}
}

/**
 * Settings exposes no public key getter; report the runtime override layer,
 * which outranks global, project, and overlay values.
 */
function runtimeCompactionMethodOrder(settings: unknown): unknown {
	if (
		typeof settings !== "object" ||
		settings === null ||
		!("overlayLayers" in settings) ||
		typeof settings.overlayLayers !== "function"
	) {
		fail("Reviewer settings do not expose overlayLayers()");
	}
	const layers: unknown = settings.overlayLayers();
	if (
		typeof layers !== "object" ||
		layers === null ||
		!("overrides" in layers)
	) {
		fail("Reviewer settings overlay has no runtime overrides");
	}
	const { overrides } = layers;
	if (typeof overrides !== "object" || overrides === null) return undefined;
	const compaction = "compaction" in overrides ? overrides.compaction : undefined;
	if (typeof compaction !== "object" || compaction === null) return undefined;
	return "methodOrder" in compaction ? compaction.methodOrder : undefined;
}

/** Run one request with the SDK of the current omp process; returns the stdout text. */
export async function runReview(
	request: ReviewRequest,
	runtime: ReviewRuntime,
): Promise<string> {
	const agentDir = runtime.sdk.getAgentDir();
	const selection = resolveReviewSelection({
		profile: request.profile,
		model: request.model,
		thinking: request.thinking,
		agentDir,
		thinkingEfforts: runtime.thinkingEfforts,
	});
	const { result, capabilities } = await createRestrictedReviewSession(
		runtime,
		{ cwd: request.cwd, selection, agentDir },
	);
	try {
		if (request.inspectTools) {
			return JSON.stringify(
				{
					profile: selection.profile,
					model: selection.model,
					thinking: result.session.thinkingLevel ?? selection.thinking,
					effortSource: selection.effortSource,
					compactionMethodOrder: runtimeCompactionMethodOrder(
						result.session.settings,
					),
					...capabilities,
				},
				null,
				2,
			);
		}
		if (!request.brief) fail("A non-empty review brief is required");
		return await reviewOnce(runtime, result.session, request.brief);
	} finally {
		await result.session.dispose();
	}
}

/**
 * Host side of the launcher protocol: read the request, write exactly one
 * result, and return the process exit code. Never throws.
 */
export async function runHostedReview(
	ipcDir: string,
	runtime: ReviewRuntime,
): Promise<number> {
	let result: HostResult;
	try {
		const request = JSON.parse(
			await readFile(join(ipcDir, REQUEST_FILE), "utf8"),
		) as ReviewRequest;
		result = { output: await runReview(request, runtime) };
	} catch (error) {
		result = { error: errorMessage(error) };
	}
	try {
		await writeFile(join(ipcDir, RESULT_FILE), JSON.stringify(result), {
			mode: 0o600,
		});
	} catch (error) {
		process.stderr.write(
			`Reviewer host could not write its result: ${errorMessage(error)}\n`,
		);
		return 1;
	}
	return "output" in result ? 0 : 1;
}

/**
 * Run the request inside the PATH `omp` executable. A Bun-side SDK import would
 * bind to whatever package files sit beside that executable, which need not be
 * the runtime `omp` itself executes (a compiled binary embeds its own SDK).
 */
async function runInOmpHost(request: ReviewRequest): Promise<string> {
	const omp = Bun.which("omp");
	if (!omp)
		fail("The restricted reviewer requires an installed omp executable");
	const ipcDir = await mkdtemp(join(tmpdir(), "harness-review-"));
	try {
		await writeFile(join(ipcDir, REQUEST_FILE), JSON.stringify(request), {
			mode: 0o600,
		});
		// The host omp loads only review-host.ts, which reviews and exits before
		// omp would create its own session (ambient custom tools, MCP).
		const host = Bun.spawn(
			[
				omp,
				"--mode",
				"rpc",
				"--no-session",
				"--no-extensions",
				"--no-skills",
				"--no-rules",
				"--no-lsp",
				"--no-tools",
				"--no-title",
				// Exact module only, no package-root discovery; a load failure
				// aborts omp instead of continuing to its session.
				"--trusted-extension",
				HOST_EXTENSION_PATH,
			],
			{
				cwd: ipcDir,
				env: { ...process.env, [REVIEW_IPC_ENV]: ipcDir },
				// RPC mode owns stdin; keep it open. review-host.ts exits on its own
				// when this launcher disappears.
				stdin: "pipe",
				stdout: "ignore",
				// omp prints a "Still starting" notice every 10 s while the review
				// runs inside its startup; show host stderr only on failure.
				stderr: "pipe",
			},
		);
		const hostStderr = new Response(host.stderr).text();
		// Stop the reviewer turn with the launcher rather than finishing it unseen.
		const stop = () => host.kill("SIGTERM");
		const signals = ["SIGINT", "SIGTERM", "SIGHUP"] as const;
		for (const signal of signals) process.on(signal, stop);
		let exitCode: number;
		try {
			exitCode = await host.exited;
		} finally {
			for (const signal of signals) process.off(signal, stop);
		}
		let result: unknown;
		try {
			result = JSON.parse(await readFile(join(ipcDir, RESULT_FILE), "utf8"));
		} catch {
			result = undefined;
		}
		const record = typeof result === "object" && result !== null ? result : {};
		const output =
			"output" in record && typeof record.output === "string"
				? record.output
				: undefined;
		if (output !== undefined && exitCode === 0) return output;
		process.stderr.write(await hostStderr);
		if ("error" in record && typeof record.error === "string")
			fail(record.error);
		if (result === undefined)
			fail(`Reviewer host exited with code ${exitCode} without a result`);
		if (output === undefined) fail("Reviewer host wrote a malformed result");
		fail(`Reviewer host exited with code ${exitCode} after reporting success`);
	} finally {
		await rm(ipcDir, { recursive: true, force: true });
	}
}

async function main(): Promise<void> {
	const parsed = parseReviewArgs(process.argv.slice(2));
	if ("help" in parsed) {
		process.stdout.write(`${usage()}\n`);
		return;
	}
	process.stdout.write(`${await runInOmpHost(parsed)}\n`);
}

if (import.meta.main) {
	main().catch((error) => {
		process.stderr.write(`${errorMessage(error)}\n`);
		process.exitCode = 1;
	});
}
