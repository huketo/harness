import { expect, test } from "bun:test";
import type { FetchImpl, Message, Model, Tool } from "@oh-my-pi/pi-ai";
import {
	ANTHROPIC_COMPACTION_BETA,
	ANTHROPIC_COMPACTION_TRIGGER_TOKENS,
	compactAnthropic,
} from "./anthropic";
import type { NativeRequest, NativeWindow } from "./types";

const model = {
	id: "claude-opus-5",
	requestModelId: "claude-opus-5",
	name: "Claude Opus 5",
	api: "anthropic-messages",
	provider: "anthropic",
	baseUrl: "https://anthropic.example.test",
	reasoning: true,
	input: ["text", "image"],
	cost: { input: 5, output: 25, cacheRead: 0.5, cacheWrite: 6.25 },
	contextWindow: 1_000_000,
	maxTokens: 4096,
	identity: { class: "anthropic", family: "opus", revision: "5.0.0" },
	compat: {
		officialEndpoint: true,
		signingEndpoint: true,
		supportsContextManagement: true,
		supportsOutputEffort: true,
		disableStrictTools: false,
		disableAdaptiveThinking: false,
		allowAnthropicHeaderOverrides: false,
		supportsEagerToolInputStreaming: true,
		supportsLongCacheRetention: true,
		supportsMidConversationSystem: true,
		supportsTurnScopedSystem: true,
		supportsMidConversationToolChanges: true,
		supportsPerMessageEffort: false,
		supportsThinkingBindingControls: false,
		supportsForcedToolChoice: true,
		supportsSamplingParams: false,
		requiresToolResultId: false,
		requiresThinkingEnabled: false,
		replayUnsignedThinking: false,
		escapeBuiltinToolNames: false,
		injectClaudeCodeInstruction: true,
		stripImageInput: false,
	},
} as unknown as Model<"anthropic-messages">;

const messages: Message[] = [
	{
		role: "user",
		content: [{ type: "text", text: "Inspect the repository." }],
		timestamp: 1,
	},
	{
		role: "assistant",
		api: "anthropic-messages",
		provider: "anthropic",
		model: "claude-opus-5",
		content: [
			{
				type: "toolCall",
				id: "call-1",
				name: "inspect",
				arguments: { path: "src/app.ts" },
			},
		],
		usage: {
			input: 1,
			output: 1,
			cacheRead: 0,
			cacheWrite: 0,
			totalTokens: 2,
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
		},
		stopReason: "toolUse",
		timestamp: 2,
	},
	{
		role: "toolResult",
		toolCallId: "call-1",
		toolName: "inspect",
		content: [{ type: "text", text: "export const answer = 42;" }],
		isError: false,
		timestamp: 3,
	},
	{
		role: "user",
		content: [{ type: "text", text: "Continue with that result." }],
		timestamp: 4,
	},
];

const tools: Tool[] = [
	{
		name: "inspect",
		description: "Read a source file",
		parameters: {
			type: "object",
			properties: { path: { type: "string" } },
			required: ["path"],
			additionalProperties: false,
		},
	},
];

function request(
	fetch: FetchImpl,
	options: Partial<NativeRequest> = {},
): NativeRequest {
	return {
		model,
		context: {
			systemPrompt: ["Keep implementation details exact."],
			messages,
			tools,
		},
		apiKey: "fake-api-key",
		sessionId: "session-1",
		instructions: "Preserve decisions, paths, and outstanding work.",
		fetch,
		...options,
	};
}

function jsonResponse(value: unknown, status = 200): Response {
	return new Response(JSON.stringify(value), {
		status,
		headers: { "content-type": "application/json" },
	});
}

test("uses Anthropic's native compact beta and preserves replay blocks, tool pairs, schemas, response blocks, and complete usage", async () => {
	let url = "";
	let init: RequestInit | undefined;
	const block = {
		type: "compaction",
		content: "The repository inspection found answer = 42.",
		cache_control: { type: "ephemeral" },
		provider_extension: { version: 1 },
	};
	const usage = {
		input_tokens: 9000,
		output_tokens: 700,
		cache_read_input_tokens: 41000,
		cache_creation_input_tokens: 0,
		iterations: [
			{
				type: "compaction",
				input_tokens: 52_000,
				output_tokens: 650,
			},
			{ type: "message", input_tokens: 9000, output_tokens: 50 },
		],
	};
	const fetch: FetchImpl = async (input, requestInit) => {
		url = String(input);
		init = requestInit;
		return jsonResponse({
			id: "msg_compacted",
			type: "message",
			role: "assistant",
			model: "claude-opus-5",
			content: [block],
			stop_reason: "compaction",
			usage,
		});
	};
	const previousBlock = {
		role: "assistant",
		content: [{ type: "compaction", content: "Earlier compacted state." }],
	};
	const previous: NativeWindow = {
		provider: "anthropic",
		model: "claude-opus-5",
		format: "anthropic-messages",
		items: [previousBlock],
	};

	const window = await compactAnthropic(request(fetch, { previous }));

	expect(url).toBe("https://anthropic.example.test/v1/messages?beta=true");
	const headers = new Headers(init?.headers);
	expect(headers.get("anthropic-beta")?.split(",")).toContain(
		ANTHROPIC_COMPACTION_BETA,
	);
	expect(headers.get("accept")).toBe("application/json");
	const body = JSON.parse(String(init?.body));
	expect(body.model).toBe("claude-opus-5");
	expect(body.stream).toBe(false);
	expect(body.context_management).toEqual({
		edits: [
			{
				type: "compact_20260112",
				trigger: {
					type: "input_tokens",
					value: ANTHROPIC_COMPACTION_TRIGGER_TOKENS,
				},
				pause_after_compaction: true,
				instructions:
					"Preserve decisions, paths, and outstanding work.\n\nDo not call any tools while writing this summary; respond with text only.",
			},
		],
	});
	expect(body.messages[0]).toEqual(previousBlock);
	expect(body.messages).toContainEqual({
		role: "assistant",
		content: [
			{
				type: "tool_use",
				id: "call-1",
				name: "inspect",
				input: { path: "src/app.ts" },
			},
		],
	});
	expect(body.messages).toContainEqual({
		role: "user",
		content: [
			{
				type: "tool_result",
				tool_use_id: "call-1",
				content: [{ type: "text", text: "export const answer = 42;" }],
				is_error: false,
			},
		],
	});
	expect(body.tools).toEqual([
		{
			name: "inspect",
			description: "Read a source file",
			input_schema: {
				type: "object",
				properties: { path: { type: "string" } },
				required: ["path"],
				additionalProperties: false,
			},
		},
	]);
	expect(window.items).toEqual([{ role: "assistant", content: [block] }]);
	expect(window.usage).toEqual(usage);
});

test("does not replay a native window from a different provider", async () => {
	let body: Record<string, unknown> | undefined;
	const fetch: FetchImpl = async (_input, init) => {
		body = JSON.parse(String(init?.body));
		return jsonResponse({
			content: [{ type: "compaction", content: "Fresh summary." }],
			stop_reason: "compaction",
			usage: { input_tokens: 51_000, output_tokens: 100, iterations: [] },
		});
	};
	await compactAnthropic(
		request(fetch, {
			previous: {
				provider: "other",
				model: "claude-opus-5",
				format: "anthropic-messages",
				items: [
					{
						role: "assistant",
						content: [{ type: "compaction", content: "Do not replay." }],
					},
				],
			},
		}),
	);
	expect(JSON.stringify(body)).not.toContain("Do not replay.");
});

test("rejects a null compaction summary instead of treating it as valid state", async () => {
	const fetch: FetchImpl = async () =>
		jsonResponse({
			content: [{ type: "compaction", content: null }],
			stop_reason: "compaction",
			usage: {
				input_tokens: 51_000,
				output_tokens: 10,
				iterations: [
					{ type: "compaction", input_tokens: 51_000, output_tokens: 10 },
				],
			},
		});
	await expect(compactAnthropic(request(fetch))).rejects.toThrow(
		/null summary/i,
	);
});

test("reports that short input cannot compact without fabricating padding", async () => {
	const fetch: FetchImpl = async () =>
		jsonResponse({
			content: [{ type: "text", text: "Ordinary assistant response" }],
			stop_reason: "end_turn",
			usage: {
				input_tokens: 120,
				output_tokens: 8,
				iterations: [{ type: "message", input_tokens: 120, output_tokens: 8 }],
			},
		});
	await expect(compactAnthropic(request(fetch))).rejects.toThrow(
		/below the 50,000-token trigger \(120 input tokens\)/i,
	);
});

test("rejects missing compaction blocks and wrong stop reasons", async () => {
	const missing: FetchImpl = async () =>
		jsonResponse({
			content: [{ type: "text", text: "not a summary" }],
			stop_reason: "compaction",
			usage: { input_tokens: 55_000, output_tokens: 12, iterations: [] },
		});
	await expect(compactAnthropic(request(missing))).rejects.toThrow(
		/0 compaction blocks/i,
	);

	const wrongStop: FetchImpl = async () =>
		jsonResponse({
			content: [{ type: "compaction", content: "Summary" }],
			stop_reason: "end_turn",
			usage: { input_tokens: 55_000, output_tokens: 12, iterations: [] },
		});
	await expect(compactAnthropic(request(wrongStop))).rejects.toThrow(
		/stop_reason "end_turn" instead of "compaction"/i,
	);
});

test("surfaces Anthropic HTTP errors", async () => {
	const fetch: FetchImpl = async () =>
		jsonResponse(
			{
				type: "error",
				error: { type: "invalid_request_error", message: "bad request" },
			},
			400,
		);
	await expect(compactAnthropic(request(fetch))).rejects.toThrow(
		/400.*bad request/i,
	);
});

test("propagates cancellation through the real Anthropic HTTP transport", async () => {
	const controller = new AbortController();
	let started!: () => void;
	const didStart = new Promise<void>((resolve) => {
		started = resolve;
	});
	const fetch: FetchImpl = async (_input, init) => {
		started();
		return new Promise<Response>((_resolve, reject) => {
			const signal = init?.signal;
			if (!signal) {
				reject(
					new Error(
						"Expected the Anthropic client to forward an abort signal.",
					),
				);
				return;
			}
			signal.addEventListener(
				"abort",
				() => reject(new DOMException("Aborted", "AbortError")),
				{ once: true },
			);
		});
	};
	const pending = compactAnthropic(
		request(fetch, { signal: controller.signal }),
	);
	await didStart;
	controller.abort();
	await expect(pending).rejects.toThrow(/aborted/i);
});
