// Plans the symlinks that make this checkout's skills and Codex rules visible to each agent. Each step says what it
// would do; `apply` runs it. The rules are the ones docs/REPO.md states for repository-owned assets:
//   - a correct link stays; a link into this checkout is refreshed; anything else at the target is a conflict;
//   - a regular file replaced by a link is first copied to `<path>.bak`, and an existing different backup blocks it;
//   - slots that point at assets this checkout does not own (the shared skill tree, the user's CLAUDE.md) are
//     linked only when empty.
import { copyFileSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, realpathSync, rmSync, symlinkSync } from "node:fs";
import { basename, dirname, join } from "node:path";

export type StepKind = "change" | "unchanged" | "conflict" | "skip";
export interface Step {
	kind: StepKind;
	text: string;
	apply?: () => void;
}

export interface LinkOptions {
	repo: string;
	home: string;
	claudeDir: string;
	skillsOnly?: boolean;
}

function resolved(path: string): string | null {
	try {
		return realpathSync(path);
	} catch {
		return null;
	}
}

function isLink(path: string): boolean {
	try {
		return lstatSync(path).isSymbolicLink();
	} catch {
		return false;
	}
}

function exists(path: string): boolean {
	return isLink(path) || existsSync(path);
}

function inside(path: string, root: string): boolean {
	const real = resolved(path);
	const base = resolved(root) ?? root;
	return real !== null && (real === base || real.startsWith(`${base}/`));
}

function sameLink(target: string, src: string): boolean {
	return isLink(target) && resolved(target) !== null && resolved(target) === resolved(src);
}

function relink(target: string, src: string) {
	rmSync(target, { force: true });
	symlinkSync(src, target);
}

function sameFile(a: string, b: string): boolean {
	try {
		return lstatSync(b).isFile() && readFileSync(a).equals(readFileSync(b));
	} catch {
		return false;
	}
}

/** A directory the next steps write into; returns false (after adding a conflict) when something else is there. */
function ensureDir(dir: string, steps: Step[]): boolean {
	if (existsSync(dir) && lstatSync(dir).isDirectory()) return true;
	if (exists(dir) && !(isLink(dir) && resolved(dir) !== null && lstatSync(resolved(dir)!).isDirectory())) {
		steps.push({ kind: "conflict", text: `directory required but another entry exists: ${dir}` });
		return false;
	}
	if (exists(dir)) return true;
	steps.push({ kind: "change", text: `create directory: ${dir}`, apply: () => mkdirSync(dir, { recursive: true }) });
	return true;
}

function linkOwned(src: string, target: string, label: string, repo: string, steps: Step[]) {
	const name = basename(target);
	if (sameLink(target, src)) return steps.push({ kind: "unchanged", text: `unchanged ${label}: ${name} -> ${src}` });
	if (isLink(target)) {
		if (!inside(target, repo)) return steps.push({ kind: "conflict", text: `${label} ${target} links outside this checkout; left as is` });
		return steps.push({ kind: "change", text: `refresh ${label} link: ${target} -> ${src}`, apply: () => relink(target, src) });
	}
	if (exists(target)) return steps.push({ kind: "conflict", text: `${label} ${target} exists and is not a symlink; left as is` });
	steps.push({ kind: "change", text: `link ${label}: ${target} -> ${src}`, apply: () => symlinkSync(src, target) });
}

function linkForeign(src: string, target: string, steps: Step[], planned = false) {
	if (!exists(src) && !planned) return steps.push({ kind: "skip", text: `source missing: ${src}; ${target} not linked` });
	if (!ensureDir(dirname(target), steps)) return;
	if (sameLink(target, src)) return steps.push({ kind: "unchanged", text: `unchanged asset: ${target} -> ${src}` });
	if (exists(target)) return steps.push({ kind: "conflict", text: `${target} already exists and this checkout will not replace it` });
	steps.push({ kind: "change", text: `link asset: ${target} -> ${src}`, apply: () => symlinkSync(src, target) });
}

function migrateFile(src: string, target: string, repo: string, steps: Step[]) {
	if (!existsSync(src)) return steps.push({ kind: "conflict", text: `managed source is missing: ${src}` });
	if (!ensureDir(dirname(target), steps)) return;
	if (sameLink(target, src)) return steps.push({ kind: "unchanged", text: `unchanged asset: ${target} -> ${src}` });
	if (isLink(target)) {
		if (!inside(target, repo)) return steps.push({ kind: "conflict", text: `${target} links outside this checkout; left as is` });
		return steps.push({ kind: "change", text: `refresh asset link: ${target} -> ${src}`, apply: () => relink(target, src) });
	}
	if (!exists(target)) return steps.push({ kind: "change", text: `link asset: ${target} -> ${src}`, apply: () => symlinkSync(src, target) });
	if (!lstatSync(target).isFile()) return steps.push({ kind: "conflict", text: `${target} is not a regular file or symlink; left as is` });
	const backup = `${target}.bak`;
	if (exists(backup) && !sameFile(target, backup)) return steps.push({ kind: "conflict", text: `backup already exists and differs: ${backup}` });
	steps.push({
		kind: "change",
		text: `back up ${target} to ${backup} and replace it with a link to ${src}`,
		apply: () => {
			if (!exists(backup)) copyFileSync(target, backup);
			relink(target, src);
		},
	});
}

/** Skill directories of this checkout: every `skills/<name>/` that holds a SKILL.md. */
export function skillDirs(repo: string): string[] {
	const root = join(repo, "skills");
	if (!existsSync(root)) return [];
	return readdirSync(root)
		.sort()
		.map((name) => join(root, name))
		.filter((dir) => existsSync(join(dir, "SKILL.md")));
}

export function planLinks({ repo, home, claudeDir, skillsOnly = false }: LinkOptions): Step[] {
	const steps: Step[] = [];
	const shared = join(home, ".agents/skills");
	const skills = skillDirs(repo);

	// A shared tree that is itself a link into this checkout would send every per-skill link back into the source.
	if (isLink(shared) && inside(shared, repo)) {
		steps.push({ kind: "conflict", text: `${shared} is a symlink into this checkout; remove it and rerun to recreate it as a directory` });
		return steps;
	}
	const sharedReady = ensureDir(shared, steps);
	if (sharedReady) for (const dir of skills) linkOwned(dir, join(shared, basename(dir)), "skill", repo, steps);

	// Claude Code reads <config dir>/skills, not ~/.agents/skills. Each link resolves through the shared tree, the way
	// the skills CLI fills that directory, so it still ends in this checkout.
	const claudeSkills = join(claudeDir, "skills");
	if (ensureDir(claudeSkills, steps))
		for (const dir of skills) {
			const viaShared = join(shared, basename(dir));
			const ownedOrPlanned = inside(viaShared, repo) || !exists(viaShared);
			if (ownedOrPlanned) linkOwned(viaShared, join(claudeSkills, basename(dir)), "Claude skill", repo, steps);
			else steps.push({ kind: "conflict", text: `Claude skill ${basename(dir)} skipped: ${viaShared} is not owned by this checkout` });
		}
	if (skillsOnly) return steps;

	// Antigravity CLI reads its skills and global rules from two slots that hold assets this checkout does not own:
	// the shared skill tree and the user's Claude Code instructions. Linking them keeps one source of each.
	const agyConfig = join(home, ".gemini/config");
	linkForeign(shared, join(agyConfig, "skills"), steps, sharedReady);
	linkForeign(join(claudeDir, "CLAUDE.md"), join(agyConfig, "rules/AGENTS.md"), steps);

	// Codex loads every *.rules file in ~/.codex/rules; default.rules there is Codex's own.
	migrateFile(join(repo, "codex/harness.rules"), join(home, ".codex/rules/harness.rules"), repo, steps);
	return steps;
}
