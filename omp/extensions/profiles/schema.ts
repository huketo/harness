/**
 * Shared, dependency-free profile/model resolution logic for the harness
 * "profiles" extension (loaded in-process by OMP) and its standalone CLI
 * (`omp/profiles.ts`, invoked as a bare script outside any OMP process).
 *
 * Deliberately imports nothing from `@oh-my-pi/*` packages: the standalone
 * CLI runs outside the omp process, and those packages' native addon
 * (`@oh-my-pi/pi-natives`) fails to resolve when imported from a script that
 * isn't `omp` itself (confirmed: `bun -e 'import("@oh-my-pi/pi-coding-agent")'`
 * throws "Failed to load pi_natives native addon" even for the lighter
 * `@oh-my-pi/pi-utils`). This module therefore only uses Node/Bun builtins.
 */
import * as fs from "node:fs";
import * as path from "node:path";

export type Runner = "omp" | "agy";

/** Idle-boundary input budget; AGY's separate runtime has no OMP compaction policy. */
export interface CompactionPolicy {
	thresholdPercent: number | null;
}

export interface ModelEntry {
	provider: string;
	model: string;
	effort: string;
	prompt: string;
	compaction: CompactionPolicy;
}

export interface ProfileEntry {
	model: string;
	effort?: string;
	purpose: string;
}

export interface ProfilesFile {
	version: 1;
	models: Record<string, ModelEntry>;
	profiles: Record<string, ProfileEntry>;
}

export interface ProfilesState {
	version: 1;
	/** Per-model effort override, independent of any profile. */
	modelEffort: Record<string, string>;
	/** Per-profile effort override, independent of the model's own default/override. */
	profileEffort: Record<string, string>;
}

/**
 * OMP built-in/custom role name -> purpose profile name, per the roles this
 * harness's config.apply.sh actually declares (modelRoles keys: default,
 * designer, mid, plan, slow, smol, task, tiny, vision, advisor, commit).
 * Only roles that resolve to an omp-runner profile belong here: a built-in
 * role selects a model within the CURRENT OMP session, never a separate agy
 * process.
 */
export const ROLE_PURPOSE_MAP: Record<string, string> = {
	default: "frontend",
	designer: "frontend",
	plan: "orchestrate",
	slow: "best",
	mid: "code",
	task: "code",
	smol: "economical",
	tiny: "economical",
	commit: "economical",
	vision: "best",
	advisor: "hard-code",
};

/** The 12 contractually-required purpose names, avoiding built-in role names on purpose. */
export const REQUIRED_PURPOSES = [
	"frontend",
	"orchestrate",
	"hard-code",
	"code",
	"general",
	"best",
	"economical",
	"mechanical",
	"search",
	"media",
	"automation",
	"fallback",
] as const;

// omp/extensions/profiles/schema.ts -> repo root is two levels above omp/.
// realpath so a symlinked extension root (e.g. ~/.omp/agent/extensions/harness-profiles)
// still resolves to the real harness checkout, not the symlink's own directory.
const REPO_ROOT = fs.realpathSync(path.join(import.meta.dir, "..", "..", ".."));
const PROFILES_PATH = path.join(REPO_ROOT, "omp", "profiles.json");
const STATE_FILENAME = "harness-profiles-state.json";

export function loadProfiles(): ProfilesFile {
	const raw = fs.readFileSync(PROFILES_PATH, "utf8");
	const parsed = JSON.parse(raw) as ProfilesFile;
	if (parsed.version !== 1) {
		throw new Error(
			`${PROFILES_PATH}: unsupported version ${String(parsed.version)}`,
		);
	}
	return parsed;
}

/** Resolve a model entry's prompt file to its text, or undefined if unset/missing. */
export function resolvePromptText(entry: ModelEntry): string | undefined {
	if (!entry.prompt) return undefined;
	const abs = path.join(REPO_ROOT, "omp", entry.prompt);
	try {
		const text = fs.readFileSync(abs, "utf8").trim();
		return text.length > 0 ? text : undefined;
	} catch (error) {
		throw new Error(`Cannot read model prompt ${abs}: ${error}`);
	}
}

export function loadState(agentDir: string): ProfilesState {
	const statePath = path.join(agentDir, STATE_FILENAME);
	try {
		const raw = fs.readFileSync(statePath, "utf8");
		const parsed = JSON.parse(raw) as Partial<ProfilesState>;
		return {
			version: 1,
			modelEffort: parsed.modelEffort ?? {},
			profileEffort: parsed.profileEffort ?? {},
		};
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
		return { version: 1, modelEffort: {}, profileEffort: {} };
	}
}

export function saveState(agentDir: string, state: ProfilesState): void {
	const statePath = path.join(agentDir, STATE_FILENAME);
	fs.mkdirSync(agentDir, { recursive: true });
	const temporary = `${statePath}.${process.pid}.tmp`;
	fs.writeFileSync(temporary, `${JSON.stringify(state, null, 2)}\n`, {
		mode: 0o600,
	});
	fs.renameSync(temporary, statePath);
}

export type EffortSource =
	| "profile-override"
	| "profile-default"
	| "model-override"
	| "model-default";

export interface ResolvedProfile {
	name: string;
	runner: Runner;
	provider: string;
	model: string;
	modelKey: string;
	effort: string;
	effortSource: EffortSource;
	purpose: string;
}

/**
 * Effective effort/model for a named profile, applying independent override
 * layers in priority order:
 *   1. a live `/effort` (or CLI `effort set`) override saved AGAINST THIS PROFILE
 *   2. the static `effort` this profile declares in profiles.json (if any)
 *   3. a live effort override saved against the profile's MODEL (independent of profile)
 *   4. the model's own static default effort
 */
export function resolveProfile(
	profiles: ProfilesFile,
	state: ProfilesState,
	name: string,
): ResolvedProfile {
	const profile = profiles.profiles[name];
	if (!profile) {
		const known = Object.keys(profiles.profiles).sort().join(", ");
		throw new Error(`Unknown profile "${name}". Known profiles: ${known}`);
	}
	const modelEntry = profiles.models[profile.model];
	if (!modelEntry) {
		throw new Error(
			`Profile "${name}" references unknown model key "${profile.model}"`,
		);
	}
	const runner: Runner = modelEntry.provider === "agy" ? "agy" : "omp";

	let effort: string;
	let effortSource: EffortSource;
	if (state.profileEffort[name] !== undefined) {
		effort = state.profileEffort[name];
		effortSource = "profile-override";
	} else if (profile.effort !== undefined) {
		effort = profile.effort;
		effortSource = "profile-default";
	} else if (state.modelEffort[profile.model] !== undefined) {
		effort = state.modelEffort[profile.model];
		effortSource = "model-override";
	} else {
		effort = modelEntry.effort;
		effortSource = "model-default";
	}

	return {
		name,
		runner,
		provider: modelEntry.provider,
		model:
			modelEntry.provider === "agy" &&
			/^gemini-3\.8-flash-(low|medium|high)$/.test(modelEntry.model)
				? `gemini-3.8-flash-${effort}`
				: modelEntry.model,
		modelKey: profile.model,
		effort,
		effortSource,
		purpose: profile.purpose,
	};
}

/** Effective effort for a model key directly (bypassing any profile), independent of profile overrides. */
export function resolveModelEffort(
	profiles: ProfilesFile,
	state: ProfilesState,
	modelKey: string,
): { effort: string; source: "model-override" | "model-default" } {
	const modelEntry = profiles.models[modelKey];
	if (!modelEntry) throw new Error(`Unknown model key "${modelKey}"`);
	if (state.modelEffort[modelKey] !== undefined) {
		return { effort: state.modelEffort[modelKey], source: "model-override" };
	}
	return { effort: modelEntry.effort, source: "model-default" };
}

/** Compatibility roles are declaration-owned; personal effort overrides never rewrite them. */
export function resolveRoles(profiles: ProfilesFile): Record<string, string> {
	const state: ProfilesState = {
		version: 1,
		modelEffort: {},
		profileEffort: {},
	};
	const result: Record<string, string> = {};
	for (const [role, purpose] of Object.entries(ROLE_PURPOSE_MAP)) {
		const resolved = resolveProfile(profiles, state, purpose);
		if (resolved.runner === "omp") result[role] = selectorString(resolved);
	}
	return result;
}

/** `provider/model:effort`, OMP's own selector syntax. Throws for an agy-runner profile: no OMP selector exists for it. */
export function selectorString(resolved: ResolvedProfile): string {
	if (resolved.runner !== "omp") {
		throw new Error(
			`Profile "${resolved.name}" targets the agy runner (${resolved.model}); it has no OMP provider/model:effort selector. ` +
				`Use "argv ${resolved.name}" to launch it as a separate agy process instead.`,
		);
	}
	return `${resolved.provider}/${resolved.model}:${resolved.effort}`;
}

export interface ArgvOptions {
	/** Repeatable `--add-dir` values, supported by both the omp and agy CLIs. */
	addDir?: string[];
	/** agy's `--agent` flag (which agent the agy CLI session should run). Ignored for the omp runner. */
	agent?: string;
}

/**
 * Native CLI argv for launching this resolved profile as a fresh process.
 * Never emits a permission-widening flag (`--dangerously-skip-permissions`,
 * `--auto-approve`, `--approval-mode=yolo`, ...) -- callers that want reduced
 * approval friction must add that themselves, explicitly, at the call site.
 */
export function buildArgv(
	resolved: ResolvedProfile,
	options: ArgvOptions = {},
): string[] {
	const argv: string[] = [resolved.runner];
	if (resolved.runner === "omp") {
		argv.push("--harness-profile", resolved.name);
		argv.push("--model", `${resolved.provider}/${resolved.model}`);
		if (resolved.effort) argv.push("--thinking", resolved.effort);
	} else {
		argv.push("--model", resolved.model);
		if (resolved.effort) argv.push("--effort", resolved.effort);
		if (options.agent) argv.push("--agent", options.agent);
	}
	if (resolved.runner === "agy" && !options.addDir?.length)
		argv.push("--add-dir", process.cwd());
	for (const dir of options.addDir ?? []) {
		argv.push("--add-dir", dir);
	}
	return argv;
}

export function validateProfilesFile(profiles: ProfilesFile): string[] {
	const errors: string[] = [];
	for (const purpose of REQUIRED_PURPOSES) {
		if (!profiles.profiles[purpose])
			errors.push(`missing required purpose profile "${purpose}"`);
	}
	for (const [name, profile] of Object.entries(profiles.profiles)) {
		if (!profiles.models[profile.model]) {
			errors.push(
				`profile "${name}" references unknown model key "${profile.model}"`,
			);
		}
	}
	for (const role of Object.keys(ROLE_PURPOSE_MAP)) {
		const purpose = ROLE_PURPOSE_MAP[role];
		if (!profiles.profiles[purpose])
			errors.push(`role "${role}" maps to missing purpose "${purpose}"`);
	}
	return errors;
}
