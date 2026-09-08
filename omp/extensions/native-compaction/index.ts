import type * as AiModule from "@oh-my-pi/pi-ai";
import type {
	Context,
	FetchImpl,
	Model,
	SimpleStreamOptions,
} from "@oh-my-pi/pi-ai";
import type * as ProviderRegistry from "@oh-my-pi/pi-ai/registry/registry";
import type * as CatalogBuild from "@oh-my-pi/pi-catalog/build";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";
import type * as MessagesModule from "@oh-my-pi/pi-coding-agent/session/messages";
import type * as ContextModule from "@oh-my-pi/pi-coding-agent/session/session-context";
import { NATIVE_COMPACTION_TIMEOUT_MS } from "../../native-runtime";
import { hasNativeCompactionRuntime, loadOmp } from "./runtime";
import {
	decodeWindow,
	marker,
	PORTABLE_INSTRUCTIONS,
	replayWindow,
	STATE_KEY,
	storedWindow,
} from "./state";

const CLAUDE_API = "harness-anthropic-native";
const PRESERVE =
	"Preserve the user's goals, constraints, decisions, evidence, changed files, verification, unresolved work and next actions. Keep tool calls and results paired. Do not call tools while writing the summary; respond with text only.";

function activePreserveData(ctx: ExtensionContext) {
	const boundary = ctx.sessionManager
		.getBranch()
		.findLast(
			(entry) => entry.type === "compaction" || entry.type === "reset_boundary",
		);
	return boundary?.type === "compaction" ? boundary.preserveData : undefined;
}

function activeWindow(ctx: ExtensionContext) {
	return storedWindow(activePreserveData(ctx));
}

function withCompactionBeta(baseFetch: FetchImpl): FetchImpl {
	return (input, init) => {
		const headers = new Headers(
			init?.headers ?? (input instanceof Request ? input.headers : undefined),
		);
		const betas = new Set(
			(headers.get("anthropic-beta") ?? "").split(",").filter(Boolean),
		);
		betas.add("compact-2026-01-12");
		headers.set("anthropic-beta", [...betas].join(","));
		return baseFetch(input, { ...init, headers });
	};
}

/** Replay existing opaque sessions and convert them once; new compaction belongs to OMP. */
export default async function nativeCompaction(pi: ExtensionAPI) {
	let migrationRegistered = false;
	let installedClaude = false;

	pi.on("before_provider_request", (event, ctx) => {
		const stored = activeWindow(ctx);
		return stored ? replayWindow(event.payload, stored) : undefined;
	});

	async function enableMigration(ctx: ExtensionContext) {
		const preserveData = activePreserveData(ctx);
		if (preserveData?.[STATE_KEY] === undefined) return;
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

		if (!migrationRegistered) {
			migrationRegistered = true;
			// Do not register this veto hook for ordinary sessions: its presence also disables OMP speculation.
			pi.on("session_before_compact", async (event, compactCtx) => {
				const boundaryEntry = event.branchEntries.findLast(
					(entry) =>
						entry.type === "compaction" || entry.type === "reset_boundary",
				);
				try {
					const stored = storedWindow(
						boundaryEntry?.type === "compaction"
							? boundaryEntry.preserveData
							: undefined,
					);
					if (!stored) return;
					if (!hasNativeCompactionRuntime())
						throw new Error(
							"기존 압축 세션을 이전하려면 bash install.sh 실행 후 OMP를 재시작하세요.",
						);
					const previous = decodeWindow(stored);
					if (
						!compactCtx.model ||
						previous.provider !== compactCtx.model.provider
					)
						throw new Error(
							"원래 공급자에서 /native-compact portable로 이전한 뒤 모델을 변경하세요.",
						);
					const signal = AbortSignal.any([
						event.signal,
						AbortSignal.timeout(NATIVE_COMPACTION_TIMEOUT_MS),
					]);
					const model = nativeModel(compactCtx.model);
					// The runtime patch exposes the provider routing identity, not just the persisted session UUID.
					const sessionId = (
						compactCtx as ExtensionContext & { sessionId?: string }
					).sessionId;
					if (!sessionId)
						throw new Error(
							"계정 세션 런타임 패치를 적용한 OMP에서 이전하세요.",
						);
					const leaf = compactCtx.sessionManager.getLeafId();
					const { buildSessionContext } = await loadOmp<typeof ContextModule>(
						"@oh-my-pi/pi-coding-agent/session/session-context",
					);
					const { convertToLlm } = await loadOmp<typeof MessagesModule>(
						"@oh-my-pi/pi-coding-agent/session/messages",
					);
					const messages = buildSessionContext(
						event.branchEntries,
					).messages.filter((message) => message.role !== "compactionSummary");
					const activeTools = new Set(pi.getActiveTools());
					const context: Context = {
						systemPrompt: compactCtx.getSystemPrompt(),
						messages: [
							{ role: "user", content: marker(stored), timestamp: Date.now() },
							...convertToLlm(messages),
							{
								role: "user",
								content: `${PRESERVE}\nWrite a self-contained, readable handoff for another model.`,
								timestamp: Date.now(),
							},
						],
						tools: pi
							.getAllTools()
							.filter((tool) => activeTools.has(tool.name))
							.map((tool) => ({
								name: tool.name,
								description: tool.description,
								parameters: tool.parameters,
							})),
					};
					const apiKey = await compactCtx.modelRegistry.getApiKey(
						model,
						sessionId,
						{ signal },
					);
					if (!apiKey)
						throw new Error(`${model.provider} 인증을 사용할 수 없습니다.`);
					const result = await completeSimple(model, context, {
						apiKey,
						signal,
						sessionId,
						maxTokens: 16000,
						...(model.provider === "anthropic"
							? { fetch: withCompactionBeta(fetch) }
							: {}),
						onPayload: (payload) => replayWindow(payload, stored),
					} as SimpleStreamOptions);
					if (result.stopReason !== "stop")
						throw new Error(
							result.errorMessage ?? `인계문 생성 미완료: ${result.stopReason}`,
						);
					const summary = result.content
						.filter((part) => part.type === "text")
						.map((part) => part.text)
						.join("\n");
					if (!summary.trim())
						throw new Error("읽을 수 있는 인계문이 비어 있습니다.");
					signal.throwIfAborted();
					if (compactCtx.sessionManager.getLeafId() !== leaf)
						throw new Error(
							"압축 중 세션이 변경되어 결과를 적용하지 않았습니다.",
						);
					pi.appendEntry("harness-native-compaction-boundary", {
						portable: true,
					});
					const boundary = compactCtx.sessionManager.getLeafId();
					if (!boundary || boundary === leaf)
						throw new Error("압축 저장 경계를 만들지 못했습니다.");
					return {
						compaction: {
							summary,
							firstKeptEntryId: boundary,
							tokensBefore:
								compactCtx.getContextUsage()?.tokens ??
								event.preparation.tokensBefore,
						},
					};
				} catch (error) {
					compactCtx.ui.notify(
						error instanceof Error ? error.message : String(error),
						"error",
					);
					// Never let a failed legacy conversion summarize only its opaque marker.
					return { cancel: true };
				}
			});
		}
		const stored = storedWindow(preserveData);
		if (!stored) return;
		const previous = decodeWindow(stored);
		// Only an existing Claude opaque block needs the old beta transport.
		if (previous.provider === "anthropic" && !installedClaude) {
			const models = ctx.modelRegistry
				.getAll()
				.filter((model) => model.provider === "anthropic");
			const { getProviderDefinition } = await loadOmp<typeof ProviderRegistry>(
				"@oh-my-pi/pi-ai/registry/registry",
			);
			const auth = getProviderDefinition("anthropic");
			if (!auth?.login || !models.length)
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
					api: CLAUDE_API,
					compat: model.compatConfig ?? model.compat,
				})),
				streamSimple(model, context, options) {
					const original = originals.get(model.id);
					if (!original)
						throw new Error(`Claude 모델 원본을 찾을 수 없습니다: ${model.id}`);
					return streamSimple(
						{ ...original, headers: model.headers },
						context,
						{
							...options,
							...(activeWindow(ctx)
								? { fetch: withCompactionBeta(options?.fetch ?? fetch) }
								: {}),
						},
					);
				},
			});
			installedClaude = true;
			if (ctx.model?.provider === "anthropic") {
				const replacement = ctx.modelRegistry.find("anthropic", ctx.model.id);
				if (replacement) await pi.setModel(replacement);
			}
		}
	}

	pi.on("session_start", async (_event, ctx) => enableMigration(ctx));
	pi.on("session_switch", async (_event, ctx) => enableMigration(ctx));
	pi.on("session_tree", async (_event, ctx) => enableMigration(ctx));
	pi.registerCommand("native-compact", {
		description:
			"기존 네이티브 저장 상태를 OMP 내장 압축용 portable 인계문으로 이전",
		handler: async (args, ctx) => {
			if (!ctx.isIdle()) throw new Error("현재 응답이 끝난 뒤 압축하세요.");
			if (args.trim() !== "portable")
				throw new Error(
					"새 압축은 /compact를 사용하세요. 기존 상태 이전: /native-compact portable",
				);
			if (!activeWindow(ctx))
				throw new Error(
					"이전할 기존 네이티브 압축 상태가 없습니다. /compact를 사용하세요.",
				);
			await enableMigration(ctx);
			await ctx.compact(`${PORTABLE_INSTRUCTIONS}${PRESERVE}`);
		},
	});
}
