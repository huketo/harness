// Temporary-local tests for the skill and rule links and for update.ts. No network, no real HOME.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readlinkSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { install } from "./install.ts";
import { planLinks } from "./links.ts";

const SOURCE = dirname(dirname(fileURLToPath(import.meta.url)));
const temps: string[] = [];
after(() => temps.forEach((dir) => rmSync(dir, { recursive: true, force: true })));

function temp(): string {
	const dir = realpathSync(mkdtempSync(join(tmpdir(), "hstack-install-")));
	temps.push(dir);
	return dir;
}

function skill(repo: string, name: string) {
	mkdirSync(join(repo, "skills", name), { recursive: true });
	writeFileSync(join(repo, "skills", name, "SKILL.md"), `---\nname: ${name}\n---\n`);
}

const isLink = (path: string) => existsSync(path) && lstatSync(path).isSymbolicLink();

function fixture() {
	const root = temp();
	const repo = join(root, "repo");
	const home = join(root, "home");
	mkdirSync(join(repo, "codex"), { recursive: true });
	writeFileSync(join(repo, "codex/harness.rules"), "prefix_rule()\n");
	skill(repo, "example");
	mkdirSync(home);
	return { root, repo, home, claudeDir: join(home, ".claude") };
}

async function runInstall(opts: Parameters<typeof install>[0]) {
	const lines: string[] = [];
	const code = await install({ ...opts, print: (line) => lines.push(line) });
	return { code, out: lines.join("\n") };
}

test("a plan writes nothing; skills-only links skills for every agent and leaves other configuration alone", async () => {
	const { repo, home, claudeDir } = fixture();
	const plan = await runInstall({ repo, home, claudeDir, skillsOnly: true });
	assert.equal(plan.code, 0);
	assert.match(plan.out, /would link skill/);
	assert.ok(!existsSync(join(home, ".agents")));

	mkdirSync(join(home, ".codex/rules"), { recursive: true });
	writeFileSync(join(home, ".codex/rules/default.rules"), "keep\n");
	assert.equal((await runInstall({ repo, home, claudeDir, skillsOnly: true, apply: true })).code, 0);
	assert.equal(realpathSync(join(home, ".agents/skills/example")), join(repo, "skills/example"));
	assert.equal(readlinkSync(join(claudeDir, "skills/example")), join(home, ".agents/skills/example"));
	assert.equal(readFileSync(join(home, ".codex/rules/default.rules"), "utf8"), "keep\n");
	assert.ok(!existsSync(join(home, ".codex/rules/harness.rules")) && !existsSync(join(home, ".gemini")));
	assert.ok(planLinks({ repo, home, claudeDir, skillsOnly: true }).every((s) => s.kind === "unchanged"));
});

test("Claude skills follow CLAUDE_CONFIG_DIR", async () => {
	const { repo, home } = fixture();
	const claudeDir = join(home, ".claude-work");
	assert.equal((await runInstall({ repo, home, claudeDir, skillsOnly: true, apply: true })).code, 0);
	assert.ok(isLink(join(claudeDir, "skills/example")));
	assert.ok(!existsSync(join(home, ".claude")));
});

test("foreign skills and links are conflicts that are reported and preserved", async () => {
	const { repo, home, claudeDir } = fixture();
	skill(repo, "taken");
	mkdirSync(join(home, ".agents/skills/taken"), { recursive: true });
	const result = await runInstall({ repo, home, claudeDir, skillsOnly: true, apply: true });
	assert.equal(result.code, 1);
	assert.match(result.out, /conflict: skill .*taken exists and is not a symlink/);
	assert.ok(!isLink(join(home, ".agents/skills/taken")));
	assert.ok(!existsSync(join(claudeDir, "skills/taken")));
	assert.ok(isLink(join(home, ".agents/skills/example")), "the other skills are still processed");
});

test("agy slots and Codex rules: a missing CLAUDE.md is skipped, a regular rules file is backed up once", () => {
	const { repo, home, claudeDir } = fixture();
	mkdirSync(join(home, ".codex/rules"), { recursive: true });
	writeFileSync(join(home, ".codex/rules/harness.rules"), "old\n");
	const steps = planLinks({ repo, home, claudeDir });
	assert.ok(steps.some((s) => s.kind === "skip" && s.text.includes("CLAUDE.md")));
	steps.forEach((s) => s.kind === "change" && s.apply?.());
	assert.equal(readFileSync(join(home, ".codex/rules/harness.rules.bak"), "utf8"), "old\n");
	assert.equal(readlinkSync(join(home, ".codex/rules/harness.rules")), join(repo, "codex/harness.rules"));
	assert.equal(readlinkSync(join(home, ".gemini/config/skills")), join(home, ".agents/skills"));
	assert.ok(!existsSync(join(home, ".gemini/config/rules/AGENTS.md")));

	mkdirSync(claudeDir, { recursive: true });
	writeFileSync(join(claudeDir, "CLAUDE.md"), "rules\n");
	planLinks({ repo, home, claudeDir }).forEach((s) => s.kind === "change" && s.apply?.());
	assert.equal(readlinkSync(join(home, ".gemini/config/rules/AGENTS.md")), join(claudeDir, "CLAUDE.md"));
	assert.ok(planLinks({ repo, home, claudeDir }).every((s) => s.kind === "unchanged"));
});

test("a shared skill tree that links into the checkout stops the run", () => {
	const { repo, home, claudeDir } = fixture();
	mkdirSync(join(home, ".agents"), { recursive: true });
	spawnSync("ln", ["-s", join(repo, "skills"), join(home, ".agents/skills")]);
	const steps = planLinks({ repo, home, claudeDir });
	assert.equal(steps.length, 1);
	assert.equal(steps[0].kind, "conflict");
});

function git(cwd: string, ...args: string[]) {
	const run = spawnSync("git", args, { cwd, encoding: "utf8", env: gitEnv });
	assert.equal(run.status, 0, `git ${args.join(" ")}: ${run.stderr}`);
	return run.stdout.trim();
}
const gitEnv = {
	...process.env,
	GIT_CONFIG_NOSYSTEM: "1",
	GIT_CONFIG_GLOBAL: "/dev/null",
	GIT_AUTHOR_NAME: "Test",
	GIT_AUTHOR_EMAIL: "test@example.invalid",
	GIT_COMMITTER_NAME: "Test",
	GIT_COMMITTER_EMAIL: "test@example.invalid",
};

test("update fast-forwards a clean main and reinstalls; previews, dirty work, topic branches, and divergence change nothing", () => {
	const root = temp();
	const home = join(root, "home");
	mkdirSync(home);
	const env = { ...gitEnv, HOME: home, CLAUDE_CONFIG_DIR: "" };
	delete (env as Record<string, string | undefined>).CLAUDE_CONFIG_DIR;
	git(root, "init", "-q", "--bare", "--initial-branch=main", "origin.git");
	git(root, "clone", "-q", "origin.git", "author");
	const author = join(root, "author");
	for (const file of ["install.ts", "links.ts", "safe-generate.ts", "update.ts"]) cpSync(join(SOURCE, "scripts", file), join(author, "scripts", file));
	cpSync(join(SOURCE, "package.json"), join(author, "package.json"));
	skill(author, "example");
	git(author, "add", ".");
	git(author, "commit", "-qm", "initial");
	git(author, "push", "-q", "origin", "main");
	git(root, "clone", "-q", "origin.git", "installed");
	const installed = join(root, "installed");
	const update = (...args: string[]) => spawnSync(process.execPath, [join(installed, "scripts/update.ts"), ...args], { encoding: "utf8", env });

	assert.equal(update("--skills-only").status, 0);
	assert.ok(isLink(join(home, ".agents/skills/example")) && isLink(join(home, ".claude/skills/example")));

	skill(author, "added");
	git(author, "add", ".");
	git(author, "commit", "-qm", "add-skill");
	git(author, "push", "-q", "origin", "main");
	const before = git(installed, "rev-parse", "HEAD");
	const preview = update("--skills-only", "--dry-run");
	assert.equal(preview.status, 0);
	assert.match(preview.stdout, /add-skill/);
	assert.equal(git(installed, "rev-parse", "HEAD"), before);
	assert.ok(!existsSync(join(home, ".agents/skills/added")));

	// A user's rebase preference must not change the fast-forward-only mechanism.
	git(installed, "config", "pull.rebase", "true");
	assert.equal(update("--skills-only").status, 0);
	assert.ok(isLink(join(home, ".agents/skills/added")) && isLink(join(home, ".claude/skills/added")));
	assert.equal(git(installed, "rev-parse", "HEAD"), git(author, "rev-parse", "HEAD"));

	assert.equal(update("--skills-only", "--with-config").status, 2);
	writeFileSync(join(installed, "untracked"), "dirty\n");
	assert.equal(update("--skills-only").status, 1);
	rmSync(join(installed, "untracked"));
	git(installed, "switch", "-qc", "topic");
	assert.equal(update("--skills-only").status, 1);
	git(installed, "switch", "-q", "main");

	writeFileSync(join(installed, "local"), "local\n");
	git(installed, "add", "local");
	git(installed, "commit", "-qm", "local");
	writeFileSync(join(author, "remote"), "remote\n");
	git(author, "add", "remote");
	git(author, "commit", "-qm", "remote");
	git(author, "push", "-q", "origin", "main");
	const local = git(installed, "rev-parse", "HEAD");
	assert.equal(update("--skills-only").status, 1);
	assert.equal(git(installed, "rev-parse", "HEAD"), local);
});
