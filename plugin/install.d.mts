// Types for scripts/install.ts, which imports this plain-JavaScript module.
export interface PluginStep {
	kind: "change" | "unchanged" | "conflict" | "skip";
	text: string;
	apply?: () => void;
}
export function plan(opts?: { env?: NodeJS.ProcessEnv; home?: string; claudeDir?: string; out?: string; repo?: string }): PluginStep[];
export function ensureAutoUpdate(settings: Record<string, unknown>, name: string, source: unknown): boolean;
