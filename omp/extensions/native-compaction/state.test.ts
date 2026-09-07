import { expect, test } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type * as SessionModule from "@oh-my-pi/pi-coding-agent/session/session-manager";
import { loadOmp } from "./runtime";
import {
	decodeWindow,
	encodeWindow,
	marker,
	replayWindow,
	STATE_KEY,
	storedWindow,
} from "./state";
import type { NativeWindow } from "./types";

import { nativeUsage } from "./usage";

const { SessionManager } = await loadOmp<typeof SessionModule>(
	"@oh-my-pi/pi-coding-agent/session/session-manager",
);

test("opaque native window survives real OMP disk persistence and resume without duplicate history", async () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-native-state-"));
	const session = SessionManager.create(dir, dir);
	let reopened: SessionModule.SessionManager | undefined;
	const window: NativeWindow = {
		provider: "openai-codex",
		model: "gpt-6-astra",
		format: "openai-responses",
		items: [
			{
				type: "message",
				role: "user",
				content: [{ type: "input_text", text: "retained user" }],
			},
			{ type: "reasoning", id: "rs_native", encrypted_content: "reasoning" },
			{
				type: "function_call",
				call_id: "paired",
				name: "read",
				arguments: "{}",
			},
			{
				type: "function_call_output",
				call_id: "paired",
				output: "original result",
			},
			{
				type: "compaction",
				id: "cmp_native",
				encrypted_content: "opaque".repeat(110000),
			},
		],
	};
	try {
		session.appendMessage({
			role: "user",
			content: "old transcript",
			timestamp: 1,
		});
		const boundary = session.appendCustomEntry(
			"harness-native-compaction-boundary",
			{},
		);
		const encoded = encodeWindow(window);
		session.appendCompaction(marker(encoded), undefined, boundary, 100000, {
			fromExtension: true,
			preserveData: { [STATE_KEY]: encoded },
		});
		session.appendMessage({ role: "user", content: "continue", timestamp: 2 });
		await session.ensureOnDisk();
		await session.close();
		const file = session.getSessionFile();
		if (!file) throw new Error("Session file was not created");
		reopened = await SessionManager.open(file, dir);
		const compaction = reopened
			.getBranch()
			.find((entry) => entry.type === "compaction");
		if (!compaction) throw new Error("Compaction was not persisted");
		const stored = storedWindow(compaction.preserveData);
		if (!stored) throw new Error("Native window was not persisted");
		expect(decodeWindow(stored)).toEqual(window);
		const messages = reopened.buildSessionContext().messages;
		expect(messages.map((message) => message.role)).toEqual([
			"compactionSummary",
			"user",
		]);
		const next = {
			type: "message",
			role: "user",
			content: [{ type: "input_text", text: "continue" }],
		};
		expect(
			replayWindow(
				{ input: [{ role: "user", content: marker(stored) }, next] },
				stored,
			),
		).toEqual({ input: [...window.items, next] });
	} finally {
		await reopened?.close();
		await session.close();
		rmSync(dir, { recursive: true, force: true });
	}
});

test("Claude replay keeps a following user turn coalesced by the serializer", () => {
	const block = { type: "compaction", content: "Native summary" };
	const stored = encodeWindow({
		provider: "anthropic",
		model: "claude-fable-5-1",
		format: "anthropic-messages",
		items: [{ role: "assistant", content: [block] }],
	});
	const next = { type: "text", text: "Now continue" };
	const replayed = replayWindow(
		{
			messages: [
				{
					role: "user",
					content: [{ type: "text", text: marker(stored) }, next],
				},
			],
		},
		stored,
	) as Record<string, unknown>;
	expect(replayed.messages).toEqual([
		{ role: "assistant", content: [block] },
		{ role: "user", content: [next] },
	]);
	expect(replayed.context_management).toEqual({
		edits: [
			{
				type: "compact_20260112",
				trigger: { type: "input_tokens", value: 1000000 },
			},
		],
	});
	expect(() =>
		replayWindow(
			{ input: [{ role: "user", content: marker(stored) }] },
			stored,
		),
	).toThrow("다른 공급자");
});

test("corrupted persisted native state fails integrity verification", () => {
	const stored = JSON.parse(
		JSON.stringify(
			encodeWindow({
				provider: "anthropic",
				model: "claude-fable-5-1",
				format: "anthropic-messages",
				items: [
					{
						role: "assistant",
						content: [{ type: "compaction", content: "keep this decision" }],
					},
				],
			}),
		),
	);
	stored.chunks[0] = stored.chunks[0].replace(
		"keep this decision",
		"lose this decision",
	);
	expect(() => decodeWindow(stored)).toThrow("무결성");
});

test("compaction billing sums iterations rather than the non-compaction top-level usage", () => {
	const totals = nativeUsage({
		provider: "anthropic",
		model: "claude-fable-5-1",
		format: "anthropic-messages",
		items: [],
		usage: {
			input_tokens: 23,
			output_tokens: 10,
			iterations: [
				{
					type: "compaction",
					input_tokens: 118008,
					output_tokens: 263,
					cache_read_input_tokens: 1000,
				},
				{ type: "message", input_tokens: 23, output_tokens: 10 },
			],
		},
	});
	expect(totals).toEqual({
		input: 118031,
		output: 273,
		cacheRead: 1000,
		cacheWrite: 0,
	});
});
