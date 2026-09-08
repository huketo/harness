import { expect, test } from "bun:test";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import nativeCompaction from "./index";
import { encodeWindow, marker, STATE_KEY } from "./state";

async function extension() {
	const handlers = new Map<string, Function>();
	const commands = new Map<string, unknown>();
	await nativeCompaction({
		on: (name: string, handler: Function) => handlers.set(name, handler),
		registerCommand: (name: string, command: unknown) =>
			commands.set(name, command),
	} as unknown as ExtensionAPI);
	return { handlers, commands };
}

test("ordinary OpenAI and Claude compaction stays with OMP even without a custom runtime stamp", async () => {
	const { handlers } = await extension();
	for (const provider of ["openai-codex", "anthropic"]) {
		const notices: string[] = [];
		const ctx = {
			model: {
				provider,
				id: provider === "anthropic" ? "claude-fable-5-1" : "gpt-6-astra",
			},
			sessionManager: { getBranch: () => [] },
			ui: { notify: (message: string) => notices.push(message) },
		};
		await handlers.get("session_start")?.({}, ctx);
		const result = await handlers.get("session_before_compact")?.(
			{ branchEntries: [], signal: new AbortController().signal },
			ctx,
		);
		expect(result).toBeUndefined();
		expect(notices).toEqual([]);
	}
});

test("OMP remote state does not re-enter the retired native compactor", async () => {
	const { handlers } = await extension();
	const result = await handlers.get("session_before_compact")?.(
		{
			branchEntries: [
				{
					type: "compaction",
					preserveData: {
						openaiRemoteCompaction: {
							provider: "openai-codex",
							replacementHistory: [],
						},
					},
				},
			],
			signal: new AbortController().signal,
		},
		{
			model: { provider: "openai-codex", id: "gpt-6-astra" },
			ui: { notify() {} },
		},
	);
	expect(result).toBeUndefined();
});

test("legacy replay survives until a newer native boundary replaces it", async () => {
	const { handlers } = await extension();
	const stored = encodeWindow({
		provider: "openai-codex",
		model: "gpt-6-astra",
		format: "openai-responses",
		items: [{ type: "compaction", encrypted_content: "opaque" }],
	});
	const branch: { type: string; preserveData?: Record<string, unknown> }[] = [
		{ type: "compaction", preserveData: { [STATE_KEY]: stored } },
	];
	const ctx = { sessionManager: { getBranch: () => branch } };
	const event = {
		payload: { input: [{ role: "user", content: marker(stored) }] },
	};
	expect(await handlers.get("before_provider_request")!(event, ctx)).toEqual({
		input: [{ type: "compaction", encrypted_content: "opaque" }],
	});
	branch.push({ type: "reset_boundary" });
	expect(
		await handlers.get("before_provider_request")!(event, ctx),
	).toBeUndefined();
});

test("malformed legacy state cannot fall through to a marker-only summary", async () => {
	const { handlers } = await extension();
	const branch = [
		{ type: "compaction", preserveData: { [STATE_KEY]: { version: 2 } } },
	];
	const ctx = {
		sessionManager: { getBranch: () => branch },
		ui: { notify() {} },
	};
	await expect(handlers.get("session_start")!({}, ctx)).rejects.toThrow();
	expect(
		await handlers.get("session_before_compact")?.(
			{ branchEntries: branch },
			ctx,
		),
	).toEqual({ cancel: true });
	expect(branch[0].preserveData[STATE_KEY]).toEqual({ version: 2 });
});
