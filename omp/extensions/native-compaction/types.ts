import type { Context, FetchImpl, Model } from "@oh-my-pi/pi-ai";

export interface NativeWindow {
	provider: string;
	model: string;
	format: "openai-responses" | "anthropic-messages";
	items: Record<string, unknown>[];
	contextWindow?: number;
	/** Readable native summary, when the provider exposes one. */
	summary?: string;
	usage?: Record<string, unknown>;
}

export interface NativeRequest {
	model: Model;
	context: Context;
	apiKey: string;
	sessionId: string;
	signal?: AbortSignal;
	instructions: string;
	previous?: NativeWindow;
	fetch?: FetchImpl;
}
