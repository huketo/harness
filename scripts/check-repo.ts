// Repository rules that used to live only in prose, enforced by `mise run check`. Each check exists because the
// mistake it rejects was made here more than once; AGENTS.md pairs every rule with the check that enforces it.
//   node scripts/check-repo.ts [repo]     exit 1 and one `path:line: problem. Fix` line per violation
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { validateEvals } from "./skill-eval/lib/evals.ts";

export interface Problem {
	path: string;
	line: number;
	message: string;
}

// YAML reads an unquoted `key: a: b` as a nested mapping and ` #` as a comment, so the skill loads without its text.
// This is not a YAML parser: it rejects the plain-scalar traps and unbalanced quotes, and accepts block scalars.
const PLAIN_SCALAR_TRAP = /: | #|^[\[{&*!|>%@`"']/;
const QUOTED = /^"(?:[^"\\]|\\.)*"$|^'(?:[^']|'')*'$/;
const BLOCK_SCALAR = /^[|>][+-]?\d*$/;

/** One top-level frontmatter key line: the key, the text after the colon, the block scalar's joined lines, and its 1-based line. */
export interface FrontmatterField {
	key: string;
	raw: string;
	block: string | null;
	line: number;
}

/**
 * The top-level key lines of a SKILL.md frontmatter block in file order, a repeated key once per line, or a problem
 * when the block is missing or not closed. YAML loaders keep a repeated key's last value.
 */
export function frontmatterFields(text: string): FrontmatterField[] | Omit<Problem, "path"> {
	const lines = text.split("\n");
	if (lines[0] !== "---") return { line: 1, message: "SKILL.md must start with a `---` frontmatter block." };
	const end = lines.indexOf("---", 1);
	if (end < 0) return { line: 1, message: "The frontmatter block is not closed. Add a `---` line after the last key." };
	const fields: FrontmatterField[] = [];
	for (let i = 1; i < end; i++) {
		const match = /^([A-Za-z][\w-]*):(?: (.*))?$/.exec(lines[i] ?? "");
		if (!match) continue; // nested or continuation lines belong to the key above
		const raw = (match[2] ?? "").trim();
		let block: string | null = null;
		if (BLOCK_SCALAR.test(raw)) {
			// The text is the indented lines that follow; an empty block is an empty value.
			const body = lines.slice(i + 1, end).findIndex((line) => !/^(\s+\S|\s*$)/.test(line));
			block = lines.slice(i + 1, body < 0 ? end : i + 1 + body).join(" ").trim();
		}
		fields.push({ key: match[1] ?? "", raw, block, line: i + 1 });
	}
	return fields;
}

/** Problems in one SKILL.md frontmatter block. `dir` is the skill's directory name. */
export function checkFrontmatter(text: string, dir: string): Omit<Problem, "path">[] {
	const fields = frontmatterFields(text);
	if (!Array.isArray(fields)) return [fields];
	const problems: Omit<Problem, "path">[] = [];
	const seen = new Map<string, string>();
	for (const { key, raw, block, line } of fields) {
		seen.set(key, block ?? raw);
		if (block === null && raw !== "" && !QUOTED.test(raw) && PLAIN_SCALAR_TRAP.test(raw)) {
			problems.push({ line, message: `\`${key}\` holds a colon-space, a space-hash, a leading YAML indicator, or unbalanced quotes. Wrap the whole value in double quotes and escape inner double quotes.` });
		}
	}
	const unquote = (value: string | undefined) => (value ?? "").replace(/^["']|["']$/g, "");
	if (unquote(seen.get("name")) !== dir) {
		problems.push({ line: 1, message: `\`name\` must equal the directory name. Set \`name: ${dir}\`.` });
	}
	if (unquote(seen.get("description")) === "") {
		problems.push({ line: 1, message: "`description` is missing or empty. Add a one-line `description:`." });
	}
	return problems;
}

/** Relative link targets in markdown, outside fenced and inline code, with their 1-based line numbers. */
export function relativeLinks(text: string): { target: string; line: number }[] {
	const found: { target: string; line: number }[] = [];
	let fence: string | null = null;
	text.split("\n").forEach((raw, index) => {
		// A fence closes only on a bare marker of the same character at least as long as the one that opened it, so a
		// three-backtick example inside a four-backtick fence stays inside.
		const marker = /^\s*(```+|~~~+)/.exec(raw)?.[1];
		if (fence === null) {
			if (marker) {
				fence = marker;
				return;
			}
		} else {
			if (marker && marker[0] === fence[0] && marker.length >= fence.length && /^\s*(```+|~~~+)\s*$/.test(raw)) fence = null;
			return;
		}
		const line = raw.replace(/(`+).*?\1/g, "");
		for (const match of line.matchAll(/\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)/g)) {
			const target = (match[1] ?? "").split("#")[0] ?? "";
			if (target === "" || /^[a-z][a-z0-9+.-]*:/i.test(target) || target.startsWith("/") || target.includes("{{")) continue;
			found.push({ target, line: index + 1 });
		}
	});
	return found;
}

function markdownFiles(repo: string, dir: string, out: string[] = []): string[] {
	for (const entry of readdirSync(join(repo, dir), { withFileTypes: true })) {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) {
			if (SKIPPED_DIRS.has(entry.name)) continue;
			markdownFiles(repo, path, out);
		} else if (entry.name.endsWith(".md")) out.push(path);
	}
	return out;
}

// Templates and eval fixtures hold links that resolve only after they are copied into another repository.
const SKIPPED_DIRS = new Set(["node_modules", ".git", "archived", "var", "templates", "fixtures", "evals", "third-party"]);

/** Skills that predate the cases rule, one name per line. The list only shrinks: a skill leaves it when it gains cases. */
export const EVALS_OWED = "scripts/evals-owed.txt";

/**
 * Every shared skill carries cases in `evals/evals.json` that the skill-eval runner can execute, or is still
 * listed in `EVALS_OWED`. A skill written without cases was never shown to change what an agent does.
 */
export function checkEvals(repo: string): Problem[] {
	const problems: Problem[] = [];
	if (!existsSync(join(repo, "skills"))) return problems;
	const owedLines = existsSync(join(repo, EVALS_OWED)) ? readFileSync(join(repo, EVALS_OWED), "utf8").split("\n") : [];
	const owed = new Map(owedLines.map((name, index) => [name.trim(), index + 1] as const).filter(([name]) => name !== "" && !name.startsWith("#")));
	for (const entry of readdirSync(join(repo, "skills"), { withFileTypes: true })) {
		if (!entry.isDirectory() || !existsSync(join(repo, "skills", entry.name, "SKILL.md"))) continue;
		const path = join("skills", entry.name, "evals", "evals.json");
		const line = owed.get(entry.name);
		owed.delete(entry.name);
		if (!existsSync(join(repo, path))) {
			if (line === undefined)
				problems.push({ path: join("skills", entry.name, "SKILL.md"), line: 1, message: `The skill has no ${path}. Follow the \`make-skill\` skill: write the cases, run them without the skill, and commit them with it.` });
			continue;
		}
		if (line !== undefined) problems.push({ path: EVALS_OWED, line, message: `\`${entry.name}\` now has cases. Delete this line.` });
		let data: unknown;
		try {
			data = JSON.parse(readFileSync(join(repo, path), "utf8"));
		} catch (error) {
			problems.push({ path, line: 1, message: `Not valid JSON (${(error as Error).message}). Fix the syntax.` });
			continue;
		}
		for (const message of validateEvals(data, join(repo, "skills", entry.name))) problems.push({ path, line: 1, message: `${message}.` });
	}
	for (const [name, line] of owed) problems.push({ path: EVALS_OWED, line, message: `\`${name}\` is not a skill in skills/. Delete this line.` });
	return problems;
}

export function checkRepo(repo: string): Problem[] {
	const problems: Problem[] = [];
	// Shared skills this checkout installs, and the project-local skills agents read while working here.
	for (const root of ["skills", ".agents/skills"]) {
		if (!existsSync(join(repo, root))) continue;
		for (const entry of readdirSync(join(repo, root), { withFileTypes: true })) {
			const path = join(root, entry.name, "SKILL.md");
			if (!entry.isDirectory() || !existsSync(join(repo, path))) continue;
			for (const problem of checkFrontmatter(readFileSync(join(repo, path), "utf8"), entry.name)) problems.push({ path, ...problem });
		}
	}

	problems.push(...checkEvals(repo));

	const roots = readdirSync(repo, { withFileTypes: true });
	const files = roots.filter((entry) => entry.isFile() && entry.name.endsWith(".md")).map((entry) => entry.name);
	for (const dir of ["docs", "skills", "plugin", "scripts", "codex", "t3", ".agents"]) if (existsSync(join(repo, dir))) markdownFiles(repo, dir, files);
	for (const path of files) {
		for (const { target, line } of relativeLinks(readFileSync(join(repo, path), "utf8"))) {
			let decoded = target;
			try {
				decoded = decodeURIComponent(target);
			} catch {}
			if (!existsSync(resolve(repo, dirname(path), decoded))) {
				problems.push({ path, line, message: `The link target ${target} does not exist. Point the link at the file's current path or remove it.` });
			}
		}
	}
	return problems;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const repo = resolve(process.argv[2] ?? join(dirname(fileURLToPath(import.meta.url)), ".."));
	const problems = checkRepo(repo);
	for (const { path, line, message } of problems) console.error(`${relative(process.cwd(), join(repo, path)) || path}:${line}: ${message}`);
	if (problems.length > 0) {
		console.error(`check-repo: ${problems.length} problem${problems.length === 1 ? "" : "s"}`);
		process.exit(1);
	}
	console.log("check-repo: skill frontmatter, skill cases, and relative links are consistent");
}
