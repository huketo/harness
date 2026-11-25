import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { checkEvals, checkFrontmatter, checkRepo, EVALS_OWED, relativeLinks } from "./check-repo.ts";

function repoWith(files: Record<string, string>): string {
	const repo = mkdtempSync(join(tmpdir(), "check-repo-"));
	for (const [path, text] of Object.entries(files)) {
		mkdirSync(dirname(join(repo, path)), { recursive: true });
		writeFileSync(join(repo, path), text);
	}
	return repo;
}

const skill = (name: string, description: string) => `---\nname: ${name}\ndescription: ${description}\n---\n\n# Skill\n`;

test("rejects the unquoted description that once hid a skill's trigger text", () => {
	// The line commit de36d5f shipped; 26afff5 fixed it by quoting.
	const shipped = "Design, improve, and review product interfaces: accessibility, layout, UI copy.";
	const problems = checkFrontmatter(skill("awesome-interface", shipped), "awesome-interface");
	assert.equal(problems.length, 1);
	assert.equal(problems[0]?.line, 3);
	assert.match(problems[0]?.message ?? "", /double quotes/);
	assert.deepEqual(checkFrontmatter(skill("awesome-interface", JSON.stringify(shipped)), "awesome-interface"), []);
});

test("accepts plain values, block scalars, and nested keys", () => {
	const text = "---\nname: demo\ndescription: Review a change since a fixed point (commit, branch, tag).\nmetadata:\n  note: a: b\nlicense: MIT\n---\n";
	assert.deepEqual(checkFrontmatter(text, "demo"), []);
	assert.deepEqual(checkFrontmatter("---\nname: demo\ndescription: >-\n  Review: every change,\n  twice.\n---\n", "demo"), []);
	assert.deepEqual(checkFrontmatter("---\nname: demo\ndescription: |\n\n  After a blank line.\n---\n", "demo"), []);
	assert.match(checkFrontmatter("---\nname: demo\ndescription: |\n---\n", "demo")[0]?.message ?? "", /description/);
});

test("rejects quotes that do not close around the whole value", () => {
	for (const value of ['"Use the "preview" command."', '"unclosed', "'it's broken: here'", '"a": "b"']) {
		assert.equal(checkFrontmatter(skill("demo", value), "demo").length, 1, value);
	}
	assert.deepEqual(checkFrontmatter(skill("demo", '"Use the \\"preview\\" command: now."'), "demo"), []);
	assert.deepEqual(checkFrontmatter(skill("demo", "'it''s fine: here'"), "demo"), []);
});

test("checks every line of a repeated key and reads the last one", () => {
	// A Map keyed by name once dropped the first line's diagnostic.
	const repeated = "---\nname: demo\ndescription: Invalid: mapping\ndescription: Correct text.\n---\n";
	assert.deepEqual(checkFrontmatter(repeated, "demo").map((p) => p.line), [3]);
	assert.match(checkFrontmatter("---\nname: demo\ndescription: Set.\ndescription:\n---\n", "demo")[0]?.message ?? "", /description/);
});

test("requires a frontmatter block whose name is the directory and whose description is set", () => {
	assert.match(checkFrontmatter("# No frontmatter\n", "demo")[0]?.message ?? "", /must start/);
	assert.match(checkFrontmatter("---\nname: demo\n", "demo")[0]?.message ?? "", /not closed/);
	assert.match(checkFrontmatter(skill("other", "x"), "demo")[0]?.message ?? "", /name: demo/);
	assert.match(checkFrontmatter("---\nname: demo\n---\n", "demo")[0]?.message ?? "", /description/);
});

test("reads link targets outside code and skips URLs, anchors, and template placeholders", () => {
	const text = [
		"See [a](docs/a.md#part) and [site](https://example.com/x.md).",
		"`[inline](gone.md)` and `` [double](gone.md) `` and [anchor](#top) and [slot]({{GLOSSARY_ENTRY}}).",
		"```md",
		"[fenced](gone.md)",
		"```",
		"[after](after.md)",
		"````md",
		"```",
		"[nested](gone.md)",
		"```",
		"````",
		"[last](last.md)",
	].join("\n");
	assert.deepEqual(relativeLinks(text), [
		{ target: "docs/a.md", line: 1 },
		{ target: "after.md", line: 6 },
		{ target: "last.md", line: 12 },
	]);
});

test("reports a link whose target was removed and passes once the target exists", () => {
	// The shape of docs/guides/installation.md → ../../install.sh after the installer moved (commit 5fd802f).
	const files = {
		"skills/demo/SKILL.md": skill("demo", "Demo skill."), [EVALS_OWED]: "demo\n",
		"docs/guides/installation.md": "Run [install.sh](../../install.sh).\n",
		"skills/demo/templates/AGENTS.md": "[later](docs/agents/hitl.md)\n",
	};
	const broken = repoWith(files);
	const fixed = repoWith({ ...files, "install.sh": "" });
	try {
		assert.deepEqual(
			checkRepo(broken).map(({ path, line }) => `${path}:${line}`),
			["docs/guides/installation.md:1"],
		);
		assert.deepEqual(checkRepo(fixed), []);
	} finally {
		rmSync(broken, { recursive: true, force: true });
		rmSync(fixed, { recursive: true, force: true });
	}
});

test("reports a skill whose frontmatter is broken, by path", () => {
	const repo = repoWith({ "skills/demo/SKILL.md": skill("demo", "Use for: reviews."), [EVALS_OWED]: "demo\n" });
	try {
		assert.deepEqual(
			checkRepo(repo).map(({ path, line }) => `${path}:${line}`),
			["skills/demo/SKILL.md:3"],
		);
	} finally {
		rmSync(repo, { recursive: true, force: true });
	}
});

const cases = (name: string, patch: object = {}) =>
	JSON.stringify({ skill_name: name, evals: [{ id: 1, name: "routine", prompt: "Do the thing.", expected_output: "The thing is done.", files: [], expectations: ["The thing is done."], ...patch }] });

test("a skill without cases fails unless it is on the owed list, and the list only shrinks", () => {
	const repo = repoWith({
		"skills/fresh/SKILL.md": skill("fresh", "New."),
		"skills/older/SKILL.md": skill("older", "Old."),
		"skills/done/SKILL.md": skill("done", "Done."),
		"skills/done/evals/evals.json": cases("done"),
		[EVALS_OWED]: "# comment\nolder\ndone\ngone\n",
	});
	try {
		assert.deepEqual(
			checkEvals(repo).map(({ path, line, message }) => `${path}:${line}: ${message.split(".")[0]}`).sort(),
			[
				`${EVALS_OWED}:3: \`done\` now has cases`,
				`${EVALS_OWED}:4: \`gone\` is not a skill in skills/`,
				"skills/fresh/SKILL.md:1: The skill has no skills/fresh/evals/evals",
			],
		);
		writeFileSync(join(repo, EVALS_OWED), "older\n");
		mkdirSync(join(repo, "skills/fresh/evals"));
		writeFileSync(join(repo, "skills/fresh/evals/evals.json"), cases("fresh"));
		assert.deepEqual(checkEvals(repo), []);
	} finally {
		rmSync(repo, { recursive: true, force: true });
	}
});

test("rejects cases the runner could not execute", () => {
	const repo = repoWith({
		"skills/demo/SKILL.md": skill("demo", "Demo."),
		"skills/demo/evals/evals.json": cases("other", { name: "Has Spaces", files: ["fixtures/missing.md", "../SKILL.md"], expectations: [] }),
	});
	try {
		assert.deepEqual(
			checkRepo(repo).map(({ message }) => message),
			[
				'skill_name must equal the skill directory name "demo".',
				"evals[0]: name must be lowercase kebab (/^[a-z0-9]+(?:-[a-z0-9]+)*$/); it names the case directory.",
				"evals[0]: expectations must be a non-empty array of pass/fail statements.",
				'evals[0]: file "fixtures/missing.md" must be an existing plain file under evals/, reached through no symbolic link.',
				'evals[0]: file "../SKILL.md" must stay inside evals/.',
			],
		);
	} finally {
		rmSync(repo, { recursive: true, force: true });
	}
});
