import { realpathSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

const RUNNER = join(
	realpathSync(join(import.meta.dir, "../../..")),
	"herdr/scripts/harness-run.ts",
);
const POLICY =
	"Use Herdr for command execution only when it is long-running, needs live human observation, or supports human collaboration (server/debugger/REPL). Short reads, transforms, builds and tests stay on native tools. herdr_run detach:true starts a retained interactive terminal (name required); inspect readiness explicitly and use herdr_agent read/send/wait to control it. Finite runs close their tab automatically after results are captured. Use herdr_agent for independently visible, reusable OMP/AGY agents with explicit briefs. Built-in task agents remain accessible through Alt+A Agent Hub; they cannot be moved into Herdr.";

async function run(args: string[], signal?: AbortSignal) {
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
			reason: "herdr-hitl channel is messenger: nobody is watching this interface. Do not use the ask tool. Ask with the herdr-hitl CLI (bash: herdr-hitl ask …) under the message contract in the herdr-hitl skill and APPEND_SYSTEM.md, then act only on an explicit answer.",
		};
	if (channel === "afk")
		return {
			block: true,
			reason: "herdr-hitl channel is afk: the person declared themselves unavailable. Do not ask or notify on any channel and do not retry. Apply the autonomous/quorum/defer policy from the herdr-hitl skill: decide in-scope reversible matters from evidence, defer only work that depends on a human-only decision, continue independent authorized work, and record the blocker in your final report.",
		};
	return {
		block: true,
		reason: `herdr-hitl channel returned an unknown channel "${channel}". The ask tool is blocked; run herdr-hitl doctor and take the safe reversible path.`,
	};
}

export default function herdrExtension(pi: ExtensionAPI) {
	const z = pi.zod;
	pi.on("before_agent_start", (event) =>
		process.env.HERDR_ENV === "1" && !event.systemPrompt.includes(POLICY)
			? { systemPrompt: [...event.systemPrompt, POLICY] }
			: undefined,
	);
	pi.on("tool_call", (event) =>
		event.toolName === "ask" ? askChannel() : undefined,
	);
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
		approval: "exec",
		description:
			"Start a named OMP/AGY purpose profile in an independent retained Herdr tab, or list/read/send/wait on retained sessions (including herdr_run commands). Fresh agents need an explicit brief; same-name live agents are reused only with matching cwd/profile. AGY unattended:true requires prompt and validates process exit plus JSON SUCCESS; interactive AGY cannot reliably wait. resume:true resumes a captured session after its process exited. Readiness and task completion are distinct.",
		parameters: z.object({
			action: z.enum(["start", "list", "read", "send", "wait"]),
			profile: z.string().optional(),
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
			const args: string[] = [];
			if (params.action === "list") return run(["list"], signal);
			if (!params.name)
				return {
					content: [{ type: "text" as const, text: "name이 필요합니다." }],
					isError: true,
				};
			if (params.action === "start") {
				if (!params.profile)
					return {
						content: [
							{
								type: "text" as const,
								text: "profile이 필요합니다. omp-profile list로 조회하세요.",
							},
						],
						isError: true,
					};
				args.push(
					"agent",
					"--name",
					params.name,
					"--profile",
					params.profile,
					"--cwd",
					ctx.cwd,
				);
				if (params.prompt !== undefined) args.push(`--prompt=${params.prompt}`);
				if (params.unattended) args.push("--unattended");
				if (params.resume) args.push("--resume");
			} else {
				args.push(params.action, params.name);
				if (params.action === "send") {
					if (params.text === undefined)
						return {
							content: [{ type: "text" as const, text: "text가 필요합니다." }],
							isError: true,
						};
				}
				if (params.action === "read" && params.lines)
					args.push("--lines", String(params.lines));
			}
			if (params.wait) args.push("--wait");
			if (params.timeoutMs) args.push("--timeout", String(params.timeoutMs));
			if (params.action === "send" && params.text !== undefined)
				args.push("--", params.text);
			return run(args, signal);
		},
	});
}
