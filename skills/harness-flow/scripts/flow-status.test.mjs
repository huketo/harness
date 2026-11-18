// Contract tests for skills/harness-flow/scripts/flow-status against synthetic repositories.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, before, test } from "node:test";

const STATUS = join(import.meta.dirname, "flow-status");
const env = { ...process.env, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1" };
let root;

before(() => (root = mkdtempSync(join(tmpdir(), "flow-status-"))));
after(() => rmSync(root, { recursive: true, force: true }));

/** A git repository holding `files`, all tracked. */
function repo(name, files) {
	const dir = join(root, name);
	execFileSync("git", ["init", "-q", dir], { env });
	for (const [path, text] of Object.entries(files)) {
		mkdirSync(dirname(join(dir, path)), { recursive: true });
		writeFileSync(join(dir, path), text);
	}
	execFileSync("git", ["-C", dir, "add", "-A"], { env });
	return dir;
}

function status(dir) {
	const run = spawnSync(STATUS, [dir], { encoding: "utf8", env });
	assert.equal(run.status, 0, run.stderr);
	const rows = run.stdout.trim().split("\n").map((line) => line.split("\t"));
	const state = Object.fromEntries(rows.filter(([layer]) => layer !== "next").map(([, item, value]) => [item, value]));
	const [, next, reason] = rows.find(([layer]) => layer === "next");
	return { state, next, reason };
}

const table = (...rows) => `# Demo\n\n## Rules and enforcement\n\n| Rule | Enforced by |\n| --- | --- |\n${rows.join("\n")}\n`;
const verify = { ".agents/skills/verify-demo/SKILL.md": "---\nname: verify-demo\ndescription: Synthetic.\n---\n" };
const base = { "src/app.ts": "export const a = 1;\n", "mise.toml": "[tasks.check]\nrun = \"true\"\n", ".gitlab-ci.yml": "check: {}\n" };

test("an empty repository starts with repo-bootstrap", () => {
	const { state, next } = status(repo("empty", { "README.md": "# Empty\n" }));
	assert.equal(state.sources, "none");
	assert.equal(next, "repo-bootstrap");
});

test("a repository with only tool configuration and documents counts as having no source", () => {
	const { state, next } = status(repo("config-only", { "eslint.config.js": "export default [];\n", ".prettierrc.js": "x\n", "mise.toml": "[tasks.check]\nrun = \"true\"\n", "AGENTS.md": table() }));
	assert.equal(state.sources, "none");
	assert.equal(next, "repo-bootstrap");
});

test("an existing repository without the rule table starts with repo-init", () => {
	const { state, next } = status(repo("no-table", { ...base, "AGENTS.md": "# Demo\n" }));
	assert.equal(state["rule-table"], "missing");
	assert.equal(next, "repo-init");
});

test("a table under the heading counts only with the Rule and Enforced by header", () => {
	const agents = "# Demo\n\n## Rules and enforcement\n\n| Planned coverage | Owner |\n| --- | --- |\n| lint | team |\n";
	assert.equal(status(repo("wrong-header", { ...base, "AGENTS.md": agents })).next, "repo-init");
});

test("an escaped pipe inside a reason does not hide an unenforced row", () => {
	const { next, reason } = status(repo("escaped", { ...base, ...verify, "AGENTS.md": table("| A | unenforced: needs a \\| b check |") }));
	assert.equal(next, "correct");
	assert.match(reason, /^1 unenforced/);
});

test("a Rules and enforcement heading without a table does not count as the rule table", () => {
	const { state, next } = status(repo("heading-only", { ...base, "AGENTS.md": "# Demo\n\n## Rules and enforcement\n\nTo do.\n\n## Other\n\n| A | B |\n| --- | --- |\n" }));
	assert.equal(state["rule-table"], "missing");
	assert.equal(next, "repo-init");
});

test("only the Enforced by column of the rule table counts as unenforced", () => {
	const agents = `${table("| A | judgment |", "| unenforced words in the rule | `mise run check` |")}\n## Other\n\n| X | Y |\n| --- | --- |\n| a | unenforced |\n`;
	const { state, next } = status(repo("other-tables", { ...base, ...verify, "AGENTS.md": agents }));
	assert.match(state["rule-table"] ?? "", /present/);
	assert.equal(next, "none");
});

test("a check script entry is required, not a dependency named check", () => {
	const files = { "src/app.ts": "x\n", ".gitlab-ci.yml": "c: {}\n", "AGENTS.md": table(), "package.json": '{"scripts":{"test":"node --test"},"devDependencies":{"check":"1.0.0"}}' };
	const { state, next, reason } = status(repo("dependency-named-check", files));
	assert.equal(state["check-command"], "missing");
	assert.equal(next, "repo-bootstrap");
	assert.match(reason, /existing repository/);
	const notString = { ...files, "package.json": '{"scripts":{"check":false}}' };
	assert.equal(status(repo("check-false", notString)).state["check-command"], "missing");
});

test("an existing repository without one check command or CI goes to repo-bootstrap's existing-repository section", () => {
	const { state, next, reason } = status(repo("no-ci", { "src/app.ts": "x\n", "package.json": '{"scripts":{"check":"tsc"}}', "AGENTS.md": table() }));
	assert.equal(state["check-command"], "present");
	assert.equal(state.ci, "missing");
	assert.equal(next, "repo-bootstrap");
	assert.match(reason, /existing repository/);
});

test("without a verification skill the next step is verify-init, and full-send is not ready", () => {
	const { state, next } = status(repo("no-verify", { ...base, "AGENTS.md": table() }));
	assert.equal(state["full-send-ready"], "no");
	assert.equal(next, "verify-init");
});

test("unenforced rows send the repository to correct", () => {
	const dir = repo("debt", { ...base, ...verify, "AGENTS.md": table("| A | `unenforced`: owed. |", "| B | judgment |", "| C | unenforced: owed |") });
	const { state, next, reason } = status(dir);
	assert.equal(state["full-send-ready"], "yes");
	assert.equal(next, "correct");
	assert.match(reason, /^2 unenforced/);
});

test("a repository with the base in place has no fixed next step", () => {
	const { state, next } = status(repo("done", { ...base, ...verify, "AGENTS.md": table("| A | `mise run check` |"), "eslint.config.js": "no-restricted-imports\n" }));
	assert.equal(state.lint, "present");
	assert.equal(state["boundary-rules"], "present");
	assert.equal(next, "none");
});

test("boundary rules count only when a root lint or dependency configuration declares them", () => {
	const elsewhere = { ...base, "skills/x/templates/eslint.config.js": "no-restricted-imports\n", "scripts/detect.sh": "grep no-restricted-imports\n" };
	assert.equal(status(repo("mentioned-only", elsewhere)).state["boundary-rules"], "missing");
	assert.equal(status(repo("cruiser", { ...base, ".dependency-cruiser.cjs": "module.exports = {};\n" })).state["boundary-rules"], "present");
});

test("it refuses a directory outside a git repository", () => {
	const dir = mkdtempSync(join(root, "plain-"));
	assert.equal(spawnSync(STATUS, [dir], { encoding: "utf8", env }).status, 2);
});
