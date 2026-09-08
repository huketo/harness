import { expect, test } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { ThinkingLevel } from "@oh-my-pi/pi-agent-core";
import type { Model } from "@oh-my-pi/pi-ai";
import type {
	CompactOptions,
	ExtensionAPI,
	ExtensionCommandContext,
} from "@oh-my-pi/pi-coding-agent";
import extension, { contextBudget } from "./index";
import {
	buildArgv,
	loadProfiles,
	loadState,
	resolveProfile,
	saveState,
} from "./schema";

// Model/profile effort precedence is the user's contract, not OMP's role assignment.
test("model and purpose overrides stay independent across save/reload", () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-profiles-"));
	try {
		const state = loadState(dir);
		state.modelEffort["gpt-5.6-sol"] = "max";
		state.profileEffort.code = "low";
		saveState(dir, state);
		const restored = loadState(dir);
		const profiles = loadProfiles();
		expect(resolveProfile(profiles, restored, "code").effort).toBe("low");
		expect(resolveProfile(profiles, restored, "general").effort).toBe("medium");
		expect(restored.modelEffort["gpt-5.6-sol"]).toBe("max");
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("personal CLI effort overrides do not create compatibility-role drift", () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-cli-"));
	const env = {
		...process.env,
		PI_CODING_AGENT_DIR: dir,
		PI_PROFILE: undefined,
	};
	const cli = (...args: string[]) => {
		const result = Bun.spawnSync(
			["bun", join(import.meta.dir, "../../profiles.ts"), ...args],
			{ env },
		);
		expect(result.exitCode).toBe(0);
		return result.stdout.toString().trim();
	};
	try {
		const roles = cli("roles");
		cli("effort", "set", "code", "low");
		expect(cli("selector", "code")).toBe("openai-codex/gpt-5.6-sol:low");
		expect(cli("selector", "code", "--defaults")).toBe(
			"openai-codex/gpt-5.6-sol:high",
		);
		expect(cli("roles")).toBe(roles);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("requested routes expose their selected effort capabilities", () => {
	const profiles = loadProfiles();
	const state = { version: 1 as const, modelEffort: {}, profileEffort: {} };
	const best = resolveProfile(profiles, state, "best");
	expect(best.model).toBe("gpt-6-astra");
	expect(best.effort).toBe("medium");
	const hardCode = resolveProfile(profiles, state, "hard-code");
	expect(hardCode.model).toBe("claude-fable-5-1");
	expect(hardCode.effort).toBe("medium");
	expect(resolveProfile(profiles, state, "economical").effort).toBe("max");
	const flash = resolveProfile(profiles, state, "media");
	expect(flash.model).toBe("gemini-3.8-flash-high");
	expect(flash.effort).toBe("high");
	expect(buildArgv(flash)).toContain(process.cwd());
	const fallback = resolveProfile(profiles, state, "fallback");
	expect(fallback.effort).toBeNull();
	expect(buildArgv(fallback)).not.toContain("--effort");
});

test("CLI rejects effort overrides for models without effort selection", () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-cli-unsupported-effort-"));
	try {
		const result = Bun.spawnSync(
			[
				"bun",
				join(import.meta.dir, "../../profiles.ts"),
				"effort",
				"set",
				"fallback",
				"high",
			],
			{
				env: {
					...process.env,
					PI_CODING_AGENT_DIR: dir,
					PI_PROFILE: undefined,
				},
			},
		);
		expect(result.exitCode).toBe(1);
		expect(result.stderr.toString()).toContain(
			'Model "agy-opus-thinking" does not support effort selection.',
		);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("input budget reserves output without subtracting it twice", () => {
	expect(contextBudget({ contextWindow: 272000, maxTokens: 128000 }, 70)).toBe(
		136000,
	);
	expect(contextBudget({ contextWindow: 1000000, maxTokens: 128000 }, 75)).toBe(
		750000,
	);
});

test("portable compaction finishes before a cross-provider switch; failure prevents switching", async () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-transition-"));
	try {
		const commands: Record<
			string,
			Parameters<ExtensionAPI["registerCommand"]>[1]
		> = {};
		// Provider doubles contain only fields consumed by this boundary; no provider call is claimed.
		const old = {
			id: "gpt-6-astra",
			provider: "openai-codex",
			contextWindow: 272000,
			maxTokens: 128000,
			thinking: { efforts: ["medium"] },
		} as unknown as Model;
		const next = {
			id: "claude-fable-5-1",
			provider: "anthropic",
			contextWindow: 1000000,
			maxTokens: 128000,
			thinking: { efforts: ["medium"] },
		} as unknown as Model;
		let native = true;
		let fail = true;
		let selected = old;
		const observed: string[] = [];
		const pi = {
			pi: { getAgentDir: () => dir },
			registerFlag() {},
			getFlag() {},
			registerCommand(
				name: string,
				command: Parameters<ExtensionAPI["registerCommand"]>[1],
			) {
				commands[name] = command;
			},
			on() {},
			appendEntry() {},
			async setModel(model: Model) {
				observed.push("switch");
				selected = model;
				return true;
			},
			setThinkingLevel() {},
		};
		extension(pi as unknown as ExtensionAPI); // Unused SDK operations are intentionally absent from this double.
		const ctx = {
			get model() {
				return selected;
			},
			models: { resolve: () => next },
			isIdle: () => true,
			getContextUsage: () => ({ tokens: 20000 }),
			ui: { notify() {} },
			sessionManager: {
				getBranch: () => [
					{ type: "message" },
					{
						type: "compaction",
						preserveData: native ? { openaiRemoteCompaction: {} } : {},
					},
				],
			},
			async compact(options: string | CompactOptions) {
				expect(selected).toBe(old);
				// OMP's soft method removes its provider-specific remote state.
				if (typeof options === "string" || options.mode !== "soft")
					throw new Error("Remote state requires a portable soft handoff");
				observed.push("compact");
				if (fail) throw new Error("summarizer unavailable");
				native = false;
			},
		} as unknown as ExtensionCommandContext;
		await commands.profile.handler("frontend", ctx);
		expect(selected).toBe(old);
		expect(observed).toEqual(["compact"]);
		fail = false;
		observed.length = 0;
		await commands.profile.handler("frontend", ctx);
		expect(selected).toBe(next);
		expect(observed).toEqual(["compact", "switch"]);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("ordinary high-context input is left to OMP automatic maintenance", async () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-input-"));
	try {
		const handlers = new Map<string, CallableFunction>();
		const model = {
			id: "gpt-6-astra",
			provider: "openai-codex",
			contextWindow: 272000,
			maxTokens: 128000,
		};
		extension({
			pi: { getAgentDir: () => dir },
			registerFlag() {},
			getFlag() {},
			registerCommand() {},
			on: (name: string, handler: CallableFunction) =>
				handlers.set(name, handler),
		} as unknown as ExtensionAPI);
		const ctx = {
			model,
			isIdle: () => true,
			hasUI: false,
			getContextUsage: () => ({ tokens: 250000 }),
			sessionManager: { getBranch: () => [{ type: "message" }] },
			ui: { notify() {} },
			async compact() {
				throw new Error("profile extension intercepted ordinary input");
			},
		};
		const sessionStart = handlers.get("session_start");
		const input = handlers.get("input");
		if (!sessionStart || !input) throw new Error("extension handlers missing");
		await sessionStart({ type: "session_start" }, ctx);
		expect(await input({ text: "continue" }, ctx)).toBeUndefined();
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

// Real preference storage, separate SDK session adapters. No model/provider response is mocked.
async function effortSession(
	dir: string,
	initialEntries: { type: "custom"; customType: string; data: unknown }[] = [],
) {
	const commands: Record<
		string,
		Parameters<ExtensionAPI["registerCommand"]>[1]
	> = {};
	const handlers = new Map<string, unknown>();
	let entries = structuredClone(initialEntries);
	let level = "medium" as ThinkingLevel;
	let model = {
		id: "gpt-5.6-sol",
		provider: "openai-codex",
		contextWindow: 272000,
		maxTokens: 128000,
		thinking: { efforts: ["low", "medium", "high", "max"] },
	} as unknown as Model;
	const pi = {
		pi: { getAgentDir: () => dir },
		registerFlag() {},
		getFlag: () => "code",
		registerCommand(
			name: string,
			command: Parameters<ExtensionAPI["registerCommand"]>[1],
		) {
			commands[name] = command;
		},
		on(name: string, handler: unknown) {
			handlers.set(name, handler);
		},
		appendEntry(customType: string, data: unknown) {
			entries.push({ type: "custom", customType, data });
		},
		getThinkingLevel: () => level,
		setThinkingLevel(value: ThinkingLevel) {
			level = value;
		},
		async setModel() {
			return true;
		},
	};
	const ctx = {
		get model() {
			return model;
		},
		models: { resolve: () => model },
		isIdle: () => true,
		getContextUsage: () => ({ tokens: 0 }),
		ui: {
			notify(_message: string, severity: string) {
				if (severity === "error") throw new Error(_message);
			},
		},
		sessionManager: { getBranch: () => entries },
	} as unknown as ExtensionCommandContext;
	extension(pi as unknown as ExtensionAPI);
	const emit = (name: string) => {
		const handler = handlers.get(name);
		if (typeof handler !== "function")
			throw new Error(`Missing session event handler: ${name}`);
		return handler({ type: name, systemPrompt: [] }, ctx);
	};
	await emit("session_start");
	return {
		command: (args: string) => commands.effort.handler(args, ctx),
		profile: (name: string) => commands.profile.handler(name, ctx),
		request: () => emit("before_agent_start"),
		level: () => level,
		entries: () => structuredClone(entries),
		selectModel(id: string) {
			model = { ...model, id };
		},
		async switchTo(next: typeof entries) {
			entries = structuredClone(next);
			level = "medium" as ThinkingLevel; // The host restored the destination session.
			await emit("session_switch");
		},
	};
}

test("session effort changes never change another session or shared preferences", async () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-effort-isolation-"));
	try {
		const shared = {
			version: 1 as const,
			modelEffort: { "gpt-5.6-sol": "medium" },
			profileEffort: {},
		};
		saveState(dir, shared);
		const a = await effortSession(dir);
		const b = await effortSession(dir);
		await a.command("high");
		await a.request();
		await b.request();
		expect(a.level()).toBe("high");
		expect(b.level()).toBe("medium");
		expect(loadState(dir)).toEqual(shared);
		const transcript = a.entries();
		const resumed = await effortSession(dir, transcript);
		await resumed.request();
		expect(resumed.level()).toBe("high");
		await a.switchTo([]);
		await a.request();
		expect(a.level()).toBe("medium");
		await a.switchTo(transcript);
		await a.request();
		expect(a.level()).toBe("high");
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("session effort overrides profile changes until reset or explicit profile selection", async () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-effort-precedence-"));
	try {
		saveState(dir, {
			version: 1,
			modelEffort: { "gpt-5.6-sol": "medium" },
			profileEffort: {},
		});
		const a = await effortSession(dir);
		const b = await effortSession(dir);
		await a.command("high");
		await b.command("low --profile");
		await a.request();
		await b.request();
		expect(a.level()).toBe("high");
		expect(b.level()).toBe("low");
		await a.command("reset");
		await a.request();
		expect(a.level()).toBe("low");
		await a.command("high");
		await a.command("medium --profile");
		await a.request();
		await b.request();
		expect(a.level()).toBe("medium");
		expect(b.level()).toBe("medium");
		await a.command("high");
		await a.profile("general");
		await a.request();
		expect(a.level()).toBe("medium");
		expect(loadState(dir).modelEffort["gpt-5.6-sol"]).toBe("medium");
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("native model switch cannot leave an unrelated profile selected after a session effort change", async () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-effort-model-switch-"));
	try {
		const shared = { version: 1 as const, modelEffort: {}, profileEffort: {} };
		saveState(dir, shared);
		const session = await effortSession(dir);
		session.selectModel("gpt-6-astra");
		await session.command("high");
		await expect(session.command("low --profile")).rejects.toThrow();
		expect(loadState(dir)).toEqual(shared);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});
