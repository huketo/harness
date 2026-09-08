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
