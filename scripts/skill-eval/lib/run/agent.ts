/**
 * The evaluated agent: command construction, the injected skill text, the
 * default `claude -p` runner, and stream-json parsing. Tests replace the
 * runner so they never start a real agent.
 */

import { spawn } from "node:child_process";
import { closeSync, openSync } from "node:fs";
import type { RunMeta } from "../schema.ts";

export interface AgentInvocation {
	command: string;
	args: string[];
	cwd: string;
	env: Record<string, string>;
	timeoutMs: number;
	/** stdout is written here verbatim (the stream-json transcript). */
	stdoutPath: string;
	stderrPath: string;
}

export interface AgentOutcome {
	/** Exit code; `null` when the process ended by a signal or never started. */
	rc: number | null;
	timedOut: boolean;
}

export type AgentRunner = (inv: AgentInvocation) => Promise<AgentOutcome>;

export function systemAppendText(skills: { name: string; skillMd: string }[]): string {
	const head = [
		"# Installed skills",
		"",
		"The user has installed the following skill(s) for this session. Their full instructions are below and apply to this task as if the user had invoked them. Each skill's other files are readable under `.skills/<name>/` relative to the working directory; resolve relative links in a skill against its directory.",
	].join("\n");
	const sections = skills.map((s) => `## Skill: ${s.name}\n\n${s.skillMd.trimEnd()}`);
	return `${[head, ...sections].join("\n\n").trimEnd()}\n`;
}

export function buildAgentArgs(opts: {
	prompt: string;
	model: string;
	effort: string | null;
	appendFile: string | null;
}): string[] {
	const args = ["-p", opts.prompt, "--model", opts.model];
	if (opts.effort) args.push("--effort", opts.effort);
	args.push(
		"--output-format",
		"stream-json",
		"--verbose",
		"--disable-slash-commands",
		"--no-session-persistence",
		"--strict-mcp-config",
		"--permission-mode",
		"bypassPermissions",
	);
	if (opts.appendFile) args.push("--append-system-prompt-file", opts.appendFile);
	return args;
}

/**
 * Variables that tie a process to the caller's own Claude Code session. They
 * are dropped so an evaluated run neither joins that session nor inherits its
 * effort; everything else, including `CLAUDE_CONFIG_DIR`, is inherited.
 */
export const SESSION_ENV = [
	"CLAUDECODE",
	"CLAUDE_CODE_ENTRYPOINT",
	"CLAUDE_CODE_SESSION_ID",
	"CLAUDE_CODE_CHILD_SESSION",
	"CLAUDE_CODE_SESSION_ATTENDED",
	"CLAUDE_CODE_MESSAGING_SOCKET",
	"CLAUDE_CODE_MESSAGING_TOKEN",
	"CLAUDE_AGENT_SDK_VERSION",
	"CLAUDE_EFFORT",
	"CLAUDE_PID",
];

export function agentEnv(base: NodeJS.ProcessEnv = process.env): Record<string, string> {
	const env: Record<string, string> = {};
	for (const [k, v] of Object.entries(base)) if (v !== undefined && !SESSION_ENV.includes(k)) env[k] = v;
	return env;
}

/** Process groups of running agents, killed if the runner itself is interrupted. */
export const activeGroups = new Set<number>();

function killGroup(pid: number, signal: NodeJS.Signals): void {
	try {
		process.kill(-pid, signal);
	} catch {
		// The group is already gone.
	}
}

/** Spawns the agent in its own process group and kills the whole group on timeout. */
export const spawnAgent: AgentRunner = (inv) =>
	new Promise((resolve) => {
		const out = openSync(inv.stdoutPath, "w");
		const err = openSync(inv.stderrPath, "w");
		let timedOut = false;
		let killTimer: ReturnType<typeof setTimeout> | undefined;
		const child = spawn(inv.command, inv.args, {
			cwd: inv.cwd,
			env: inv.env,
			stdio: ["ignore", out, err],
			detached: true,
		});
		closeSync(out);
		closeSync(err);
		const pid = child.pid;
		if (pid) activeGroups.add(pid);
		const timer = setTimeout(() => {
			if (!pid) return;
			timedOut = true;
			killGroup(pid, "SIGTERM");
			killTimer = setTimeout(() => killGroup(pid, "SIGKILL"), 10_000);
		}, inv.timeoutMs);
		const finish = (rc: number | null) => {
			clearTimeout(timer);
			if (killTimer) clearTimeout(killTimer);
			if (pid) {
				// Reap stragglers that outlived the main process.
				killGroup(pid, "SIGKILL");
				activeGroups.delete(pid);
			}
			resolve({ rc, timedOut });
		};
		child.on("error", () => finish(null));
		child.on("close", (code) => finish(code));
	});

export function killActiveGroups(): void {
	for (const pid of activeGroups) killGroup(pid, "SIGKILL");
	activeGroups.clear();
}

export interface TranscriptSummary {
	/** `result` of the last `type:"result"` event; `null` when there is none. */
	final: string | null;
	usage: RunMeta["usage"];
	costUsd: number | null;
	numTurns: number | null;
}

const num = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : 0);

export function parseTranscript(text: string): TranscriptSummary {
	let result: Record<string, unknown> | null = null;
	for (const line of text.split("\n")) {
		if (!line.trim()) continue;
		try {
			const event = JSON.parse(line);
			if (event && typeof event === "object" && event.type === "result") result = event;
		} catch {
			// Non-JSON noise is kept in the transcript but ignored here.
		}
	}
	if (!result) return { final: null, usage: null, costUsd: null, numTurns: null };
	const u = result.usage as Record<string, unknown> | undefined;
	return {
		final: typeof result.result === "string" ? result.result : null,
		usage: u
			? {
					inputTokens: num(u.input_tokens),
					outputTokens: num(u.output_tokens),
					cacheReadTokens: num(u.cache_read_input_tokens),
					cacheCreationTokens: num(u.cache_creation_input_tokens),
				}
			: null,
		costUsd: typeof result.total_cost_usd === "number" ? result.total_cost_usd : null,
		numTurns: typeof result.num_turns === "number" ? result.num_turns : null,
	};
}
