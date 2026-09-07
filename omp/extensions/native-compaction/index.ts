import type * as AiModule from "@oh-my-pi/pi-ai";
import type {
	Context,
	FetchImpl,
	Model,
	SimpleStreamOptions,
} from "@oh-my-pi/pi-ai";
import type * as ProviderRegistry from "@oh-my-pi/pi-ai/registry/registry";
import type * as CatalogBuild from "@oh-my-pi/pi-catalog/build";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import type * as MessagesModule from "@oh-my-pi/pi-coding-agent/session/messages";
import type * as ContextModule from "@oh-my-pi/pi-coding-agent/session/session-context";
import { ANTHROPIC_COMPACTION_BETA, compactAnthropic } from "./anthropic";
import { compactOpenAI } from "./openai";
import { hasNativeCompactionRuntime, loadOmp } from "./runtime";
import {
	decodeWindow,
	encodeWindow,
	marker,
	PORTABLE_INSTRUCTIONS,
	replayWindow,
	STATE_KEY,
	storedWindow,
} from "./state";
import type { NativeWindow } from "./types";
import { nativeUsage } from "./usage";

const CLAUDE_API = "harness-anthropic-native";
const PRESERVE =
	"Preserve the user's goals, constraints, decisions, evidence, changed files, verification, unresolved work and next actions. Keep tool calls and results paired. Do not call tools while writing the summary; respond with text only.";
const supported = (model: Model) =>
	["openai", "openai-codex"].includes(model.provider) ||
	(model.provider === "anthropic" &&
		/^(claude-(fable-5|mythos|opus-(5|4-[678])|sonnet-(5|4-6)))(-|$)/.test(
			model.id,
		));

export function withCompactionBeta(baseFetch: FetchImpl): FetchImpl {
	return (input, init) => {
		const headers = new Headers(
			init?.headers ?? (input instanceof Request ? input.headers : undefined),
		);
		const betas = new Set(
			(headers.get("anthropic-beta") ?? "").split(",").filter(Boolean),
		);
		betas.add(ANTHROPIC_COMPACTION_BETA);
		headers.set("anthropic-beta", [...betas].join(","));
		return baseFetch(input, { ...init, headers });
	};
}

export default async function nativeCompaction(pi: ExtensionAPI) {
	const { buildSessionContext } = await loadOmp<typeof ContextModule>(
		"@oh-my-pi/pi-coding-agent/session/session-context",
	);
	const { convertToLlm } = await loadOmp<typeof MessagesModule>(
		"@oh-my-pi/pi-coding-agent/session/messages",
	);
	const { completeSimple, streamSimple } =
		await loadOmp<typeof AiModule>("@oh-my-pi/pi-ai");
	const { buildModel } = await loadOmp<typeof CatalogBuild>(
		"@oh-my-pi/pi-catalog/build",
	);
	const nativeModel = (model: Model): Model =>
		model.api === CLAUDE_API
			? buildModel({
					...model,
					api: "anthropic-messages",
					compat: model.compatConfig,
				})
			: model;
	let installedClaude = false;

	pi.on("session_start", async (_event, ctx) => {
		if (installedClaude) return;
		const models = ctx.modelRegistry
			.getAll()
			.filter((model) => model.provider === "anthropic");
		if (!models.length) return;
		const { getProviderDefinition } = await loadOmp<typeof ProviderRegistry>(
			"@oh-my-pi/pi-ai/registry/registry",
		);
		const auth = getProviderDefinition("anthropic");
		if (!auth?.login)
			throw new Error("OMP의 기존 Anthropic 인증 공급자를 찾을 수 없습니다.");
		const originals = new Map(
			models.map((model) => [model.id, nativeModel(model)]),
		);
		pi.registerProvider("anthropic", {
			baseUrl: models[0].baseUrl,
			oauth: {
				name: auth.name,
				login: auth.login,
				refreshToken: auth.refreshToken,
				getApiKey: auth.getApiKey,
			},
			api: CLAUDE_API,
			models: models.map((model) => ({
				...model,
				api: supported(model) ? CLAUDE_API : model.api,
				compat: model.compatConfig ?? model.compat,
			})),
			streamSimple(model, context, options) {
				const original = originals.get(model.id);
				if (!original)
					throw new Error(`Claude 모델 원본을 찾을 수 없습니다: ${model.id}`);
				return streamSimple({ ...original, headers: model.headers }, context, {
					...options,
					fetch: withCompactionBeta(options?.fetch ?? fetch),
				});
			},
		});
		installedClaude = true;
		if (ctx.model?.provider === "anthropic" && supported(ctx.model)) {
			const replacement = ctx.modelRegistry.find("anthropic", ctx.model.id);
			if (replacement) await pi.setModel(replacement);
		}
	});

	pi.on("before_provider_request", (event, ctx) => {
		const boundary = ctx.sessionManager
			.getBranch()
			.findLast(
				(entry) =>
					entry.type === "compaction" || entry.type === "reset_boundary",
			);
		const stored = storedWindow(
			boundary?.type === "compaction" ? boundary.preserveData : undefined,
		);
		return stored ? replayWindow(event.payload, stored) : undefined;
	});

	pi.on("session_before_compact", async (event, ctx) => {
		if (!ctx.model || !supported(ctx.model)) return;
		try {
			const signal = AbortSignal.any([
				event.signal,
				AbortSignal.timeout(170000),
			]);
			if (!hasNativeCompactionRuntime())
				throw new Error(
					"네이티브 압축 런타임 패치가 필요합니다. bash install.sh를 실행한 뒤 OMP를 재시작하세요.",
				);
			const model = nativeModel(ctx.model);
			const sessionId = ctx.sessionManager.getSessionId();
			const leaf = ctx.sessionManager.getLeafId();
			const boundaryEntry = event.branchEntries.findLast(
				(entry) =>
					entry.type === "compaction" || entry.type === "reset_boundary",
			);
			const last =
				boundaryEntry?.type === "compaction" ? boundaryEntry : undefined;
			const stored = storedWindow(last?.preserveData);
			let previous: NativeWindow | undefined = stored
				? decodeWindow(stored)
				: undefined;
			const legacy = last?.preserveData?.openaiRemoteCompaction as
				| { provider?: string; replacementHistory?: Record<string, unknown>[] }
				| undefined;
			if (
				!previous &&
				legacy?.provider &&
				Array.isArray(legacy.replacementHistory)
			)
				previous = {
					provider: legacy.provider,
					model: model.id,
					format: "openai-responses",
					items: legacy.replacementHistory,
				};
			if (previous && previous.provider !== model.provider)
				throw new Error(
					"공급자를 바꾸기 전에 원래 모델에서 /native-compact portable을 실행하세요.",
				);
			const effective = buildSessionContext(event.branchEntries).messages;
			const messages = previous
				? effective.filter((message) => message.role !== "compactionSummary")
				: effective;
			const activeTools = new Set(pi.getActiveTools());
			const context: Context = {
				systemPrompt: ctx.getSystemPrompt(),
				messages: convertToLlm(messages),
				tools: pi
					.getAllTools()
					.filter((tool) => activeTools.has(tool.name))
					.map((tool) => ({
						name: tool.name,
						description: tool.description,
						parameters: tool.parameters,
					})),
			};
			const apiKey = await ctx.modelRegistry.getApiKey(model, sessionId, {
				signal,
			});
			if (!apiKey)
				throw new Error(`${model.provider} 인증을 사용할 수 없습니다.`);
			const portable =
				event.customInstructions?.startsWith(PORTABLE_INSTRUCTIONS) === true;
			let summary: string;
			let preserveData: Record<string, unknown> | undefined;
			let details: Record<string, unknown> | undefined;
			if (portable) {
				const portableStored = previous ? encodeWindow(previous) : undefined;
				const prefix = portableStored
					? [
							{
								role: "user" as const,
								content: marker(portableStored),
								timestamp: Date.now(),
							},
						]
					: [];
				const result = await completeSimple(
					model,
					{
						...context,
						messages: [
							...prefix,
							...context.messages,
							{
								role: "user",
								content: `${PRESERVE}\nWrite a self-contained, readable handoff for another model.`,
								timestamp: Date.now(),
							},
						],
					},
					{
						apiKey,
						signal,
						sessionId,
						maxTokens: 16000,
						...(model.provider === "anthropic"
							? { fetch: withCompactionBeta(fetch) }
							: {}),
						onPayload: (payload) =>
							portableStored ? replayWindow(payload, portableStored) : payload,
					} as SimpleStreamOptions,
				);
				if (result.stopReason === "error" || result.stopReason === "aborted")
					throw new Error(result.errorMessage ?? "인계문 생성 실패");
				summary = result.content
					.filter((part) => part.type === "text")
					.map((part) => part.text)
					.join("\n");
				if (!summary.trim())
					throw new Error("읽을 수 있는 인계문이 비어 있습니다.");
			} else {
				const request = {
					model,
					context,
					apiKey,
					sessionId,
					signal,
					previous,
					instructions: [PRESERVE, event.customInstructions]
						.filter(Boolean)
						.join("\n"),
				};
				const window =
					model.provider === "anthropic"
						? await compactAnthropic(request)
						: await compactOpenAI(request);
				details = {
					provider: window.provider,
					model: window.model,
					usage: window.usage,
					totals: nativeUsage(window),
				};
				const encoded = encodeWindow(window);
				summary = `${marker(encoded)}\n${window.summary ?? "OpenAI 네이티브 압축 상태. 다음 요청에서 원본 압축 창을 복원합니다."}`;
				preserveData = { [STATE_KEY]: encoded };
			}
			signal.throwIfAborted();
			if (ctx.sessionManager.getLeafId() !== leaf)
				throw new Error("압축 중 세션이 변경되어 결과를 적용하지 않았습니다.");
			// A non-message cut point retains no already-compacted messages.
			pi.appendEntry("harness-native-compaction-boundary", { portable });
			const boundary = ctx.sessionManager.getLeafId();
			if (!boundary || boundary === leaf)
				throw new Error("압축 저장 경계를 만들지 못했습니다.");
			return {
				compaction: {
					summary,
					firstKeptEntryId: boundary,
					tokensBefore:
						ctx.getContextUsage()?.tokens ?? event.preparation.tokensBefore,
					preserveData,
					details,
				},
			};
		} catch (error) {
			ctx.ui.notify(
				error instanceof Error ? error.message : String(error),
				"error",
			);
			// OMP contains extension exceptions; explicit cancellation prevents a silent local fallback.
			return { cancel: true };
		}
	});

	pi.registerCommand("native-compact", {
		description:
			"네이티브 압축 실행; portable은 다른 공급자로 옮길 읽기 가능한 인계문 생성",
		handler: async (args, ctx) => {
			if (!ctx.isIdle()) throw new Error("현재 응답이 끝난 뒤 압축하세요.");
			if (args.trim() && args.trim() !== "portable")
				throw new Error("사용법: /native-compact [portable]");
			await ctx.compact(
				args.trim() === "portable"
					? `${PORTABLE_INSTRUCTIONS}${PRESERVE}`
					: undefined,
			);
		},
	});
}
