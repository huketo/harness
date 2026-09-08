#!/usr/bin/env bun
import type {
	AgentSession,
	CreateAgentSessionOptions,
	CreateAgentSessionResult,
	Settings,
} from "@oh-my-pi/pi-coding-agent";
import type { ConfiguredThinkingLevel } from "@oh-my-pi/pi-coding-agent/thinking";
import {
	loadProfiles,
	loadState,
	type ResolvedProfile,
	resolveProfile,
	validateProfilesFile,
} from "./extensions/profiles/schema";
import { runtime, sdk, thinking, utils } from "./review-sdk";

const { AgentRegistry, createAgentSession, getAgentDir, SessionManager } = sdk;
const { initializeExtensions } = runtime;
const { CLI_THINKING_LEVELS, parseCliThinkingLevel } = thinking;
const { sanitizeText } = utils;

export const REVIEW_TOOL_NAMES = ["read", "grep", "glob"] as const;
const DEFAULT_PROFILE = "best";

const REVIEW_SYSTEM_PROMPT = `You are a capability-restricted code reviewer. Find concrete bugs introduced by the change described in the review brief. Inspect the named repository files and artifacts, trace values across producer/consumer boundaries, and report only actionable findings with provable impact. For each finding give severity, path, and the narrowest relevant line range. If there are no findings, say so plainly. Do not ask a human or attempt any mutation; put unresolved questions in the review output.`;

export interface ReviewSelection {
	profile: string;
	model: string;
	thinking: ConfiguredThinkingLevel;
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

interface CliOptions {
	brief?: string;
	cwd: string;
	inspectTools: boolean;
	model?: string;
	profile: string;
	thinking?: string;
}

function fail(message: string): never {
	throw new Error(message);
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
		"  --model PROVIDER/ID  Override only the profile model; keep its resolved effort",
		"  --thinking LEVEL     Override profile effort using OMP's native thinking selector",
		"  --cwd DIR            Repository root to review (default: current directory)",
		"  --brief TEXT         Review assignment; positional text after -- is also accepted",
		"  --inspect-tools      Build and initialize the real session, print capabilities, do not call a model",
		"  --help               Show this help",
	].join("\n");
}

export function parseReviewArgs(argv: string[]): CliOptions | { help: true } {
	const result: CliOptions = {
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
		else if (arg === "--cwd") result.cwd = valueAfter(argv, i++);
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
	agentDir?: string;
}): ReviewSelection {
	const profiles = loadProfiles();
	const errors = validateProfilesFile(profiles);
	if (errors.length > 0) fail(`Invalid profiles:\n${errors.join("\n")}`);
	const resolved = resolveProfile(
		profiles,
		loadState(options.agentDir ?? getAgentDir()),
		options.profile,
	);
	if (!options.model && resolved.runner !== "omp") {
		fail(
			`Profile "${options.profile}" uses the ${resolved.runner} runner; ` +
				"the restricted reviewer requires an OMP provider/model (or an explicit --model PROVIDER/ID)",
		);
	}
	const model = options.model ?? `${resolved.provider}/${resolved.model}`;
	if (!model.includes("/") || model.startsWith("/") || model.endsWith("/")) {
		fail(`--model must be an exact PROVIDER/ID selector, got "${model}"`);
	}
	const thinkingText = options.thinking ?? resolved.effort;
	const thinking = parseCliThinkingLevel(thinkingText);
	if (!thinking) {
		fail(
			`Unknown thinking level "${thinkingText}". Supported values: ${CLI_THINKING_LEVELS.join(", ")}`,
		);
	}
	return {
		profile: options.profile,
		model,
		thinking,
		effortSource: options.thinking ? "command-line" : resolved.effortSource,
	};
}

/**
 * Build the fail-closed SDK boundary. OMP 18.1.14 treats restrictToolNames as
 * authoritative: it suppresses extension factories/custom tools, MCP, IRC,
 * eval preludes, memory tools, and discovered extras before registry assembly.
 */
export function buildRestrictedReviewSessionOptions(options: {
	cwd: string;
	modelPattern?: string;
	thinkingLevel?: ConfiguredThinkingLevel;
	agentDir?: string;
	settings?: Settings;
}): CreateAgentSessionOptions {
	return {
		cwd: options.cwd,
		agentDir: options.agentDir,
		settings: options.settings,
		modelPattern: options.modelPattern,
		thinkingLevel: options.thinkingLevel,
		sessionManager: SessionManager.inMemory(options.cwd),
		agentRegistry: new AgentRegistry(),
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
	result: CreateAgentSessionResult,
): ReviewCapabilitySnapshot {
	const snapshot = reviewCapabilitySnapshot(result);
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
	return snapshot;
}

export async function initializeReviewExtensions(
	session: AgentSession,
): Promise<void> {
	await initializeExtensions(session, {
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

export async function createRestrictedReviewSession(options: {
	cwd: string;
	selection: ReviewSelection;
	agentDir?: string;
}): Promise<{
	result: CreateAgentSessionResult;
	capabilities: ReviewCapabilitySnapshot;
}> {
	const agentDir = options.agentDir ?? getAgentDir();
	const settings = await sdk.Settings.loadIsolated({
		cwd: options.cwd,
		agentDir,
		readOnly: true,
		overrides: { "compaction.methodOrder": ["remote", "handoff", "soft"] },
	});
	const result = await createAgentSession(
		buildRestrictedReviewSessionOptions({
			cwd: options.cwd,
			agentDir,
			settings,
			modelPattern: options.selection.model,
			thinkingLevel: options.selection.thinking,
		}),
	);
	try {
		await initializeReviewExtensions(result.session);
		const capabilities = assertRestrictedReviewCapabilities(result);
		return { result, capabilities };
	} catch (error) {
		await result.session.dispose();
		throw error;
	}
}

export async function reviewOnce(
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
		return sanitizeText(output);
	} finally {
		unsubscribe();
	}
}

async function main(): Promise<void> {
	const parsed = parseReviewArgs(process.argv.slice(2));
	if ("help" in parsed) {
		process.stdout.write(`${usage()}\n`);
		return;
	}
	const selection = resolveReviewSelection({
		profile: parsed.profile,
		model: parsed.model,
		thinking: parsed.thinking,
	});
	const { result, capabilities } = await createRestrictedReviewSession({
		cwd: parsed.cwd,
		selection,
	});
	try {
		if (parsed.inspectTools) {
			process.stdout.write(
				`${JSON.stringify(
					{
						profile: selection.profile,
						model: result.session.model
							? `${result.session.model.provider}/${result.session.model.id}`
							: selection.model,
						thinking: result.session.thinkingLevel ?? selection.thinking,
						effortSource: selection.effortSource,
						compactionMethodOrder: result.session.settings.get(
							"compaction.methodOrder",
						),
						...capabilities,
					},
					null,
					2,
				)}\n`,
			);
			return;
		}
		if (!parsed.brief) fail("A non-empty review brief is required");
		process.stdout.write(`${await reviewOnce(result.session, parsed.brief)}\n`);
	} finally {
		await result.session.dispose();
	}
}

if (import.meta.main) {
	main().catch((error) => {
		process.stderr.write(
			`${error instanceof Error ? error.message : String(error)}\n`,
		);
		process.exitCode = 1;
	});
}
