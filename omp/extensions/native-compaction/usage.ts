import type { NativeWindow } from "./types";

/** Claude's top-level usage excludes compaction; iterations are the billing source. */
export function nativeUsage(window: NativeWindow) {
	const usage = window.usage;
	const totals = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
	if (!usage) return totals;
	if (window.format === "anthropic-messages") {
		const iterations = Array.isArray(usage.iterations)
			? usage.iterations
			: [usage];
		for (const iteration of iterations) {
			if (!iteration || typeof iteration !== "object") continue;
			totals.input += Number(iteration.input_tokens ?? 0);
			totals.output += Number(iteration.output_tokens ?? 0);
			totals.cacheRead += Number(iteration.cache_read_input_tokens ?? 0);
			totals.cacheWrite += Number(iteration.cache_creation_input_tokens ?? 0);
		}
	} else {
		const details = usage.input_tokens_details as
			| { cached_tokens?: number }
			| undefined;
		totals.cacheRead = Number(
			usage.cachedInputTokens ?? details?.cached_tokens ?? 0,
		);
		totals.input =
			Number(usage.inputTokens ?? usage.input_tokens ?? 0) - totals.cacheRead;
		totals.output = Number(usage.outputTokens ?? usage.output_tokens ?? 0);
	}
	return totals;
}
