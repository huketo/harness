import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, test } from "node:test";
import { checkFrontmatter } from "../check-repo.ts";
import type { AgentInvocation } from "./lib/run/agent.ts";
import { gitText } from "./lib/run/skills.ts";
import { parseRouting } from "./lib/route/cases.ts";
import { descriptionOf, readDescriptions, ROUTE_SCOPE, ROUTE_SETTINGS, ROUTER_SYSTEM, routeArgs, routeRequest } from "./lib/route/classify.ts";
import { main, type RouteResults } from "./lib/route/runner.ts";

const roots: string[] = [];
function tmp(prefix = "skill-route-test-"): string {
	const dir = mkdtempSync(join(tmpdir(), prefix));
	roots.push(dir);
	return dir;
}
after(() => {
	for (const r of roots) rmSync(r, { recursive: true, force: true });
});

function sh(cwd: string, ...args: string[]): string {
	const res = spawnSync("git", args, {
		cwd,
		env: { ...process.env, GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@t", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@t" },
	});
	if (res.status !== 0) throw new Error(`git ${args.join(" ")}: ${res.stderr}`);
	return res.stdout.toString().trim();
}

function write(root: string, files: Record<string, string>): void {
	for (const [rel, body] of Object.entries(files)) {
		mkdirSync(join(root, rel, ".."), { recursive: true });
		writeFileSync(join(root, rel), body);
	}
}

const skillMd = (name: string, description: string) => `---\nname: ${name}\ndescription: ${description}\n---\n\n# ${name}\n`;

/** Two committed skills; the working tree then changes one description, which a run must not see. */
function setup(answers: Record<string, string | null> = {}) {
	const repo = tmp();
	sh(repo, "init", "-q", "-b", "main");
	write(repo, {
		"skills/alpha/SKILL.md": skillMd("alpha", '"Draw alpha things. Not for beta things."'),
		"skills/beta/SKILL.md": skillMd("beta", "Write beta documents from a brief."),
	});
	sh(repo, "add", ".");
	sh(repo, "commit", "-qm", "skills");
	const sha = sh(repo, "rev-parse", "HEAD");
	write(repo, { "skills/beta/SKILL.md": skillMd("beta", "UNCOMMITTED beta text.") });
	const routing = {
		suite: "demo-routing",
		version: 1,
		skills: {
			alpha: {
				should_fire: ["Draw an alpha.", "알파를 그려 주세요."],
				should_not_fire: [
					{ prompt: "Write the beta doc.", goes_to: "beta" },
					{ prompt: "Fix the build.", goes_to: "none" },
				],
			},
			beta: {
				// "Write the beta doc." repeats alpha's should_not_fire entry with the same expectation: one call.
				should_fire: ["Write the beta doc.", "베타 문서를 써 주세요."],
				should_not_fire: [{ prompt: "Draw an alpha.", goes_to: "alpha" }],
			},
		},
	};
	const casesFile = join(tmp(), "routing.json");
	writeFileSync(casesFile, JSON.stringify(routing, null, 2));
	const calls: AgentInvocation[] = [];
	/** Entries in each call's working directory when the call starts. */
	const cwdEntries: number[] = [];
	const lines: string[] = [];
	const outRoot = tmp();
	const deps = {
		repoRoot: repo,
		tmpRoot: tmp(),
		cwd: repo,
		agentCommand: "claude",
		env: {},
		log: (l: string) => lines.push(l),
		warn: (l: string) => lines.push(l),
		now: () => new Date("2026-01-02T03:04:05Z"),
		runAgent: async (inv: AgentInvocation) => {
			calls.push(inv);
			cwdEntries.push(readdirSync(inv.cwd).length);
			const request = inv.args[inv.args.indexOf("-p") + 1] ?? "";
			const prompt = /<request>\n([\s\S]*?)\n<\/request>/.exec(request)?.[1] ?? "";
			const answer = prompt in answers ? answers[prompt] : null;
			if (answer === null) return { rc: 1, timedOut: false };
			writeFileSync(inv.stdoutPath, `${JSON.stringify({ type: "result", result: answer, num_turns: 1 })}\n`);
			return { rc: 0, timedOut: false };
		},
	};
	const run = (...args: string[]) => main(["--cases", casesFile, "--out-root", outRoot, ...args], deps);
	const runDir = join(outRoot, "demo-routing", "run-2026-01-02T03-04-05Z");
	const results = (): RouteResults => JSON.parse(readFileSync(join(runDir, "results.json"), "utf8"));
	return { repo, sha, casesFile, calls, cwdEntries, lines, deps, run, runDir, results, routing };
}

const requestOf = (inv: AgentInvocation) => inv.args[inv.args.indexOf("-p") + 1] ?? "";

describe("description-based routing run", () => {
	test("sends one classification call per distinct prompt, with every description from the commit", async () => {
		const t = setup({
			"Draw an alpha.": "alpha",
			"알파를 그려 주세요.": "alpha",
			"Write the beta doc.": "beta",
			"Fix the build.": "none",
			"베타 문서를 써 주세요.": "beta",
		});
		assert.equal(await t.run("--model", "test-model"), 0);
		const prompts = t.calls.map((c) => /<request>\n([\s\S]*?)\n<\/request>/.exec(requestOf(c))?.[1]);
		assert.deepEqual(prompts.toSorted(), ["Draw an alpha.", "Fix the build.", "Write the beta doc.", "베타 문서를 써 주세요.", "알파를 그려 주세요."].toSorted());
		for (const call of t.calls) {
			const request = requestOf(call);
			assert.match(request, /- alpha: Draw alpha things\. Not for beta things\.\n/);
			assert.match(request, /- beta: Write beta documents from a brief\.\n/);
			assert.doesNotMatch(request, /UNCOMMITTED/);
			assert.deepEqual(call.args, routeArgs({ request, model: "test-model", effort: null }));
		}
		assert.deepEqual(t.cwdEntries, [0, 0, 0, 0, 0], "each call runs in an empty directory");
		assert.deepEqual(readdirSync(t.deps.tmpRoot), [], "the run removes its work directory");
		const r = t.results();
		assert.equal(r.descriptionsCommit, t.sha);
		assert.equal(r.totals.correct, 5);
		assert.equal(r.prompts.find((p) => p.prompt === "Write the beta doc.")?.expected, "beta");
	});

	test("two runs that start in the same second keep their own work directories", async () => {
		const t = setup({ "Draw an alpha.": "alpha" });
		const otherOut = tmp();
		const fake = t.deps.runAgent;
		const cwdLeft: boolean[] = [];
		let other: Promise<number> | null = null;
		t.deps.runAgent = async (inv: AgentInvocation) => {
			// The first call of the outer run lets a whole second run start and finish before it goes on.
			if (!other) {
				other = main(["--cases", t.casesFile, "--out-root", otherOut], { ...t.deps, runAgent: fake });
				await other;
			}
			cwdLeft.push(existsSync(inv.cwd));
			return fake(inv);
		};
		await t.run();
		assert.ok(other);
		assert.equal(cwdLeft.length, 5);
		assert.ok(cwdLeft.every(Boolean), "the second run removed the first run's work directory");
		assert.ok(existsSync(join(otherOut, "demo-routing", "run-2026-01-02T03-04-05Z", "results.json")));
		assert.deepEqual(readdirSync(t.deps.tmpRoot), []);
	});

	test("refuses a run directory that already exists", async () => {
		const t = setup();
		mkdirSync(t.runDir, { recursive: true });
		assert.equal(await t.run(), 1);
		assert.ok(t.lines.some((l) => l.includes(`${t.runDir} already exists`)));
		assert.equal(t.calls.length, 0);
	});

	test("grades a correct answer, another skill, none, a malformed answer, and a failed call separately", async () => {
		const t = setup({
			"Draw an alpha.": "alpha",
			"알파를 그려 주세요.": "beta",
			"Write the beta doc.": "none",
			"Fix the build.": "I would pick `alpha`.",
			"베타 문서를 써 주세요.": null,
		});
		assert.equal(await t.run(), 1);
		const verdicts = Object.fromEntries(t.results().prompts.map((p) => [p.prompt, [p.answer, p.verdict]]));
		assert.deepEqual(verdicts, {
			"Draw an alpha.": ["alpha", "correct"],
			"알파를 그려 주세요.": ["beta", "wrong"],
			"Write the beta doc.": ["none", "none"],
			"Fix the build.": ["I would pick `alpha`.", "malformed"],
			"베타 문서를 써 주세요.": [null, "failed"],
		});
		assert.deepEqual(t.results().totals, { prompts: 5, correct: 1, wrong: 1, none: 1, malformed: 1, failed: 1 });
	});

	test("a skill named where none was expected is wrong, and a name outside the list is malformed", async () => {
		const t = setup({
			"Draw an alpha.": "gamma",
			"알파를 그려 주세요.": " alpha\n",
			"Write the beta doc.": "beta",
			"Fix the build.": "beta",
			"베타 문서를 써 주세요.": "beta",
		});
		assert.equal(await t.run(), 1);
		const verdicts = Object.fromEntries(t.results().prompts.map((p) => [p.prompt, p.verdict]));
		assert.equal(verdicts["Fix the build."], "wrong");
		assert.equal(verdicts["Draw an alpha."], "malformed");
		assert.equal(verdicts["알파를 그려 주세요."], "correct", "surrounding whitespace is not a format error");
	});

	test("the report and results say the check reads descriptions only and does not observe activation", async () => {
		const t = setup({ "Draw an alpha.": "beta" });
		await t.run();
		const report = readFileSync(join(t.runDir, "report.md"), "utf8");
		assert.match(report, /^# Description-based routing: demo-routing v1\n/);
		assert.ok(report.includes(ROUTE_SCOPE));
		assert.match(ROUTE_SCOPE, /descriptions only/);
		assert.match(ROUTE_SCOPE, /does not observe/);
		assert.match(report, /\| `Draw an alpha\.` \| alpha \| beta \| wrong \|/);
		assert.equal(t.results().scope, ROUTE_SCOPE);
	});

	test("--dry-run prints the request from the committed descriptions and calls no model", async () => {
		const t = setup();
		assert.equal(await t.run("--dry-run"), 0);
		assert.equal(t.calls.length, 0);
		const out = t.lines.join("\n");
		assert.ok(out.includes(ROUTE_SCOPE));
		assert.match(out, new RegExp(`descriptions: skills/<name>/SKILL\\.md at ${t.sha}`));
		assert.match(out, /- beta: Write beta documents from a brief\./);
		assert.doesNotMatch(out, /UNCOMMITTED/);
		assert.match(out, /5 prompts, 5 classification calls/);
		assert.match(out, /p04 expect none +\| Fix the build\./);
		assert.match(out, /claude -p <request> --model claude-opus-5-5 /);
		assert.ok(out.includes(` --safe-mode --setting-sources "" --settings ${JSON.stringify(ROUTE_SETTINGS)} --max-turns 1 `));
		assert.deepEqual(readdirSync(join(t.runDir, "..", "..")), [], "a dry run writes nothing");
	});

	test("refuses a description that scripts/check-repo.ts refuses, with its message", async () => {
		const t = setup();
		const bad = skillMd("beta", "Use when: the colon would make YAML read a mapping.");
		write(t.repo, { "skills/beta/SKILL.md": bad });
		sh(t.repo, "commit", "-qam", "bad");
		assert.equal(await t.run("--dry-run"), 1);
		const [problem] = checkFrontmatter(bad, "beta");
		assert.ok(problem);
		assert.ok(t.lines.some((l) => l.includes(`skills/beta/SKILL.md:${problem.line}: ${problem.message}`)));
	});

	test("--ref reads the descriptions at another commit", async () => {
		const t = setup();
		write(t.repo, { "skills/beta/SKILL.md": skillMd("beta", "Second beta text.") });
		sh(t.repo, "commit", "-qam", "beta v2");
		await t.run("--dry-run", "--ref", "HEAD~1");
		assert.ok(t.lines.some((l) => l.includes("- beta: Write beta documents from a brief.")));
		t.lines.length = 0;
		await t.run("--dry-run");
		assert.ok(t.lines.some((l) => l.includes("- beta: Second beta text.")));
	});
});

describe("description parsing", () => {
	test("reads quoted, plain, and block-scalar descriptions the way check-repo accepts them", () => {
		assert.equal(descriptionOf(skillMd("a", '"Quoted: with \\"inner\\" quotes."')), 'Quoted: with "inner" quotes.');
		assert.equal(descriptionOf(skillMd("a", "'It''s single.'")), "It's single.");
		assert.equal(descriptionOf(skillMd("a", "Plain text, no traps.")), "Plain text, no traps.");
		assert.equal(descriptionOf("---\nname: a\ndescription: >\n  Folded line one\n  and two.\nlicense: MIT\n---\n"), "Folded line one and two.");
	});

	test("reads a double-quoted description with YAML's escapes, not JSON's", () => {
		const yaml = String.raw`"\x41\u00e9\U0001F600 \/ \t \\ \"q\" \ \_\N\L\P\a\b\e\v\f\r\n"`;
		assert.equal(descriptionOf(skillMd("a", yaml)), 'A\u00e9\u{1F600} / \t \\ "q"  \u00a0\u0085\u2028\u2029\x07\b\x1b\v\f\r\n');
		assert.throws(() => descriptionOf(skillMd("a", String.raw`"bad \q escape"`)), /\\q/);
	});

	test("reads the last line of a repeated description key", () => {
		assert.equal(descriptionOf("---\nname: a\ndescription: First.\ndescription: Second.\n---\n"), "Second.");
	});

	test("the one-turn classification call keeps settings files, hooks, and automatic context out", () => {
		assert.deepEqual(routeArgs({ request: "R", model: "m", effort: "low" }), [
			"-p",
			"R",
			"--model",
			"m",
			"--effort",
			"low",
			"--output-format",
			"stream-json",
			"--verbose",
			"--safe-mode",
			"--setting-sources",
			"",
			"--settings",
			'{"enabledPlugins":{"cc-plugin-agents-md@builtin":false}}',
			"--max-turns",
			"1",
			"--disable-slash-commands",
			"--no-session-persistence",
			"--strict-mcp-config",
			"--tools",
			"",
			"--system-prompt",
			ROUTER_SYSTEM,
		]);
	});
});

describe("routing case file", () => {
	const valid = () => ({
		suite: "s",
		version: 1,
		skills: {
			a: { should_fire: ["one"], should_not_fire: [{ prompt: "two", goes_to: "b" }] },
			b: { should_fire: ["two"], should_not_fire: [{ prompt: "three", goes_to: "none" }] },
		},
	});
	const problems = (mutate: (f: ReturnType<typeof valid>) => void) => {
		const f = valid();
		mutate(f);
		try {
			parseRouting(JSON.stringify(f), "f.json");
			return "";
		} catch (e) {
			return (e as Error).message;
		}
	};

	test("a valid file yields one prompt per distinct text", () => {
		const r = parseRouting(JSON.stringify(valid()), "f.json");
		assert.deepEqual(r.candidates, ["a", "b"]);
		assert.deepEqual(
			r.prompts.map((p) => [p.id, p.prompt, p.expected]),
			[["p01", "one", "a"], ["p02", "two", "b"], ["p03", "three", "none"]],
		);
	});

	test("rejects unknown targets, self-targets, conflicts, and empty lists", () => {
		assert.match(problems((f) => (f.skills.a.should_not_fire[0]!.goes_to = "zeta")), /unknown skill "zeta"/);
		assert.match(problems((f) => (f.skills.a.should_not_fire[0]!.goes_to = "a")), /goes_to its own skill/);
		assert.match(problems((f) => f.skills.b.should_fire.push("one")), /"one" expects both a and b/);
		assert.match(problems((f) => (f.skills.a.should_fire = [])), /a\.should_fire must be a non-empty list/);
	});

	test("accepts a prompt that starts with a dash: the request around it starts with fixed text", () => {
		const f = valid();
		f.skills.b.should_not_fire[0]!.prompt = "-x";
		assert.equal(parseRouting(JSON.stringify(f), "f.json").prompts.at(-1)?.prompt, "-x");
		assert.match(routeRequest([{ name: "a", description: "d" }], "-x"), /^An agent /);
	});
});

describe("design routing cases", () => {
	const repoRoot = gitText(["rev-parse", "--show-toplevel"], import.meta.dirname);
	const file = join(import.meta.dirname, "routing", "design.json");
	const routing = parseRouting(readFileSync(file, "utf8"), file);
	const design = ["awesome-interface", "design-md", "make-font", "make-logo", "imagegen", "image-to-code", "diagram-design", "awesome-slides"];
	const hangul = /[가-힣]/;

	test("covers the eight design skills, each with Korean and English prompts both ways", () => {
		assert.deepEqual(routing.candidates.toSorted(), design.toSorted());
		for (const name of design) {
			const fire = routing.prompts.filter((p) => p.expected === name).map((p) => p.prompt);
			const away = routing.prompts.filter((p) => p.listedUnder.some((l) => l.skill === name && !l.fires)).map((p) => p.prompt);
			for (const [label, list] of [["fire", fire], ["away", away]] as const) {
				assert.ok(list.some((p) => hangul.test(p)), `${name} ${label}: no Korean prompt`);
				assert.ok(list.some((p) => !hangul.test(p)), `${name} ${label}: no English prompt`);
			}
		}
		assert.ok(routing.prompts.some((p) => p.expected === "none" && hangul.test(p.prompt)));
	});

	test("covers the colliding pairs in both directions", () => {
		const pairs = [
			["awesome-interface", "design-md"],
			["imagegen", "image-to-code"],
			["make-logo", "imagegen"],
			["diagram-design", "awesome-slides"],
			["awesome-interface", "image-to-code"],
			["make-font", "awesome-interface"],
		];
		for (const [a, b] of pairs)
			for (const [from, to] of [[a, b], [b, a]])
				assert.ok(
					routing.prompts.some((p) => p.expected === to && p.listedUnder.some((l) => l.skill === from && !l.fires)),
					`${from} has no prompt that goes to ${to}`,
				);
	});

	test("every design skill description loads from HEAD through the check-repo parser", () => {
		const { skills } = readDescriptions(repoRoot, "HEAD", routing.candidates);
		assert.equal(skills.length, 8);
		for (const s of skills) assert.ok(s.description.length > 40, s.name);
	});
});


test("a paid run is refused while managed settings define hooks; a description with NUL is refused by name", async () => {
	const { managedHookFiles, descriptionOf } = await import("./lib/route/classify.ts");
	const { mkdtempSync, writeFileSync, rmSync } = await import("node:fs");
	const { tmpdir } = await import("node:os");
	const { join } = await import("node:path");
	const dir = mkdtempSync(join(tmpdir(), "route-managed-"));
	try {
		const none = join(dir, "missing.json");
		const empty = join(dir, "empty.json");
		const hooked = join(dir, "hooked.json");
		writeFileSync(empty, JSON.stringify({ permissions: {} }));
		writeFileSync(hooked, JSON.stringify({ hooks: { SessionStart: [{ hooks: [{ type: "command", command: "echo x" }] }] } }));
		assert.deepEqual(managedHookFiles([none, empty]), []);
		assert.deepEqual(managedHookFiles([none, empty, hooked]), [hooked]);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
	assert.throws(() => descriptionOf('---\nname: demo\ndescription: "A \\0 null."\n---\n'), /NUL/);
});
