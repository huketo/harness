// Generates agent permission settings from .rulesync with rulesync, and applies them only when no existing setting
// would be lost. It closes three gaps measured with rulesync 43.8.0 (docs/FACTS.md):
//   - rulesync owns whole permission categories, so declaring `read` replaces every existing Read deny;
//   - rulesync always writes Claude Code files under ~/.claude and ignores CLAUDE_CONFIG_DIR;
//   - in --global mode rulesync writes under $HOME (it ignores --output-roots) and bakes that HOME into agy paths.
// So rulesync runs in a throwaway HOME seeded with copies of the real files; array entries it dropped are put back
// (the installer only ever adds), any other loss refuses the whole apply, and results are written to the real paths
// with a timestamped backup of each replaced file.
import { spawnSync } from "node:child_process";
import { chmodSync, copyFileSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

/** Agents rulesync configures, the settings file it merges into for each, and the directory that marks it installed. */
export const AGENTS = [
	{ target: "claudecode", file: ".claude/settings.json", marker: ".claude" },
	{ target: "antigravity-cli", file: ".gemini/antigravity-cli/settings.json", marker: ".gemini/antigravity-cli" },
] as const;

export interface GenerateOptions {
	repo: string;
	home: string;
	claudeDir: string;
	/** Path of the rulesync executable. */
	rulesync: string;
}

export interface FilePlan {
	target: string;
	prev: string | null;
	next: string;
	added: string[];
	restored: string[];
	lost: string[];
}

export interface GeneratePlan {
	files: FilePlan[];
	log: string[];
	skipped: string[];
}

/** Real location of a file that rulesync wrote at `rel` under the staging HOME. */
export function realPath(rel: string, home: string, claudeDir: string): string {
	return rel.startsWith(".claude/") ? join(claudeDir, rel.slice(".claude/".length)) : join(home, rel);
}

/** `dir` as rulesync source text: `~/...` when it is under `home`, otherwise absolute. */
export function homeRelative(dir: string, home: string): string {
	const rel = relative(home, dir);
	return rel && !rel.startsWith("..") && !rel.startsWith("/") ? `~/${rel}` : rel === "" ? "~" : dir;
}

/** Fill the source templates and drop lines the substitution made identical to an earlier one. */
export function renderSource(text: string, { home, claudeDir }: { home: string; claudeDir: string }): string {
	const filled = text.replaceAll("{{CLAUDE_CONFIG_DIR}}", homeRelative(claudeDir, home));
	const seen = new Set<string>();
	return filled
		.split("\n")
		.filter((line) => {
			const key = line.trim();
			if (!key.startsWith('"')) return true;
			if (seen.has(key)) return false;
			seen.add(key);
			return true;
		})
		.join("\n");
}

function stable(value: Json): string {
	if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
	if (value && typeof value === "object")
		return `{${Object.keys(value)
			.sort()
			.map((k) => `${JSON.stringify(k)}:${stable(value[k])}`)
			.join(",")}}`;
	return JSON.stringify(value);
}

/** Leaf facts of a parsed config: scalars by key path, array items as set members of their path. */
export function facts(value: Json, path = "", out = new Set<string>()): Set<string> {
	if (Array.isArray(value)) for (const item of value) out.add(`${path}[]=${stable(item)}`);
	else if (value && typeof value === "object") for (const [k, v] of Object.entries(value)) facts(v, path ? `${path}.${k}` : k, out);
	else out.add(`${path}=${stable(value)}`);
	return out;
}

function isObject(value: Json | undefined): value is { [key: string]: Json } {
	return !!value && typeof value === "object" && !Array.isArray(value);
}

/**
 * Put back into `next` every array item of `prev` that `next` no longer has at the same path, appended after
 * `next`'s own items. Returns the restored facts. Scalars are not touched: a changed scalar stays a loss.
 */
export function restoreArrays(prev: Json, next: Json, path = ""): string[] {
	const restored: string[] = [];
	if (!isObject(prev) || !isObject(next)) return restored;
	for (const [key, before] of Object.entries(prev)) {
		const at = path ? `${path}.${key}` : key;
		const after = next[key];
		if (Array.isArray(before)) {
			if (after !== undefined && !Array.isArray(after)) continue;
			const current = (after as Json[] | undefined) ?? [];
			const have = new Set(current.map(stable));
			const missing = before.filter((item) => !have.has(stable(item)));
			if (!missing.length) continue;
			next[key] = [...current, ...missing];
			restored.push(...missing.map((item) => `${at}[]=${stable(item)}`));
		} else if (isObject(before)) {
			if (after === undefined) continue;
			restored.push(...restoreArrays(before, after, at));
		}
	}
	return restored;
}

/** Compare a staged file with the real one, restoring dropped array items; `lost` is what would still disappear. */
export function reconcile(prev: string | null, staged: string): Omit<FilePlan, "target"> {
	if (prev === null) return { prev, next: staged, added: [...lines(staged)], restored: [], lost: [] };
	let before: Json;
	let after: Json;
	try {
		before = JSON.parse(prev);
		after = JSON.parse(staged);
	} catch {
		const a = lines(prev);
		const b = lines(staged);
		return { prev, next: staged, added: [...b].filter((l) => !a.has(l)), restored: [], lost: [...a].filter((l) => !b.has(l)) };
	}
	const restored = restoreArrays(before, after);
	const next = restored.length ? `${JSON.stringify(after, null, 2)}\n` : staged;
	const a = facts(before);
	const b = facts(after);
	return {
		prev,
		next,
		added: [...b].filter((f) => !a.has(f)),
		restored,
		lost: [...a].filter((f) => !b.has(f)),
	};
}

function lines(text: string): Set<string> {
	return new Set(
		text
			.split("\n")
			.map((l) => l.trim())
			.filter(Boolean),
	);
}

function walk(dir: string): string[] {
	if (!existsSync(dir)) return [];
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		return statSync(path).isDirectory() ? walk(path) : [path];
	});
}

/** Run rulesync in a staging HOME and plan the writes to the real HOME. Writes nothing outside a temp directory. */
export function generate(opts: GenerateOptions): GeneratePlan {
	const { repo, home, claudeDir, rulesync } = opts;
	const agents = AGENTS.filter((a) => existsSync(a.target === "claudecode" ? claudeDir : join(home, a.marker)));
	const skipped = AGENTS.filter((a) => !agents.includes(a)).map((a) => a.target);
	if (!agents.length) return { files: [], log: [], skipped };

	const work = mkdtempSync(join(tmpdir(), "hstack-generate-"));
	try {
		const input = join(work, "input");
		const stage = join(work, "home");
		cpSync(join(repo, ".rulesync"), input, { recursive: true });
		for (const file of walk(input)) writeFileSync(file, renderSource(readFileSync(file, "utf8"), { home, claudeDir }));
		for (const { file } of agents) {
			const src = realPath(file, home, claudeDir);
			if (!existsSync(src)) continue;
			mkdirSync(dirname(join(stage, file)), { recursive: true });
			copyFileSync(src, join(stage, file));
		}
		mkdirSync(stage, { recursive: true });
		const before = new Map(walk(stage).map((f) => [f, readFileSync(f, "utf8")]));

		// The executable may be a symlink to the CLI script or a shell shim (mise installs either); both start Node
		// through `env node`, so the Node running this script goes first on PATH.
		const env: NodeJS.ProcessEnv = { ...process.env, HOME: stage, PATH: `${dirname(process.execPath)}:${process.env.PATH ?? ""}` };
		delete env.CLAUDE_CONFIG_DIR;
		const targets = agents.map((a) => a.target).join(",");
		const run = spawnSync(rulesync, ["generate", "--global", "-t", targets, "-f", "permissions", "--input-roots", input], {
			cwd: work,
			env,
			encoding: "utf8",
			timeout: 120_000,
		});
		const log = `${run.stdout ?? ""}${run.stderr ?? ""}`
			.split("\n")
			.filter((l) => l && !/^\s/.test(l) && !/^(Written|🎉)/u.test(l));
		if (run.error || run.status !== 0) throw new Error(`rulesync generate failed (${run.error?.message ?? `exit ${run.status}`}): ${log.join(" | ")}`);

		// rulesync may resolve the staging HOME through a symlinked tmpdir, so replace both spellings.
		const spellings = [...new Set([stage, realpathSync(stage)])];
		const files: FilePlan[] = [];
		for (const file of walk(stage)) {
			const raw = readFileSync(file, "utf8");
			if (before.get(file) === raw) continue;
			const staged = spellings.reduce((text, s) => text.replaceAll(s, home), raw);
			const target = realPath(relative(stage, file), home, claudeDir);
			const prev = existsSync(target) ? readFileSync(target, "utf8") : null;
			if (prev === staged) continue;
			const plan = { target, ...reconcile(prev, staged) };
			if (plan.prev !== plan.next) files.push(plan);
		}
		return { files, log, skipped };
	} finally {
		rmSync(work, { recursive: true, force: true });
	}
}

/**
 * Replace `target` with `content` through a temporary sibling and a rename. A symlinked target is written through
 * to the file it resolves to, so a link a person keeps (a dotfiles checkout, a shared config directory) survives.
 * The file keeps its mode; a new file is created 0600 because agent settings can hold API keys.
 */
export function writeSettings(target: string, content: string) {
	const real = existsSync(target) ? realpathSync(target) : target;
	const mode = existsSync(real) ? statSync(real).mode & 0o777 : 0o600;
	mkdirSync(dirname(real), { recursive: true });
	const tmp = `${real}.tmp-${process.pid}`;
	writeFileSync(tmp, content, { mode });
	chmodSync(tmp, mode);
	renameSync(tmp, real);
}

/**
 * Write each planned file, keeping `<file>.hstack-bak-<stamp>` beside the file it replaces. A file whose content
 * changed after the plan was made is refused rather than overwritten, so a setting saved meanwhile is not lost.
 */
export function applyPlan(plan: GeneratePlan, stamp = new Date().toISOString().replace(/[:.]/g, "-")): string[] {
	if (plan.files.some((f) => f.lost.length)) throw new Error("refusing to apply a plan that loses existing settings");
	for (const { target, prev } of plan.files) {
		const now = existsSync(target) ? readFileSync(target, "utf8") : null;
		if (now !== prev) throw new Error(`${target} changed since the plan was made; run the installer again`);
	}
	return plan.files.map(({ target, next, prev }) => {
		if (prev !== null) {
			const real = realpathSync(target);
			copyFileSync(real, `${real}.hstack-bak-${stamp}`);
		}
		writeSettings(target, next);
		return target;
	});
}

/** The rulesync executable that mise installed for this checkout, or null. */
export function findRulesync(repo: string): string | null {
	if (process.env.HSTACK_RULESYNC) return process.env.HSTACK_RULESYNC;
	const which = spawnSync("mise", ["which", "rulesync"], { cwd: repo, encoding: "utf8" });
	if (which.status !== 0 || !which.stdout.trim()) return null;
	return which.stdout.trim();
}
