import { realpathSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { loadProfiles } from "../profiles/schema";

const RUNNER = join(
	realpathSync(join(import.meta.dir, "../../..")),
	"herdr/scripts/harness-run.ts",
);
const POLICY =
	"Use Herdr for command execution only when it is long-running, needs live human observation, or supports human collaboration (server/debugger/REPL). Short reads, transforms, builds and tests stay on native tools. herdr_run detach:true starts a retained interactive terminal (name required); inspect readiness explicitly and use herdr_agent read/send/wait to control it. Finite runs close their tab automatically after results are captured. Use herdr_agent for independently visible, reusable OMP/AGY agents with explicit briefs. Built-in task agents remain accessible through Alt+A Agent Hub; they cannot be moved into Herdr.";
const TRIAL_POLICY = `Herdr delegation trial: OMP owns the goal, decomposition, integration and verification.
Delegate independent substantial work through herdr_agent, with AGY as the default worker for research, implementation and review. Choose the role from the work, not the runtime. Use profile agy-work by default, agy-review for an independent review; choose an OMP profile only for an explicit model request or an OMP-specific capability and state the reason in the brief.
Native task and Eval agent()/workpool() are not this session's delegation path. The trial omits Eval because its embedded spawn API cannot be disabled independently through the public CLI; use ordinary read/bash tools for computation. Use herdr_agent action dispatch for a batch of independent assignments, or start for one worker. Each assignment needs name, role and prompt containing scope, shared contracts and acceptance evidence. Reuse that worker with send for follow-ups; do not duplicate its unfinished assignment.
Topology: keep the coordinator in its current workspace and tab. Each worker gets one no-focus tab in that same workspace and cwd. Reuse named workers before creating more tabs. Split panes only for an explicit shared-view need; choose right/down from current geometry and avoid repeated narrow splits. Workspace creation/moves are human topology decisions, not a side effect of delegation. Use returned opaque IDs and the inherited socket, never the focused pane or guessed IDs. Tabs/panes do not isolate files; coordinate file ownership exactly as for OMP workers.
Lifecycle: start is readiness/submission, not completion. Read the returned response after a settled notification, inspect artifacts and run relevant checks before completing the goal. A blocked/unknown state or timeout means inspect the existing worker, not resubmit. Preserve working/blocked workers. After integrating results, close only the trial-owned idle worker using herdr_agent close; shared tabs, caller panes and user-owned resources remain untouched. Reuse wins over close when follow-up is likely.
Ordinary short commands stay on native tools; this does not restrict agent delegation to long commands. Use interactive AGY by default, not print mode. Existing workspace and permission settings apply equally to OMP and AGY; add no special approval or sandbox flags.`;
const OFF_POLICY =
	"Delegation is off for this session. Do not create native task/Eval workers or new Herdr workers. Existing retained Herdr workers may still be read, waited on, sent follow-ups, or closed.";

async function run(
	args: string[],
	signal?: AbortSignal,
	env?: NodeJS.ProcessEnv,
) {
	if (process.env.HERDR_ENV !== "1")
		return {
			content: [
				{
					type: "text" as const,
					text: "Herdr 밖입니다. 기존 실행 도구를 사용하세요.",
				},
			],
			isError: true,
		};
	try {
		const child = Bun.spawn(["bun", RUNNER, ...args], {
			...(env ? { env } : {}),
			stdout: "pipe",
			stderr: "pipe",
		});
		const cancel = () => child.kill(); // Cancels the controller wait, not the retained terminal process.
		if (signal?.aborted) cancel();
		else signal?.addEventListener("abort", cancel, { once: true });
		try {
			const [stdout, stderr, code] = await Promise.all([
				new Response(child.stdout).text(),
				new Response(child.stderr).text(),
				child.exited,
			]);
			const output = stdout.trim() || stderr.trim();
			return {
				content: [
					{
						type: "text" as const,
						text:
							output || `Controller exited ${code}; inspect the retained pane.`,
					},
				],
				isError: code !== 0,
			};
		} finally {
			signal?.removeEventListener("abort", cancel);
		}
	} catch (error) {
		return {
			content: [{ type: "text" as const, text: String(error) }],
			isError: true,
		};
	}
}

async function askChannel() {
	let child;
	try {
		child = Bun.spawn(["herdr-hitl", "channel", "-o", "json"], {
			stdout: "pipe",
			stderr: "pipe",
		});
	} catch (error) {
		const code = (error as { code?: string }).code;
		// Only missing installations (ENOENT) are outside this gate.
		if (code === "ENOENT") return undefined;
		return {
			block: true,
			reason: `herdr-hitl channel could not start (${code ?? String(error)}). The ask tool is unavailable until the channel resolves; run herdr-hitl doctor. Do not ask the human another way: take the safe reversible path or defer only the dependent work.`,
		};
	}
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	let channel: unknown;
	try {
		channel = JSON.parse(stdout)?.channel;
	} catch {}
	if (code !== 0 || typeof channel !== "string")
		return {
			block: true,
			reason: `herdr-hitl channel failed (exit ${code}): ${(stderr.trim() || stdout.trim()).split(/\r?\n/, 1)[0]}. The ask tool is unavailable until the channel resolves; run herdr-hitl doctor. Do not ask the human another way: take the safe reversible path or defer only the dependent work.`,
		};
	if (channel === "terminal") return undefined;
	if (channel === "messenger")
		return {
			block: true,
			reason:
				"herdr-hitl channel is messenger: nobody is watching this interface. Do not use the ask tool. Ask with the herdr-hitl CLI (bash: herdr-hitl ask …) under the message contract in the herdr-hitl skill and APPEND_SYSTEM.md, then act only on an explicit answer.",
		};
	if (channel === "afk")
		return {
			block: true,
			reason:
				"herdr-hitl channel is afk: the person declared themselves unavailable. Do not ask or notify on any channel and do not retry. Apply the autonomous/quorum/defer policy from the herdr-hitl skill: decide in-scope reversible matters from evidence, defer only work that depends on a human-only decision, continue independent authorized work, and record the blocker in your final report.",
		};
	return {
		block: true,
		reason: `herdr-hitl channel returned an unknown channel "${channel}". The ask tool is blocked; run herdr-hitl doctor and take the safe reversible path.`,
	};
}

export default function herdrExtension(pi: ExtensionAPI) {
	const z = pi.zod;
	const profiles = loadProfiles();
	const agyModelProfiles = new Map<string, string>();
	for (const [profile, entry] of Object.entries(profiles.profiles)) {
		if (
			profiles.models[entry.model]?.provider === "agy" &&
			!agyModelProfiles.has(entry.model)
		)
			agyModelProfiles.set(entry.model, profile);
	}
	const agyModelKeys = [...agyModelProfiles.keys()];
	const initialModel =
		(profiles.models[profiles.profiles["agy-work"]?.model]?.provider === "agy"
			? profiles.profiles["agy-work"].model
			: undefined) ?? agyModelKeys[0];
	const initialMode =
		process.env.HERDR_ENV === "1" && process.env.HARNESS_DELEGATION === "agy"
			? ("agy" as const)
			: ("native" as const);
	let mode: "native" | "agy" | "off" = initialMode;
	let selectedModel = initialModel;
	const pending = new Map<string, AbortController>();
	const managedNames = new Set<string>();
	const removedNativeTools = new Set<string>();
	let activatedHerdrAgent = false;
	const managedEnv = () => ({
		...process.env,
		HARNESS_DELEGATION: "agy",
	});
	const runAgent = (
		args: string[],
		signal?: AbortSignal,
		name?: string,
		forceManaged = false,
	) =>
		run(
			args,
			signal,
			forceManaged || (name !== undefined && managedNames.has(name))
				? managedEnv()
				: undefined,
		);
	const stopWatches = () => {
		for (const controller of pending.values()) controller.abort();
		pending.clear();
	};
	const restrictNativeDelegation = async () => {
		const active = pi.getActiveTools();
		for (const name of ["task", "eval"])
			if (active.includes(name)) removedNativeTools.add(name);
		let next = active.filter((name) => name !== "task" && name !== "eval");
		if (!next.includes("herdr_agent")) {
			next = [...next, "herdr_agent"];
			activatedHerdrAgent = true;
		}
		if (
			next.length !== active.length ||
			next.some((name, index) => name !== active[index])
		)
			await pi.setActiveTools(next);
	};
	const restoreNativeDelegation = async () => {
		if (!removedNativeTools.size && !activatedHerdrAgent) return;
		const active = pi.getActiveTools();
		const keepHerdrAgent = activatedHerdrAgent && managedNames.size > 0;
		const next = active.filter(
			(name) =>
				!(name === "herdr_agent" && activatedHerdrAgent && !keepHerdrAgent),
		);
		for (const name of removedNativeTools)
			if (!next.includes(name)) next.push(name);
		removedNativeTools.clear();
		activatedHerdrAgent = keepHerdrAgent;
		if (
			next.length !== active.length ||
			next.some((name, index) => name !== active[index])
		)
			await pi.setActiveTools(next);
	};
	const applyMode = async (next: "native" | "agy" | "off") => {
		if (next === "native") await restoreNativeDelegation();
		else await restrictNativeDelegation();
		mode = next;
	};
	const resetSession = async () => {
		await restoreNativeDelegation();
		mode = "native";
		selectedModel = initialModel;
		await applyMode(initialMode);
	};
	const defaultProfile = () =>
		selectedModel === undefined
			? undefined
			: agyModelProfiles.get(selectedModel);
	const effectiveProfile = (requested?: string) => {
		const explicit = requested?.trim();
		return !explicit || explicit === "agy-work" ? defaultProfile() : explicit;
	};
	const status = () =>
		`Delegation mode: ${mode}; default worker model: ${selectedModel ?? "unavailable"}${defaultProfile() ? ` (profile ${defaultProfile()})` : ""}; pending workers: ${pending.size ? [...pending.keys()].sort().join(", ") : "none"}; managed workers: ${managedNames.size ? [...managedNames].sort().join(", ") : "none"}.${mode === "native" ? "" : " task and eval are disabled, including ordinary Eval computation."}`;
	const notify = (
		ctx: {
			ui: {
				notify(message: string, level: "info" | "warning" | "error"): void;
			};
		},
		message: string,
		level: "info" | "warning" | "error" = "info",
	) => ctx.ui.notify(message, level);

	pi.on("session_shutdown", stopWatches);
	pi.on("session_start", resetSession);
	pi.on("session_switch", resetSession);
	pi.registerCommand("delegation", {
		description:
			"Session delegation mode/status and the default AGY worker model",
		getArgumentCompletions: (prefix) =>
			[
				...["agy", "native", "off", "model"],
				...agyModelKeys.map((key) => `model ${key}`),
			]
				.filter((value) => value.startsWith(prefix))
				.map((value) => ({ value, label: value })),
		handler: async (args, ctx) => {
			const tokens = args.trim().split(/\s+/).filter(Boolean);
			const action = tokens[0];
			if (!action) {
				notify(ctx, status());
				return;
			}
			if (action === "model") {
				if (tokens.length > 2) {
					notify(ctx, "/delegation model [AGY model key]", "error");
					return;
				}
				let key = tokens[1];
				if (!key) {
					if (!ctx.hasUI || !ctx.isIdle()) {
						notify(
							ctx,
							"/delegation model requires an explicit AGY model key when interactive selection is unavailable.",
							ctx.isIdle() ? "info" : "warning",
						);
						return;
					}
					key = await ctx.ui.select(
						"Default AGY worker model",
						agyModelKeys.map((label) => ({
							label,
							description: `${profiles.models[label].provider}/${profiles.models[label].model}`,
						})),
					);
				}
				if (!key) return;
				if (!agyModelProfiles.has(key)) {
					notify(
						ctx,
						`Unknown AGY model key "${key}". Available: ${agyModelKeys.join(", ") || "none"}.`,
						"error",
					);
					return;
				}
				selectedModel = key;
				notify(ctx, status());
				return;
			}
			if (tokens.length !== 1 || !["agy", "native", "off"].includes(action)) {
				notify(
					ctx,
					"/delegation [agy|native|off|model [AGY model key]]",
					"error",
				);
				return;
			}
			if (action === "agy" && process.env.HERDR_ENV !== "1") {
				notify(
					ctx,
					"AGY delegation requires a Herdr session; delegation mode remains unchanged.",
					"warning",
				);
				return;
			}
			await applyMode(action as "native" | "agy" | "off");
			notify(ctx, status());
		},
	});
	pi.on("before_agent_start", async (event) => {
		if (mode !== "native") await restrictNativeDelegation();
		if (process.env.HERDR_ENV !== "1") return;
		const policy =
			mode === "agy" ? TRIAL_POLICY : mode === "off" ? OFF_POLICY : POLICY;
		const policies = new Set([POLICY, TRIAL_POLICY, OFF_POLICY]);
		const base = event.systemPrompt.filter((part) => !policies.has(part));
		if (
			base.length === event.systemPrompt.length &&
			event.systemPrompt.includes(policy)
		)
			return;
		return { systemPrompt: [...base, policy] };
	});
	pi.on("tool_call", (event) => {
		if (event.toolName === "ask") return askChannel();
		if (
			mode !== "native" &&
			(event.toolName === "task" || event.toolName === "eval")
		)
			return {
				block: true,
				reason:
					mode === "agy"
						? "AGY-first delegation uses herdr_agent. Do not create an intermediate native task or Eval worker."
						: "Delegation is off. Native task and Eval workers cannot be created in this session.",
			};
		if (
			event.toolName === "goal" &&
			event.input.op === "complete" &&
			pending.size
		)
			return {
				block: true,
				reason: `Collect Herdr workers before completing the goal: ${[...pending.keys()].join(", ")}.`,
			};
	});

	function watch(name: string) {
		pending.get(name)?.abort();
		const controller = new AbortController();
		pending.set(name, controller);
		// A bounded observational wait never submits another prompt or stops the worker.
		void runAgent(
			["wait", name, "--timeout", "300000"],
			controller.signal,
			name,
		).then((result) => {
			if (controller.signal.aborted || pending.get(name) !== controller) return;
			pending.delete(name);
			pi.sendMessage(
				{
					customType: "herdr-worker-result",
					content: `Herdr worker ${name}: ${result.content.map((part) => part.text).join("\n")}\nInspect the response and work before claiming completion. A failed wait leaves the worker retained; read it before deciding next steps.`,
					display: true,
				},
				{ triggerTurn: true, deliverAs: "aside" },
			);
		});
	}
	pi.registerTool({
		name: "herdr_run",
		label: "Herdr 실행",
		approval: "exec",
		description:
			"Run argv in a no-focus Herdr tab with the current cwd. Use only for long runs, human observation/collaboration, or an explicit visibility request. Short commands stay on native tools. detach:true requires name and returns a running handle for a server/REPL, not readiness; false waits for the real exit artifact and closes the owned tab. Logs remain on disk.",
		parameters: z.object({
			command: z.array(z.string()).min(1),
			name: z.string().optional(),
			detach: z
				.boolean()
				.optional()
				.describe(
					"Return after launch for an ongoing service or interactive program.",
				),
			timeoutMs: z
				.number()
				.int()
				.positive()
				.optional()
				.describe(
					"Wait deadline; default 300000ms. Timeout does not kill the retained process.",
				),
		}),
		execute: async (_id, params, signal, _update, ctx) => {
			const args = ["command", "--cwd", ctx.cwd];
			if (params.name) args.push("--name", params.name);
			if (params.detach) args.push("--detach");
			if (params.timeoutMs) args.push("--timeout", String(params.timeoutMs));
			return run([...args, "--", ...params.command], signal);
		},
	});
	pi.registerTool({
		name: "herdr_agent",
		label: "Herdr 세션",
		loadMode: initialMode === "agy" ? "essential" : "discoverable",
		approval: "exec",
		description:
			"Start or dispatch named OMP/AGY workers and revisit retained workers with list/read/send/wait/close. In AGY mode, a fresh worker needs an explicit brief and uses the selected default AGY model when profile is omitted or agy-work. Off mode prevents start/dispatch but preserves retained-worker operations.",
		parameters: z.object({
			action: z.enum([
				"start",
				"dispatch",
				"list",
				"read",
				"send",
				"wait",
				"close",
			]),
			profile: z.string().optional(),
			role: z.string().optional(),
			tasks: z
				.array(
					z.object({
						name: z.string(),
						role: z.string(),
						prompt: z.string(),
						profile: z.string().optional(),
					}),
				)
				.optional(),
			name: z.string().optional(),
			prompt: z.string().optional(),
			text: z.string().optional(),
			unattended: z.boolean().optional(),
			resume: z.boolean().optional(),
			wait: z.boolean().optional(),
			timeoutMs: z.number().int().positive().optional(),
			lines: z.number().int().positive().optional(),
		}),
		execute: async (_id, params, signal, _update, ctx) => {
			if (
				mode === "off" &&
				(params.action === "start" || params.action === "dispatch")
			)
				return {
					content: [
						{
							type: "text" as const,
							text: "Delegation is off; start and dispatch are disabled. Existing retained workers remain available.",
						},
					],
					isError: true,
				};
			if (params.action === "dispatch") {
				if (mode !== "agy")
					return {
						content: [
							{
								type: "text" as const,
								text: "dispatch requires /delegation agy.",
							},
						],
						isError: true,
					};
				if (
					!params.tasks?.length ||
					new Set(params.tasks.map((item) => item.name)).size !==
						params.tasks.length
				)
					return {
						content: [
							{
								type: "text" as const,
								text: "dispatch requires nonempty tasks with unique names.",
							},
						],
						isError: true,
					};
				if (
					params.tasks.some((item) => !item.role.trim() || !item.prompt.trim())
				)
					return {
						content: [
							{
								type: "text" as const,
								text: "Each assignment requires a role and nonempty brief.",
							},
						],
						isError: true,
					};
				const results = await Promise.all(
					params.tasks.map(async (item) => {
						const profile = effectiveProfile(item.profile);
						if (!profile)
							return {
								content: [
									{
										type: "text" as const,
										text: "No AGY worker profile is available.",
									},
								],
								isError: true,
							};
						// Keep recovery routed through the managed controller even if launch
						// creates a retained pane and then reports an error.
						managedNames.add(item.name);
						const result = await runAgent(
							[
								"agent",
								"--name",
								item.name,
								"--profile",
								profile,
								"--cwd",
								ctx.cwd,
								`--prompt=Role: ${item.role}\n${item.prompt}`,
							],
							signal,
							item.name,
							true,
						);
						if (!result.isError) watch(item.name);
						return result;
					}),
				);
				return {
					content: results.flatMap((result) => result.content),
					isError: results.some((result) => result.isError),
				};
			}
			const args: string[] = [];
			if (params.action === "list") return run(["list"], signal);
			if (!params.name)
				return {
					content: [{ type: "text" as const, text: "name이 필요합니다." }],
					isError: true,
				};
			if (params.action === "start") {
				if (mode === "agy" && !params.prompt?.trim())
					return {
						content: [
							{
								type: "text" as const,
								text: "A fresh worker requires an explicit assignment prompt.",
							},
						],
						isError: true,
					};
				const profile =
					mode === "agy"
						? effectiveProfile(params.profile)
						: params.profile?.trim() === "agy-work"
							? effectiveProfile(params.profile)
							: params.profile?.trim();
				if (!profile && mode === "agy")
					return {
						content: [
							{
								type: "text" as const,
								text: "No AGY worker profile is available.",
							},
						],
						isError: true,
					};
				if (!profile)
					return {
						content: [
							{
								type: "text" as const,
								text: "profile이 필요합니다. omp-profile list로 조회하세요.",
							},
						],
						isError: true,
					};
				if (mode === "agy") managedNames.add(params.name);
				args.push(
					"agent",
					"--name",
					params.name,
					"--profile",
					profile,
					"--cwd",
					ctx.cwd,
				);
				if (params.prompt !== undefined)
					args.push(
						`--prompt=${params.role ? `Role: ${params.role}\n` : ""}${params.prompt}`,
					);
				if (params.unattended) args.push("--unattended");
				if (params.resume) args.push("--resume");
			} else {
				if (params.action === "close" && !managedNames.has(params.name))
					return {
						content: [
							{
								type: "text" as const,
								text: "close is available only for delegation-managed workers.",
							},
						],
						isError: true,
					};
				args.push(params.action, params.name);
				if (params.action === "send" && params.text === undefined)
					return {
						content: [{ type: "text" as const, text: "text가 필요합니다." }],
						isError: true,
					};
				if (params.action === "read" && params.lines)
					args.push("--lines", String(params.lines));
			}
			if (params.wait) args.push("--wait");
			if (params.timeoutMs) args.push("--timeout", String(params.timeoutMs));
			if (params.action === "send" && params.text !== undefined)
				args.push("--", params.text);
			if (
				pending.has(params.name) &&
				(params.action === "send" || params.action === "close")
			)
				return {
					content: [
						{
							type: "text" as const,
							text: `Worker ${params.name} still has an outstanding assignment. Read/wait for its result before sending another assignment or closing it.`,
						},
					],
					isError: true,
				};
			const result = await runAgent(
				args,
				signal,
				params.name,
				mode === "agy" && params.action === "start",
			);
			if (!result.isError && params.action === "wait") {
				pending.get(params.name)?.abort();
				pending.delete(params.name);
			}
			if (!result.isError && params.action === "close") {
				managedNames.delete(params.name);
				if (mode === "native") await restoreNativeDelegation();
			}
			if (
				managedNames.has(params.name) &&
				!result.isError &&
				!params.wait &&
				!params.unattended &&
				(params.action === "start" || params.action === "send")
			)
				watch(params.name);
			return result;
		},
	});
}
