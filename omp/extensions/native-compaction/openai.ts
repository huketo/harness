import type { FetchImpl } from "@oh-my-pi/pi-ai";
import { loadOmp } from "./runtime";
import type { NativeRequest, NativeWindow } from "./types";

interface OpenAiCompactionModule {
	buildOpenAiNativeHistory(
		messages: NativeRequest["context"]["messages"],
		model: NativeRequest["model"],
	): Record<string, unknown>[];
	requestOpenAiRemoteCompaction(
		model: NativeRequest["model"],
		apiKey: string,
		input: Record<string, unknown>[],
		instructions: string,
		signal?: AbortSignal,
		opts?: {
			fetch?: FetchImpl;
			sessionId?: string;
		},
	): Promise<unknown>;
	buildCompactionV2RequestFromBody(
		model: NativeRequest["model"],
		body: CodexCompactionBody,
		options?: {
			sessionId?: string;
			promptCacheKey?: string;
		},
	): CompactionV2Request;
	requestCompactionV2Streaming(
		model: NativeRequest["model"],
		apiKey: string,
		request: CompactionV2Request,
		signal?: AbortSignal,
		options?: {
			fetch?: FetchImpl;
			preferWebsockets?: boolean;
		},
	): Promise<CompactionV2Response>;
}

interface CodexCompactionModule {
	buildTransformedCodexRequestBody(
		model: NativeRequest["model"],
		context: NativeRequest["context"],
		options: {
			sessionId: string;
			responsesLite?: boolean;
		},
		promptCacheKey?: string,
		inputPrefix?: Record<string, unknown>[],
	): Promise<CodexCompactionBody>;
}

interface CodexCompactionBody extends Record<string, unknown> {
	model: string;
	input?: unknown[];
	prompt_cache_key?: string;
}

interface CompactionV2Request {
	body: CodexCompactionBody;
	input: unknown[];
	retainedMessageBudget: number;
	sessionId?: string;
	promptCacheKey?: string;
}

interface CompactionV2Response {
	compactionItem: Record<string, unknown>;
	replacementHistory: Record<string, unknown>[];
	usage?: Record<string, unknown>;
}

function matchingPreviousItems(
	request: NativeRequest,
): Record<string, unknown>[] | undefined {
	const previous = request.previous;
	return previous?.provider === request.model.provider &&
		previous.format === "openai-responses"
		? previous.items
		: undefined;
}

async function compactOpenAICodexV2(
	request: NativeRequest,
	openAi: OpenAiCompactionModule,
): Promise<NativeWindow> {
	const codex = await loadOmp<CodexCompactionModule>(
		"@oh-my-pi/pi-ai/providers/openai-codex-responses",
	);
	const body = await codex.buildTransformedCodexRequestBody(
		request.model,
		{
			...request.context,
			systemPrompt: [
				...(request.context.systemPrompt ?? []),
				request.instructions,
			],
		},
		{
			sessionId: request.sessionId,
			responsesLite: request.model.useResponsesLite,
		},
	);
	const previous = matchingPreviousItems(request) ?? [];
	// Serialize only new messages. The normal Codex serializer sanitizes prefix
	// items; a previously returned native window must bypass that sanitizer.
	const current = (body.input ?? []).map((item) => {
		if (item && typeof item === "object" && !("type" in item) && "role" in item)
			return { type: "message", ...item };
		return item;
	});
	body.input = [...previous, ...current];
	const promptCacheKey =
		typeof body.prompt_cache_key === "string"
			? body.prompt_cache_key
			: undefined;
	const compactRequest = openAi.buildCompactionV2RequestFromBody(
		request.model,
		body,
		{
			sessionId: request.sessionId,
			promptCacheKey,
		},
	);
	const compacted = await openAi.requestCompactionV2Streaming(
		request.model,
		request.apiKey,
		compactRequest,
		request.signal,
		{
			fetch: request.fetch,
			// A dedicated compaction request must stay observable at the injected
			// HTTP boundary and must not attach to a normal-turn WebSocket.
			preferWebsockets: false,
		},
	);
	if (!isEncryptedCompactionItem(compacted.compactionItem)) {
		throw new Error(
			"OpenAI Codex V2 compaction is missing a valid encrypted compaction item.",
		);
	}
	return {
		provider: request.model.provider,
		model: request.model.id,
		format: "openai-responses",
		items: compacted.replacementHistory,
		...(compacted.usage ? { usage: compacted.usage } : {}),
	};
}

function isEncryptedCompactionItem(item: Record<string, unknown>): boolean {
	return (
		item.type === "compaction" &&
		typeof item.encrypted_content === "string" &&
		item.encrypted_content.trim().length > 0
	);
}

/**
 * Compact first-party OpenAI through the standalone endpoint and Codex through
 * its native V2 Responses stream. Both branches return replay-ready native
 * windows and fail rather than falling back to readable local summaries.
 */
export async function compactOpenAI(
	request: NativeRequest,
): Promise<NativeWindow> {
	if (
		request.model.provider !== "openai" &&
		request.model.provider !== "openai-codex"
	) {
		throw new Error(
			`Native OpenAI compaction does not support provider ${request.model.provider}.`,
		);
	}

	const openAi = await loadOmp<OpenAiCompactionModule>(
		"@oh-my-pi/pi-agent-core/compaction/openai",
	);
	if (request.model.provider === "openai-codex") {
		return compactOpenAICodexV2(request, openAi);
	}
	const newItems = openAi.buildOpenAiNativeHistory(
		request.context.messages,
		request.model,
	);
	// The standalone API requires the full caller-owned window. Disable the
	// installed helper's optional trailing-tool-output rewrite so opaque prior
	// items reach every later compaction byte-for-byte.
	const transportModel =
		request.model.contextWindow === null
			? request.model
			: { ...request.model, contextWindow: null };
	const previousItems = matchingPreviousItems(request);
	const input = previousItems ? [...previousItems, ...newItems] : newItems;

	let parsedResponse: unknown;
	const transport = request.fetch ?? globalThis.fetch;
	const captureFetch: FetchImpl = async (url, init) => {
		const response = await transport(url, init);
		return new Proxy(response, {
			get(target, property) {
				if (property === "json") {
					return async () => {
						const parsed = await target.json();
						parsedResponse = parsed;
						return parsed;
					};
				}
				const value = Reflect.get(target, property, target);
				return typeof value === "function" ? value.bind(target) : value;
			},
		});
	};

	// Keep the installed request implementation as the authority for endpoint,
	// authentication, HTTP errors, timeouts, and its baseline marker validation.
	// captureFetch observes the same parsed object without cloning or consuming
	// the body a second time.
	await openAi.requestOpenAiRemoteCompaction(
		transportModel,
		request.apiKey,
		input,
		request.instructions,
		request.signal,
		{ fetch: captureFetch, sessionId: request.sessionId },
	);

	if (
		parsedResponse === null ||
		typeof parsedResponse !== "object" ||
		Array.isArray(parsedResponse)
	) {
		throw new Error("OpenAI compaction returned an invalid response body.");
	}
	if (!("output" in parsedResponse) || !Array.isArray(parsedResponse.output)) {
		throw new Error("OpenAI compaction returned an invalid response body.");
	}
	if (
		!parsedResponse.output.every(
			(item) =>
				item !== null && typeof item === "object" && !Array.isArray(item),
		)
	) {
		throw new Error("OpenAI compaction returned an invalid output window.");
	}
	// Every output member was validated above; keep this exact array rather than
	// mapping it into the legacy subset returned by requestOpenAiRemoteCompaction.
	const output = parsedResponse.output as Record<string, unknown>[];
	if (!output.some(isEncryptedCompactionItem)) {
		throw new Error(
			"OpenAI compaction response is missing a valid encrypted compaction item.",
		);
	}

	let usage: Record<string, unknown> | undefined;
	if ("usage" in parsedResponse && parsedResponse.usage !== undefined) {
		if (
			parsedResponse.usage === null ||
			typeof parsedResponse.usage !== "object" ||
			Array.isArray(parsedResponse.usage)
		) {
			throw new Error("OpenAI compaction returned invalid usage data.");
		}
		usage = parsedResponse.usage as Record<string, unknown>;
	}

	return {
		provider: request.model.provider,
		model: request.model.id,
		format: "openai-responses",
		items: output,
		...(usage ? { usage } : {}),
	};
}
