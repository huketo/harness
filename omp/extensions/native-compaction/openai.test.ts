import { expect, test } from "bun:test";
import type { FetchImpl, Model, ModelSpec } from "@oh-my-pi/pi-ai";
import { compactOpenAI } from "./openai";
import { loadOmp } from "./runtime";
import type { NativeRequest } from "./types";

interface CatalogBuildModule {
	buildModel(spec: ModelSpec): Model;
}

const { buildModel } = await loadOmp<CatalogBuildModule>(
	"@oh-my-pi/pi-catalog/build",
);

interface SentCompactRequest {
	model: string;
	instructions: string;
	input: Record<string, unknown>[];
	stream?: boolean;
	store?: boolean;
}

function model(provider: "openai" | "openai-codex" = "openai"): Model {
	return buildModel({
		id: "gpt-5.6-sol",
		name: "GPT 5.6 Sol",
		provider,
		api: provider === "openai" ? "openai-responses" : "openai-codex-responses",
		baseUrl: "https://provider.example/v1",
		reasoning: true,
		input: ["text"],
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 272_000,
		maxTokens: 128_000,
	});
}

function request(
	fetch: FetchImpl,
	overrides: Partial<NativeRequest> = {},
): NativeRequest {
	return {
		model: model(),
		context: {
			messages: [{ role: "user", content: "compact this turn", timestamp: 1 }],
		},
		apiKey: "test-key",
		sessionId: "session-native-compaction",
		instructions: "Preserve everything needed to continue.",
		fetch,
		...overrides,
	};
}

function jsonResponse(body: unknown, init?: ResponseInit): Response {
	return new Response(JSON.stringify(body), {
		status: 200,
		headers: { "content-type": "application/json" },
		...init,
	});
}

function sseResponse(events: Record<string, unknown>[]): Response {
	const body = events
		.map(
			(event) =>
				`event: ${String(event.type)}\ndata: ${JSON.stringify(event)}\n\n`,
		)
		.join("");
	return new Response(`${body}data: [DONE]\n\n`, {
		status: 200,
		headers: { "content-type": "text/event-stream" },
	});
}

test("retains the standalone endpoint's complete canonical output and usage", async () => {
	const output = [
		{
			type: "reasoning",
			id: "rs_1",
			encrypted_content: "reasoning-ciphertext",
			summary: [{ type: "summary_text", text: "kept reasoning" }],
			status: "completed",
		},
		{
			type: "function_call",
			id: "fc_1",
			call_id: "call_1",
			name: "lookup",
			arguments: '{"id":1}',
			status: "completed",
		},
		{
			type: "function_call_output",
			call_id: "call_1",
			output: "tool result",
		},
		{
			type: "message",
			id: "msg_1",
			role: "assistant",
			content: [
				{ type: "output_text", text: "retained answer", annotations: [] },
			],
			status: "completed",
		},
		{
			type: "compaction",
			id: "cmp_1",
			encrypted_content: "compaction-ciphertext",
			created_by: "provider",
		},
	];
	const usage = {
		input_tokens: 123,
		output_tokens: 17,
		total_tokens: 140,
		output_tokens_details: { reasoning_tokens: 11 },
	};
	let sentUrl = "";
	let sentBody: SentCompactRequest | undefined;
	const fetch: FetchImpl = async (url, init) => {
		sentUrl = String(url);
		sentBody = JSON.parse(String(init?.body));
		return jsonResponse({
			id: "resp_compact_1",
			object: "response.compaction",
			output,
			usage,
		});
	};

	const window = await compactOpenAI(request(fetch));

	expect(sentUrl).toBe("https://provider.example/v1/responses/compact");
	expect(sentBody).toMatchObject({
		model: "gpt-5.6-sol",
		instructions: "Preserve everything needed to continue.",
		input: [
			{
				type: "message",
				role: "user",
				content: [{ type: "input_text", text: "compact this turn" }],
			},
		],
	});
	expect(window).toEqual({
		provider: "openai",
		model: "gpt-5.6-sol",
		format: "openai-responses",
		items: output,
		usage,
	});
});

test("prepends a previous native window byte-for-byte before only the new history", async () => {
	const opaqueToolOutput = "x".repeat(4_000);
	const firstOutput = [
		{
			type: "reasoning",
			id: "rs_previous",
			encrypted_content: "opaque-reasoning",
			status: "completed",
			provider_extension: { exact: [1, "two", { three: true }] },
		},
		{
			type: "custom_tool_call",
			id: "ct_previous",
			call_id: "call_previous",
			name: "patch",
			input: "opaque input",
			status: "completed",
		},
		{
			type: "compaction",
			id: "cmp_previous",
			encrypted_content: "opaque-compaction",
			created_by: "provider-vNext",
		},
		{
			type: "custom_tool_call_output",
			call_id: "call_previous",
			output: opaqueToolOutput,
		},
	];
	const secondOutput = [
		{
			type: "compaction",
			id: "cmp_next",
			encrypted_content: "next-compaction",
		},
	];
	const bodies: SentCompactRequest[] = [];
	const fetch: FetchImpl = async (_url, init) => {
		bodies.push(JSON.parse(String(init?.body)));
		return jsonResponse({
			object: "response.compaction",
			output: bodies.length === 1 ? firstOutput : secondOutput,
			usage: { total_tokens: bodies.length },
		});
	};

	const compactModel = { ...model(), contextWindow: 600 };
	const first = await compactOpenAI(request(fetch, { model: compactModel }));
	const second = await compactOpenAI(
		request(fetch, {
			model: compactModel,
			previous: first,
			context: { messages: [] },
		}),
	);

	const secondInput = bodies[1]?.input ?? [];
	expect(secondInput).toEqual(firstOutput);
	expect(first.items).toEqual(firstOutput);
	expect(second.items).toEqual(secondOutput);
});

test("does not reuse a native window from a different provider", async () => {
	let sentInput: Record<string, unknown>[] = [];
	const fetch: FetchImpl = async (_url, init) => {
		const body: SentCompactRequest = JSON.parse(String(init?.body));
		sentInput = body.input;
		return jsonResponse({
			output: [{ type: "compaction", id: "cmp_1", encrypted_content: "valid" }],
		});
	};

	await compactOpenAI(
		request(fetch, {
			previous: {
				provider: "openai-codex",
				model: "gpt-5.6-sol",
				format: "openai-responses",
				items: [{ type: "compaction", encrypted_content: "wrong-provider" }],
			},
		}),
	);

	expect(sentInput).toEqual([
		{
			type: "message",
			role: "user",
			content: [{ type: "input_text", text: "compact this turn" }],
		},
	]);
});

test("uses the native Codex V2 stream and returns its replacement history and usage", async () => {
	const previousUser = {
		type: "message",
		role: "user",
		content: [{ type: "input_text", text: "retained user request" }],
	};
	const previousCompaction = {
		type: "compaction",
		id: "cmp_previous",
		encrypted_content: "previous-ciphertext",
	};
	const compaction = {
		type: "compaction",
		id: "cmp_v2",
		encrypted_content: "v2-ciphertext",
		created_by: "codex",
	};
	const newUser = {
		type: "message",
		role: "user",
		content: [{ type: "input_text", text: "new user request" }],
	};
	let sentUrl = "";
	let sentHeaders = new Headers();
	let sentBody: SentCompactRequest | undefined;
	const fetch: FetchImpl = async (url, init) => {
		sentUrl = String(url);
		sentHeaders = new Headers(init?.headers);
		sentBody = JSON.parse(String(init?.body));
		return sseResponse([
			{ type: "response.output_item.done", item: compaction },
			{
				type: "response.completed",
				response: {
					usage: {
						input_tokens: 321,
						output_tokens: 12,
						total_tokens: 333,
						input_tokens_details: { cached_tokens: 200 },
						output_tokens_details: { reasoning_tokens: 9 },
					},
				},
			},
		]);
	};

	const window = await compactOpenAI(
		request(fetch, {
			model: model("openai-codex"),
			previous: {
				provider: "openai-codex",
				model: "gpt-5.6-sol",
				format: "openai-responses",
				items: [previousUser, previousCompaction],
			},
			context: {
				messages: [{ role: "user", content: "new user request", timestamp: 2 }],
			},
		}),
	);

	expect(sentUrl).toBe("https://provider.example/v1/codex/responses");
	expect(sentHeaders.get("authorization")).toBe("Bearer test-key");
	expect(sentHeaders.get("session-id")).toBe("session-native-compaction");
	expect(sentHeaders.get("originator")).toBe("omp");
	expect(sentBody).toMatchObject({
		model: "gpt-5.6-sol",
		instructions: "Preserve everything needed to continue.",
		stream: true,
		store: false,
		input: [
			previousUser,
			previousCompaction,
			newUser,
			{ type: "compaction_trigger" },
		],
	});
	expect(window).toEqual({
		provider: "openai-codex",
		model: "gpt-5.6-sol",
		format: "openai-responses",
		items: [previousUser, newUser, { ...compaction }],
		usage: {
			inputTokens: 321,
			outputTokens: 12,
			totalTokens: 333,
			cachedInputTokens: 200,
			reasoningOutputTokens: 9,
		},
	});
});

test("fails closed when a completed Codex V2 stream has no compaction item", async () => {
	const fetch: FetchImpl = async () =>
		sseResponse([
			{
				type: "response.completed",
				response: {
					usage: { input_tokens: 10, output_tokens: 1, total_tokens: 11 },
				},
			},
		]);

	await expect(
		compactOpenAI(request(fetch, { model: model("openai-codex") })),
	).rejects.toThrow("expected exactly one compaction output item");
});

test("propagates cancellation through the installed request transport", async () => {
	const controller = new AbortController();
	controller.abort(new DOMException("cancelled by test", "AbortError"));
	let observedAborted = false;
	const fetch: FetchImpl = async (_url, init) => {
		observedAborted = init?.signal?.aborted ?? false;
		init?.signal?.throwIfAborted();
		throw new Error("the aborted transport unexpectedly continued");
	};

	await expect(
		compactOpenAI(request(fetch, { signal: controller.signal })),
	).rejects.toMatchObject({
		name: "AbortError",
	});
	expect(observedAborted).toBe(true);
});

test("fails closed on provider HTTP errors", async () => {
	const fetch: FetchImpl = async () =>
		jsonResponse(
			{ error: { message: "capacity unavailable", type: "rate_limit_error" } },
			{ status: 429, statusText: "Too Many Requests" },
		);

	await expect(compactOpenAI(request(fetch))).rejects.toThrow(
		"Remote compaction failed (429 Too Many Requests)",
	);
});

test("fails closed when the provider omits the compaction marker", async () => {
	const fetch: FetchImpl = async () =>
		jsonResponse({
			output: [
				{ type: "reasoning", id: "rs_1", encrypted_content: "reasoning-only" },
				{
					type: "function_call",
					id: "fc_1",
					call_id: "call_1",
					name: "lookup",
					arguments: "{}",
				},
			],
		});

	await expect(compactOpenAI(request(fetch))).rejects.toThrow(
		"Remote compaction response missing compaction item",
	);
});

test("rejects a compaction marker without non-empty encrypted content", async () => {
	const fetch: FetchImpl = async () =>
		jsonResponse({
			output: [
				{ type: "compaction", id: "cmp_invalid", encrypted_content: "" },
			],
		});

	await expect(compactOpenAI(request(fetch))).rejects.toThrow(
		"missing a valid encrypted compaction item",
	);
});
