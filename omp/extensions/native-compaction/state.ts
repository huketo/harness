import { createHash, randomUUID } from "node:crypto";
import type { NativeWindow } from "./types";

export const STATE_KEY = "harnessNativeCompaction";
export const PORTABLE_INSTRUCTIONS = "harness-native-portable:";
interface StoredWindow {
	version: 1;
	id: string;
	sha256: string;
	chunks: string[];
}
const decoded = new WeakMap<object, NativeWindow>();
export function encodeWindow(window: NativeWindow): StoredWindow {
	const json = JSON.stringify(window);
	const chunks: string[] = [];
	// OMP truncates individual persisted strings above 500K characters.
	for (let i = 0; i < json.length; i += 64000)
		chunks.push(json.slice(i, i + 64000));
	const stored: StoredWindow = {
		version: 1,
		id: randomUUID(),
		sha256: createHash("sha256").update(json).digest("hex"),
		chunks,
	};
	decoded.set(stored, window);
	return stored;
}
export function storedWindow(
	preserveData: Record<string, unknown> | undefined,
): StoredWindow | undefined {
	const value = preserveData?.[STATE_KEY];
	if (value === undefined) return;
	if (
		!value ||
		typeof value !== "object" ||
		(value as StoredWindow).version !== 1 ||
		typeof (value as StoredWindow).id !== "string" ||
		!Array.isArray((value as StoredWindow).chunks)
	)
		throw new Error("네이티브 압축 상태 형식이 올바르지 않습니다.");
	return value as StoredWindow;
}
export function decodeWindow(stored: StoredWindow): NativeWindow {
	const cached = decoded.get(stored);
	if (cached) return cached;
	if (!stored.chunks.every((chunk) => typeof chunk === "string"))
		throw new Error("네이티브 압축 데이터가 손상되었습니다.");
	const json = stored.chunks.join("");
	if (createHash("sha256").update(json).digest("hex") !== stored.sha256)
		throw new Error(
			"네이티브 압축 데이터의 무결성 검사에 실패했습니다. 원본 세션을 보존합니다.",
		);
	const window = JSON.parse(json) as NativeWindow;
	if (
		!window ||
		typeof window.provider !== "string" ||
		typeof window.model !== "string" ||
		!["openai-responses", "anthropic-messages"].includes(window.format) ||
		!Array.isArray(window.items) ||
		!window.items.every(
			(item) => item && typeof item === "object" && !Array.isArray(item),
		)
	)
		throw new Error("네이티브 압축 창이 올바르지 않습니다.");
	decoded.set(stored, window);
	return window;
}
export function marker(stored: StoredWindow): string {
	return `<harness-native-compaction id="${stored.id}"/>`;
}
function hasMarker(value: unknown, needle: string): boolean {
	if (typeof value === "string") return value.includes(needle);
	if (Array.isArray(value))
		return value.some((item) => hasMarker(item, needle));
	if (value && typeof value === "object") {
		const item = value as Record<string, unknown>;
		return hasMarker(item.text, needle) || hasMarker(item.content, needle);
	}
	return false;
}
/** Replace only our summary carrier, after OMP's provider serialization. */
export function replayWindow(payload: unknown, stored: StoredWindow): unknown {
	if (!payload || typeof payload !== "object") return payload;
	const body = payload as Record<string, unknown>;
	const field = Array.isArray(body.input)
		? "input"
		: Array.isArray(body.messages)
			? "messages"
			: undefined;
	if (!field) return payload;
	const items = body[field] as Record<string, unknown>[];
	const index = items.findIndex((item) => hasMarker(item, marker(stored)));
	if (index < 0) return payload;
	const window = decodeWindow(stored);
	if ((field === "input") !== (window.format === "openai-responses"))
		throw new Error(
			"다른 공급자로 전환하기 전에 /native-compact portable을 실행하세요.",
		);
	// Anthropic can coalesce adjacent user messages. Retain content after the carrier.
	const carrier = items[index];
	let suffix: Record<string, unknown>[] = [];
	if (Array.isArray(carrier.content)) {
		const cut = carrier.content.findIndex((part) =>
			hasMarker(part, marker(stored)),
		);
		if (cut >= 0 && cut + 1 < carrier.content.length)
			suffix = [{ ...carrier, content: carrier.content.slice(cut + 1) }];
	}
	const replayed: Record<string, unknown> = {
		...body,
		[field]: [
			...items.slice(0, index),
			...window.items,
			...suffix,
			...items.slice(index + 1),
		],
	};
	if (field === "messages") {
		const management = body.context_management as
			| { edits?: Record<string, unknown>[] }
			| undefined;
		// Replay requires the strategy too. OMP invokes dedicated native compaction
		// below the window limit; this ceiling avoids a second, hidden sampling pass.
		replayed.context_management = {
			...management,
			edits: [
				...(management?.edits ?? []).filter(
					(edit) => edit.type !== "compact_20260112",
				),
				{
					type: "compact_20260112",
					trigger: {
						type: "input_tokens",
						value: window.contextWindow ?? 1000000,
					},
				},
			],
		};
	}
	return replayed;
}
