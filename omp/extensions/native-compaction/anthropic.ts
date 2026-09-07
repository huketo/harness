import type { Model, Tool } from "@oh-my-pi/pi-ai";
import type * as AnthropicProvider from "@oh-my-pi/pi-ai/providers/anthropic";
import type { AnthropicMessagesClient as AnthropicMessagesClientType } from "@oh-my-pi/pi-ai/providers/anthropic-client";
import type { MessageCreateParams } from "@oh-my-pi/pi-ai/providers/anthropic-wire";
import type * as Schema from "@oh-my-pi/pi-ai/utils/schema";
import { loadOmp } from "./runtime";
import type { NativeRequest, NativeWindow } from "./types";

/** Normal Anthropic requests replaying a compaction block must include this beta. */
export const ANTHROPIC_COMPACTION_BETA = "compact-2026-01-12";
export const ANTHROPIC_COMPACTION_TRIGGER_TOKENS = 50_000;

const NO_TOOLS_INSTRUCTION =
	"Do not call any tools while writing this summary; respond with text only.";

type AnthropicModel = Model<"anthropic-messages">;
type WireMessage = AnthropicProvider.AnthropicMessageParam;
type WireTool = {
	name: string;
	description: string;
	input_schema: Record<string, unknown>;
	defer_loading?: boolean;
};
type CompactResponse = {
	content?: unknown;
	stop_reason?: unknown;
	usage?: unknown;
};

function firstUserText(messages: readonly WireMessage[]): string {
	for (const message of messages) {
		if (message.role !== "user") continue;
		if (typeof message.content === "string") return message.content;
		for (const block of message.content) {
			if (block.type === "text") return block.text;
		}
	}
	return "";
}

function prependPreviousWindow(
	request: NativeRequest,
	messages: WireMessage[],
): WireMessage[] {
	const previous = request.previous;
	if (
		!previous ||
		previous.provider !== request.model.provider ||
		previous.format !== "anthropic-messages"
	) {
		return messages;
	}
	return [...(previous.items as WireMessage[]), ...messages];
}

async function buildTools(
	tools: readonly Tool[] | undefined,
	isOAuthToken: boolean,
	model: AnthropicModel,
	provider: typeof AnthropicProvider,
): Promise<WireTool[] | undefined> {
	if (!tools) return isOAuthToken ? [] : undefined;
	const { toolWireSchema } = await loadOmp<typeof Schema>(
		"@oh-my-pi/pi-ai/utils/schema",
	);
	return tools.map((tool) => {
		const wireSchema = toolWireSchema(tool);
		const inputSchema = provider.normalizeAnthropicToolSchema({
			...wireSchema,
			type: "object",
			properties:
				typeof wireSchema.properties === "object" &&
				wireSchema.properties !== null &&
				!Array.isArray(wireSchema.properties)
					? wireSchema.properties
					: {},
			required: Array.isArray(wireSchema.required)
				? wireSchema.required.filter(
						(entry): entry is string => typeof entry === "string",
					)
				: [],
		}) as Record<string, unknown>;
		const name =
			isOAuthToken || model.compat.escapeBuiltinToolNames
				? provider.applyClaudeToolPrefix(tool.name)
				: tool.name;
		return {
			name,
			description: tool.description || "",
			input_schema: inputSchema,
			...(tool.deferLoading ? { defer_loading: true } : {}),
		};
	});
}

function compactionInstructions(instructions: string): string {
	const requested = instructions.trim();
	return requested
		? `${requested}\n\n${NO_TOOLS_INSTRUCTION}`
		: NO_TOOLS_INSTRUCTION;
}

function parseCompactResponse(
	value: unknown,
	model: AnthropicModel,
): NativeWindow {
	if (typeof value !== "object" || value === null || Array.isArray(value)) {
		throw new Error(
			"Anthropic native compaction returned an invalid response.",
		);
	}
	const response = value as CompactResponse;
	if (response.stop_reason !== "compaction") {
		const usage =
			typeof response.usage === "object" &&
			response.usage !== null &&
			!Array.isArray(response.usage)
				? (response.usage as Record<string, unknown>)
				: undefined;
		const inputBuckets = usage
			? [
					usage.input_tokens,
					usage.cache_read_input_tokens,
					usage.cache_creation_input_tokens,
				]
			: [];
		const inputTokens =
			inputBuckets.some((tokens) => typeof tokens === "number") &&
			inputBuckets.every(
				(tokens) => tokens === undefined || typeof tokens === "number",
			)
				? inputBuckets.reduce<number>(
						(total, tokens) =>
							total + (typeof tokens === "number" ? tokens : 0),
						0,
					)
				: undefined;
		if (
			typeof inputTokens === "number" &&
			inputTokens < ANTHROPIC_COMPACTION_TRIGGER_TOKENS
		) {
			throw new Error(
				`Anthropic native compaction did not run because the input is below the ${ANTHROPIC_COMPACTION_TRIGGER_TOKENS.toLocaleString("en-US")}-token trigger (${inputTokens.toLocaleString("en-US")} input tokens).`,
			);
		}
		throw new Error(
			`Anthropic native compaction returned stop_reason ${JSON.stringify(response.stop_reason)} instead of "compaction".`,
		);
	}
	if (!Array.isArray(response.content)) {
		throw new Error("Anthropic native compaction returned missing content.");
	}
	const blocks = response.content.filter(
		(block): block is Record<string, unknown> =>
			typeof block === "object" &&
			block !== null &&
			!Array.isArray(block) &&
			(block as Record<string, unknown>).type === "compaction",
	);
	if (blocks.length !== 1) {
		throw new Error(
			`Anthropic native compaction returned ${blocks.length} compaction blocks; expected exactly one.`,
		);
	}
	const block = blocks[0];
	if (block.content === null) {
		throw new Error(
			"Anthropic native compaction returned a null summary instead of a compaction block payload.",
		);
	}
	if (typeof block.content !== "string" || block.content.length === 0) {
		throw new Error(
			"Anthropic native compaction returned a compaction block without a readable summary.",
		);
	}
	if (
		typeof response.usage !== "object" ||
		response.usage === null ||
		Array.isArray(response.usage)
	) {
		throw new Error("Anthropic native compaction returned missing usage.");
	}
	return {
		provider: model.provider,
		model: model.id,
		format: "anthropic-messages",
		contextWindow: model.contextWindow ?? undefined,
		items: [{ role: "assistant", content: [block] }],
		summary: block.content,
		usage: response.usage as Record<string, unknown>,
	};
}

export async function compactAnthropic(
	request: NativeRequest,
): Promise<NativeWindow> {
	if (request.model.api !== "anthropic-messages") {
		throw new Error(
			`Anthropic native compaction requires anthropic-messages, received ${request.model.api}.`,
		);
	}
	if (request.signal?.aborted) {
		throw new Error("Anthropic native compaction was aborted.");
	}

	const model = request.model as AnthropicModel;
	const [provider, clientModule] = await Promise.all([
		loadOmp<typeof AnthropicProvider>("@oh-my-pi/pi-ai/providers/anthropic"),
		loadOmp<{
			AnthropicMessagesClient: typeof AnthropicMessagesClientType;
		}>("@oh-my-pi/pi-ai/providers/anthropic-client"),
	]);
	const clientOptions = provider.buildAnthropicClientOptions({
		model,
		apiKey: request.apiKey,
		extraBetas: [ANTHROPIC_COMPACTION_BETA],
		stream: false,
		interleavedThinking: false,
		hasTools: !!request.context.tools?.length,
		thinkingEnabled: false,
		fetch: request.fetch,
		sessionId: request.sessionId,
	});
	const { isOAuthToken, ...transportOptions } = clientOptions;
	const serialized = provider.convertAnthropicMessages(
		request.context.messages,
		model,
		isOAuthToken,
	);
	const messages = prependPreviousWindow(request, serialized);
	const system = provider.buildAnthropicSystemBlocks(
		request.context.systemPrompt,
		{
			includeClaudeCodeInstruction:
				isOAuthToken && model.compat.injectClaudeCodeInstruction !== false,
			firstUserMessageText: firstUserText(messages),
		},
	);
	const tools = await buildTools(
		request.context.tools,
		isOAuthToken,
		model,
		provider,
	);
	const metadataUserId = provider.resolveAnthropicMetadataUserId(
		undefined,
		isOAuthToken,
		request.sessionId,
	);
	const maxTokens = Math.min(16000, model.maxTokens ?? 16000);
	const params = {
		model: model.requestModelId ?? model.id,
		messages,
		...(system && { system }),
		...(tools !== undefined && { tools }),
		...(metadataUserId && { metadata: { user_id: metadataUserId } }),
		max_tokens: maxTokens,
		context_management: {
			edits: [
				{
					type: "compact_20260112",
					trigger: {
						type: "input_tokens",
						value: ANTHROPIC_COMPACTION_TRIGGER_TOKENS,
					},
					pause_after_compaction: true,
					instructions: compactionInstructions(request.instructions),
				},
			],
		},
		stream: false,
	};
	const client = new clientModule.AnthropicMessagesClient(transportOptions);
	const pending = client.beta.messages.create(
		params as unknown as MessageCreateParams,
		{ signal: request.signal },
	);
	const httpResponse = await pending.asResponse();
	if (request.signal?.aborted) {
		throw new Error("Anthropic native compaction was aborted.");
	}
	const response = await httpResponse.json();
	if (request.signal?.aborted) {
		throw new Error("Anthropic native compaction was aborted.");
	}
	return parseCompactResponse(response, model);
}
