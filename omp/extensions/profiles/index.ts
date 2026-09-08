import type { ThinkingLevel } from "@oh-my-pi/pi-agent-core";
import type { Model } from "@oh-my-pi/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";
import { PORTABLE_INSTRUCTIONS, STATE_KEY } from "../native-compaction/state";
import {
	loadProfiles,
	loadState,
	resolveProfile,
	resolvePromptText,
	saveState,
} from "./schema";

const PRESERVE =
	"Preserve the user's goals, constraints, decisions and evidence, changed file paths, verification results, unresolved work, and next actions. Keep tool calls/results paired. Preserve source paths and media timestamps; distinguish observations from inference. Produce a readable handoff, not a provider-native placeholder.";

export function contextBudget(
	model: Pick<Model, "contextWindow" | "maxTokens">,
	percent: number,
): number {
	return Math.max(
		1,
		Math.floor(
			Math.min(
				(model.contextWindow * percent) / 100,
				model.contextWindow - model.maxTokens - 8000,
			),
		),
	);
}

export default function profilesExtension(pi: ExtensionAPI) {
	const profiles = loadProfiles();
	const prompts = new Map(
		Object.entries(profiles.models).map(([key, model]) => [
			key,
			resolvePromptText(model),
		]),
	);
	const readState = () => loadState(pi.pi.getAgentDir());
	let activeProfile: string | undefined;
	let lastModel: Model | undefined;
	let launchEffortModel: Model | undefined;
	const sessionEffort = new Map<
		string,
		{ level: ThinkingLevel; previous: ThinkingLevel | undefined }
	>();
	function setSessionEffort(key: string, level?: ThinkingLevel) {
		const previous =
			level === undefined
				? undefined
				: (sessionEffort.get(key)?.previous ?? pi.getThinkingLevel());
		pi.appendEntry("harness-session-effort", {
			key,
			level: level ?? null,
			previous,
		});
		if (level === undefined) sessionEffort.delete(key);
		else sessionEffort.set(key, { level, previous });
	}
	pi.registerFlag("harness-profile", {
		type: "string",
		description: "Purpose profile selected by omp-profile/harness-run",
	});

	const modelKey = (model: Model) =>
		Object.keys(profiles.models).find((key) => {
			const entry = profiles.models[key];
			return entry.provider === model.provider && entry.model === model.id;
		});
	const sameModel = (a?: Model, b?: Model) =>
		a?.id === b?.id && a?.provider === b?.provider;
	const budget = (model: Model) =>
		contextBudget(
			model,
			profiles.models[modelKey(model) ?? ""]?.compaction.thresholdPercent ?? 75,
		);
	const supported = (model: Model, effort: string) =>
		model.thinking?.efforts?.includes(effort as ThinkingLevel) === true;
	const latestCompaction = (ctx: ExtensionContext) => {
		const boundary = ctx.sessionManager
			.getBranch()
			.findLast(
				(entry) =>
					entry.type === "compaction" || entry.type === "reset_boundary",
			);
		return boundary?.type === "compaction" ? boundary : undefined;
	};
	const hasNativeState = (ctx: ExtensionContext) =>
		Boolean(
			latestCompaction(ctx)?.preserveData?.openaiRemoteCompaction ||
				latestCompaction(ctx)?.preserveData?.[STATE_KEY],
		);
	const notifyError = (ctx: ExtensionContext, error: unknown) =>
		ctx.ui.notify(
			error instanceof Error ? error.message : String(error),
			"error",
		);

	// Only called at idle input/command boundaries: compact() aborts a running turn.
	// Native state is converted explicitly before crossing a provider boundary.
	async function prepareContext(
		ctx: ExtensionContext,
		target: Model,
		portable: boolean,
	) {
		const usage = ctx.getContextUsage();
		if (!usage) return;
		const needsPortable = portable && hasNativeState(ctx);
		if (!needsPortable && usage.tokens <= budget(target)) return;
		const branch = ctx.sessionManager.getBranch();
		if (!branch.some((entry) => entry.type === "message")) return;
		if (branch.at(-1)?.type === "compaction")
			pi.appendEntry("harness-context-transition", {
				target: `${target.provider}/${target.id}`,
			});
		ctx.ui.notify(
			`컨텍스트 정리: ${usage.tokens} 토큰 → ${target.id}의 안전 기준 ${budget(target)} 토큰`,
			"info",
		);
		await ctx.compact(
			portable && latestCompaction(ctx)?.preserveData?.[STATE_KEY]
				? `${PORTABLE_INSTRUCTIONS}${PRESERVE}`
				: {
						internalGuidance: PRESERVE,
						...(portable ? { mode: "soft" as const } : {}),
					},
		);
		if (portable && hasNativeState(ctx))
			throw new Error(
				"읽을 수 있는 인계문 생성에 실패하여 모델 전환을 중단했습니다. 현재 세션은 유지됩니다.",
			);
		const after = ctx.getContextUsage();
		if (after && after.tokens > budget(target))
			throw new Error(
				"압축 후에도 대상 모델의 안전 기준을 초과합니다. /handoff 또는 새 세션으로 분리하세요. 모델 전환은 수행하지 않습니다.",
			);
	}

	function applySavedEffort(ctx: ExtensionContext) {
		const model = ctx.model;
		if (!model) return;
		if (!sameModel(lastModel, model)) activeProfile = undefined;
		const key = modelKey(model) ?? `${model.provider}/${model.id}`;
		let effort = sessionEffort.get(key)?.level;
		if (effort === undefined) {
			const state = readState();
			effort = (
				activeProfile
					? (resolveProfile(profiles, state, activeProfile).effort ?? undefined)
					: state.modelEffort[key]
			) as ThinkingLevel | undefined;
		}
		if (effort && supported(model, effort))
			pi.setThinkingLevel(effort as ThinkingLevel);
		lastModel = model;
	}

	pi.registerCommand("profile", {
		description: "🎯 용도별 모델·effort 선택 (내장 역할 설정과 독립)",
		getArgumentCompletions: (prefix) =>
			Object.entries(profiles.profiles)
				.filter(([name]) => name.startsWith(prefix))
				.map(([name, entry]) => ({
					value: name,
					label: name,
					description: entry.purpose,
				})),
		handler: async (args, ctx) => {
			if (!ctx.isIdle()) {
				ctx.ui.notify("모델 전환은 현재 응답이 끝난 뒤 가능합니다.", "warning");
				return;
			}
			try {
				const name =
					args.trim() ||
					(ctx.hasUI
						? await ctx.ui.select(
								"🎯 용도 선택",
								Object.entries(profiles.profiles).map(([label, entry]) => ({
									label,
									description: entry.purpose,
								})),
							)
						: undefined);
				if (!name) {
					if (!ctx.hasUI)
						ctx.ui.notify("/profile <용도> — 목록: omp-profile list", "info");
					return;
				}
				const resolved = resolveProfile(profiles, readState(), name);
				if (resolved.runner !== "omp")
					throw new Error(
						`${name}은 별도 AGY 세션입니다. harness-run agent --profile ${name} --name <이름> 으로 실행하세요.`,
					);
				const target = ctx.models.resolve(
					`${resolved.provider}/${resolved.model}`,
				);
				if (!target)
					throw new Error(
						`사용 가능한 모델이 없습니다: ${resolved.provider}/${resolved.model}`,
					);
				if (resolved.effort === null)
					throw new Error(`${target.id}에는 선택 가능한 effort가 없습니다.`);
				if (!supported(target, resolved.effort))
					throw new Error(
						`${target.id}에서 지원하지 않는 effort: ${resolved.effort}`,
					);
				// Prepare on the OLD model before any switch; failure leaves the selected model untouched.
				await prepareContext(
					ctx,
					target,
					ctx.model?.provider !== target.provider,
				);
				if (!(await pi.setModel(target)))
					throw new Error(`${target.id}의 인증을 사용할 수 없습니다.`);
				const key = modelKey(target) ?? `${target.provider}/${target.id}`;
				if (sessionEffort.has(key)) setSessionEffort(key);
				pi.setThinkingLevel(resolved.effort as ThinkingLevel);
				activeProfile = name;
				lastModel = target;
				launchEffortModel = undefined;
				pi.appendEntry("harness-profile", { name });
				ctx.ui.notify(
					`${name}: ${target.provider}/${target.id} · ${resolved.effort} (${resolved.effortSource})`,
					"info",
				);
			} catch (error) {
				notifyError(ctx, error);
			}
		},
	});

	pi.registerCommand("effort", {
		description:
			"🧠 현재 세션의 effort 변경; --profile은 용도 공용값 저장; reset은 해당 변경 해제",
		getArgumentCompletions: (prefix) =>
			["low", "medium", "high", "xhigh", "max", "reset", "--profile"]
				.filter((value) => value.startsWith(prefix))
				.map((value) => ({ value, label: value })),
		handler: async (args, ctx) => {
			if (!ctx.isIdle()) {
				ctx.ui.notify("응답이 끝난 뒤 effort를 변경하세요.", "warning");
				return;
			}
			try {
				const tokens = args.trim().split(/\s+/);
				const profileScope = tokens.includes("--profile");
				const levels = tokens.filter((token) => token !== "--profile");
				const model = ctx.model;
				if (!model || levels.length !== 1 || !levels[0])
					throw new Error("/effort <강도|reset> [--profile]");
				if (!sameModel(lastModel, model)) activeProfile = undefined;
				const level = levels[0];
				if (level !== "reset" && !supported(model, level))
					throw new Error(
						`지원 effort: ${model.thinking?.efforts?.join(", ") ?? "없음"}`,
					);
				if (profileScope && (!activeProfile || !sameModel(lastModel, model)))
					throw new Error("먼저 /profile로 용도를 선택하세요.");
				const key = modelKey(model) ?? `${model.provider}/${model.id}`;
				const state = readState();
				const previous = sessionEffort.get(key)?.previous;
				const name = profileScope && activeProfile ? activeProfile : key;
				if (profileScope) {
					if (level === "reset") delete state.profileEffort[name];
					else state.profileEffort[name] = level;
					saveState(pi.pi.getAgentDir(), state);
					if (sessionEffort.has(key)) setSessionEffort(key);
				} else {
					setSessionEffort(
						key,
						level === "reset" ? undefined : (level as ThinkingLevel),
					);
				}
				launchEffortModel = undefined;
				const effective =
					level !== "reset"
						? level
						: activeProfile
							? resolveProfile(profiles, state, activeProfile).effort
							: (state.modelEffort[key] ??
								previous ??
								profiles.models[key]?.effort);
				if (effective && supported(model, effective))
					pi.setThinkingLevel(effective as ThinkingLevel);
				lastModel = model;
				ctx.ui.notify(
					`${profileScope ? "용도 공용값" : "현재 세션"} ${name}: ${level === "reset" ? "변경 해제" : level}.${profileScope ? "" : " 다른 세션과 공용 설정은 변경하지 않았습니다."}`,
					"info",
				);
			} catch (error) {
				notifyError(ctx, error);
			}
		},
	});

	function restoreSessionState(event: { type: string }, ctx: ExtensionContext) {
		lastModel = ctx.model;
		activeProfile = undefined;
		sessionEffort.clear();
		const branch = ctx.sessionManager.getBranch();
		for (const entry of branch) {
			if (
				entry.type !== "custom" ||
				entry.customType !== "harness-session-effort" ||
				!entry.data ||
				typeof entry.data !== "object"
			)
				continue;
			const data = entry.data as {
				key?: unknown;
				level?: unknown;
				previous?: unknown;
			};
			if (typeof data.key !== "string") continue;
			if (data.level === null) sessionEffort.delete(data.key);
			else if (typeof data.level === "string")
				sessionEffort.set(data.key, {
					level: data.level as ThinkingLevel,
					previous:
						typeof data.previous === "string"
							? (data.previous as ThinkingLevel)
							: undefined,
				});
		}
		const saved = branch.findLast(
			(entry) =>
				entry.type === "custom" && entry.customType === "harness-profile",
		);
		const data =
			saved?.type === "custom" && saved.data && typeof saved.data === "object"
				? (saved.data as { name?: unknown })
				: undefined;
		const explicitProfile =
			event.type === "session_start"
				? pi.getFlag("harness-profile")
				: undefined;
		const launch = explicitProfile ?? data?.name;
		if (typeof launch === "string" && profiles.profiles[launch]) {
			const resolved = resolveProfile(profiles, readState(), launch);
			if (
				ctx.model?.provider === resolved.provider &&
				ctx.model.id === resolved.model
			)
				activeProfile = launch;
		}
		if (
			activeProfile &&
			typeof explicitProfile === "string" &&
			data?.name !== activeProfile
		) {
			pi.appendEntry("harness-profile", { name: activeProfile });
		}
		const explicitThinking =
			event.type === "session_start" &&
			process.argv.some(
				(arg, index, argv) =>
					arg === "--thinking" ||
					arg.startsWith("--thinking=") ||
					((argv[index - 1] === "--model" || arg.startsWith("--model=")) &&
						/:(off|minimal|low|medium|high|xhigh|max|auto)$/.test(arg)),
			);
		launchEffortModel =
			explicitThinking &&
			!activeProfile &&
			!(
				ctx.model &&
				sessionEffort.has(
					modelKey(ctx.model) ?? `${ctx.model.provider}/${ctx.model.id}`,
				)
			)
				? ctx.model
				: undefined;
		if (!launchEffortModel) applySavedEffort(ctx);
	}
	pi.on("session_start", restoreSessionState);
	pi.on("session_switch", restoreSessionState);
	pi.on("session_tree", restoreSessionState);
	pi.on("input", async (event, ctx) => {
		if (
			!ctx.isIdle() ||
			!ctx.model ||
			event.text.startsWith("/") ||
			sameModel(lastModel, ctx.model)
		)
			return;
		try {
			await prepareContext(
				ctx,
				ctx.model,
				lastModel !== undefined && lastModel.provider !== ctx.model.provider,
			);
		} catch (error) {
			notifyError(ctx, error);
			if (ctx.hasUI) ctx.ui.setEditorText(event.text);
			return { handled: true };
		}
	});
	pi.on("before_agent_start", (event, ctx) => {
		if (!launchEffortModel || !sameModel(launchEffortModel, ctx.model)) {
			launchEffortModel = undefined;
			applySavedEffort(ctx);
		}
		const key = ctx.model && modelKey(ctx.model);
		const prompt = key && prompts.get(key);
		return prompt && !event.systemPrompt.includes(prompt)
			? { systemPrompt: [...event.systemPrompt, prompt] }
			: undefined;
	});
	pi.on("session.compacting", () => ({ context: [PRESERVE] }));
}
