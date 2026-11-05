import { afterAll, describe, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { IterationMeta, RunMeta, Suite } from "./lib/schema.ts";
import { type AgentInvocation, buildAgentArgs, parseTranscript, spawnAgent, systemAppendText } from "./lib/run/agent.ts";
import { buildPatch, computeChanges } from "./lib/run/changes.ts";
import { listFiles, treeSha256 } from "./lib/run/files.ts";
import { main } from "./lib/run/runner.ts";
import { ensureGitSource, materializeArm, materializeLocal, resolveRef } from "./lib/run/skills.ts";

const roots: string[] = [];
function tmp(prefix = "skill-eval-test-"): string {
	const dir = mkdtempSync(join(tmpdir(), prefix));
	roots.push(dir);
	return dir;
}
afterAll(() => {
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

/** A repository with one committed skill (`skills/demo`) at two commits. */
function skillRepo() {
	const repo = tmp();
	sh(repo, "init", "-q", "-b", "main");
	write(repo, {
		"skills/demo/SKILL.md": "# demo v1\n",
		"skills/demo/references/a.md": "ref a\n",
		"skills/demo/evals/evals.json": '{"answer":42}\n',
	});
	sh(repo, "add", ".");
	sh(repo, "commit", "-qm", "v1");
	const v1 = sh(repo, "rev-parse", "HEAD");
	write(repo, { "skills/demo/SKILL.md": "# demo v2\n" });
	sh(repo, "commit", "-qam", "v2");
	const v2 = sh(repo, "rev-parse", "HEAD");
	return { repo, v1, v2 };
}

describe("skill materialization", () => {
	test("local skills come from the given ref, never the working tree, and drop evals/", () => {
		const { repo, v1, v2 } = skillRepo();
		write(repo, { "skills/demo/SKILL.md": "# uncommitted\n", "skills/demo/new.md": "untracked\n" });
		expect(resolveRef(repo, "HEAD")).toBe(v2);
		expect(resolveRef(repo, "HEAD~1")).toBe(v1);

		const dest = join(tmp(), "demo");
		materializeLocal(repo, v1, "skills/demo", dest);
		expect(listFiles(dest)).toEqual(["SKILL.md", "references/a.md"]);
		expect(readFileSync(join(dest, "SKILL.md"), "utf8")).toBe("# demo v1\n");

		const [m] = materializeArm({ skills: [{ source: "local", path: "skills/demo" }] }, join(tmp(), "stage"), {
			repoRoot: repo,
			outRoot: tmp(),
			sources: {},
			localSha: v2,
		});
		expect(m.meta).toMatchObject({ name: "demo", source: "local", commit: v2, path: "skills/demo" });
		expect(readFileSync(join(m.dir, "SKILL.md"), "utf8")).toBe("# demo v2\n");
		expect(existsSync(join(m.dir, "new.md"))).toBe(false);
	});

	test("sha256 hashes sorted path + NUL + bytes + NUL", () => {
		const dir = tmp();
		write(dir, { "b.md": "B", "a/x.md": "X" });
		const expected = createHash("sha256").update("a/x.md\0X\0b.md\0B\0").digest("hex");
		expect(treeSha256(dir)).toBe(expected);
	});

	test("git sources are cloned at the pinned commit, reused, and rejected on a SHA mismatch", () => {
		const { repo, v1, v2 } = skillRepo();
		const outRoot = tmp();
		const src = { repo: `file://${repo}`, commit: v1 };
		const dir = ensureGitSource(outRoot, "up", src);
		expect(dir).toBe(join(outRoot, "sources", `up@${v1}`));
		expect(sh(dir, "rev-parse", "HEAD")).toBe(v1);

		const [m] = materializeArm({ skills: [{ source: "up", path: "skills/demo" }] }, join(tmp(), "stage"), {
			repoRoot: repo,
			outRoot,
			sources: { up: src },
		});
		expect(m.meta.commit).toBe(v1);
		expect(listFiles(m.dir)).toEqual(["SKILL.md", "references/a.md"]);
		expect(readFileSync(join(m.dir, "SKILL.md"), "utf8")).toBe("# demo v1\n");

		writeFileSync(join(dir, "marker"), "reused");
		expect(ensureGitSource(outRoot, "up", src)).toBe(dir);
		expect(existsSync(join(dir, "marker"))).toBe(true);

		sh(dir, "checkout", "-q", "--detach", v2);
		expect(() => ensureGitSource(outRoot, "up", src)).toThrow(/expected/);
	});

	test("a cloned source cannot select a filter driver from the caller's git config", () => {
		const repo = tmp();
		sh(repo, "init", "-q", "-b", "main");
		write(repo, { ".gitattributes": "* filter=evil\n", "skills/demo/SKILL.md": "# demo\n" });
		sh(repo, "add", ".");
		sh(repo, "commit", "-qm", "v1");
		const marker = join(tmp(), "smudge-ran");
		const globalConfig = join(tmp(), "gitconfig");
		writeFileSync(globalConfig, `[filter "evil"]\n\tsmudge = touch ${marker}; cat\n`);
		const saved = process.env.GIT_CONFIG_GLOBAL;
		process.env.GIT_CONFIG_GLOBAL = globalConfig;
		try {
			const outRoot = tmp();
			const src = { repo: `file://${repo}`, commit: sh(repo, "rev-parse", "HEAD") };
			materializeArm({ skills: [{ source: "up", path: "skills/demo" }] }, join(tmp(), "stage"), {
				repoRoot: repo,
				outRoot,
				sources: { up: src },
			});
		} finally {
			if (saved === undefined) delete process.env.GIT_CONFIG_GLOBAL;
			else process.env.GIT_CONFIG_GLOBAL = saved;
		}
		expect(existsSync(marker)).toBe(false);
	});

	test("a skill path through a symlinked parent directory is rejected", () => {
		const outside = tmp();
		write(outside, { "demo/SKILL.md": "# host file\n" });
		const repo = tmp();
		sh(repo, "init", "-q", "-b", "main");
		symlinkSync(outside, join(repo, "skills"));
		write(repo, { "README.md": "x\n" });
		sh(repo, "add", ".");
		sh(repo, "commit", "-qm", "v1");
		const sha = sh(repo, "rev-parse", "HEAD");
		expect(() =>
			materializeArm({ skills: [{ source: "up", path: "skills/demo" }] }, join(tmp(), "stage"), {
				repoRoot: repo,
				outRoot: tmp(),
				sources: { up: { repo: `file://${repo}`, commit: sha } },
			}),
		).toThrow(/symlink/);
	});

	test("skills containing symlinks are rejected", () => {
		const repo = tmp();
		sh(repo, "init", "-q", "-b", "main");
		mkdirSync(join(repo, "skills/demo"), { recursive: true });
		symlinkSync("/etc/hostname", join(repo, "skills/demo/SKILL.md"));
		sh(repo, "add", ".");
		sh(repo, "commit", "-qm", "v1");
		const sha = sh(repo, "rev-parse", "HEAD");
		expect(() =>
			materializeArm({ skills: [{ source: "local", path: "skills/demo" }] }, join(tmp(), "stage"), {
				repoRoot: repo,
				outRoot: tmp(),
				sources: {},
				localSha: sha,
			}),
		).toThrow(/symlinks/);
		expect(() =>
			materializeArm({ skills: [{ source: "up", path: "skills/demo" }] }, join(tmp(), "stage"), {
				repoRoot: repo,
				outRoot: tmp(),
				sources: { up: { repo: `file://${repo}`, commit: sha } },
			}),
		).toThrow(/symlinks/);
	});
});

describe("agent", () => {
	test("command arguments; no append flag without skills", () => {
		const none = buildAgentArgs({ prompt: "fix it", model: "m", effort: null, appendFile: null });
		expect(none).toEqual([
			"-p",
			"fix it",
			"--model",
			"m",
			"--output-format",
			"stream-json",
			"--verbose",
			"--disable-slash-commands",
			"--no-session-persistence",
			"--strict-mcp-config",
			"--permission-mode",
			"bypassPermissions",
		]);
		const ai = buildAgentArgs({ prompt: "fix it", model: "m", effort: "high", appendFile: "/x.md" });
		expect(ai.slice(4, 6)).toEqual(["--effort", "high"]);
		expect(ai.slice(-2)).toEqual(["--append-system-prompt-file", "/x.md"]);
	});

	test("system append text lists every skill", () => {
		const text = systemAppendText([
			{ name: "a", skillMd: "AAA\n" },
			{ name: "b", skillMd: "BBB" },
		]);
		expect(text.startsWith("# Installed skills\n\nThe user has installed")).toBe(true);
		expect(text).toContain("under `.skills/<name>/` relative to the working directory");
		expect(text.endsWith("## Skill: a\n\nAAA\n\n## Skill: b\n\nBBB\n")).toBe(true);
	});

	test("final message and usage come from the last result event", () => {
		const lines = [
			'{"type":"system","subtype":"init"}',
			"not json",
			'{"type":"result","result":"first","num_turns":1}',
			JSON.stringify({
				type: "result",
				result: "done **ok**",
				num_turns: 4,
				total_cost_usd: 0.12,
				usage: { input_tokens: 10, output_tokens: 20, cache_read_input_tokens: 30, cache_creation_input_tokens: 40 },
			}),
		];
		expect(parseTranscript(lines.join("\n"))).toEqual({
			final: "done **ok**",
			usage: { inputTokens: 10, outputTokens: 20, cacheReadTokens: 30, cacheCreationTokens: 40 },
			costUsd: 0.12,
			numTurns: 4,
		});
		expect(parseTranscript('{"type":"assistant"}\n')).toEqual({ final: null, usage: null, costUsd: null, numTurns: null });
	});

	test("timeout kills the whole process group", async () => {
		const dir = tmp();
		const pidFile = join(dir, "pid");
		const outcome = await spawnAgent({
			command: "sh",
			args: ["-c", `sleep 30 & echo $! > ${pidFile}; wait`],
			cwd: dir,
			env: { PATH: process.env.PATH ?? "" },
			timeoutMs: 300,
			stdoutPath: join(dir, "out"),
			stderrPath: join(dir, "err"),
		});
		expect(outcome).toEqual({ rc: null, timedOut: true });
		const grandchild = Number(readFileSync(pidFile, "utf8"));
		expect(() => process.kill(grandchild, 0)).toThrow();
	});
});

describe("changes and diff", () => {
	test("exclusion rules, added/modified/deleted, text-only patch", () => {
		const fixture = tmp();
		const ws = tmp();
		write(fixture, { "keep.txt": "same\n", "edit.txt": "old\n", "gone.txt": "bye\n", "node_modules/x.js": "1" });
		write(ws, {
			"keep.txt": "same\n",
			"edit.txt": "new\n",
			"new.txt": "hi\n",
			"bin.dat": "a\0b",
			".skills/demo/SKILL.md": "s",
			".git/HEAD": "ref",
			"sub/node_modules/y.js": "2",
			"sub/.skills/kept.md": "k",
		});
		const changes = computeChanges(fixture, ws);
		expect(changes).toEqual({
			added: ["bin.dat", "new.txt", "sub/.skills/kept.md"],
			modified: ["edit.txt"],
			deleted: ["gone.txt"],
		});
		const patch = buildPatch(fixture, ws, changes);
		expect(patch).toContain("--- a/edit.txt\n+++ b/edit.txt\n@@ -1 +1 @@\n-old\n+new\n");
		expect(patch).toContain("--- /dev/null\n+++ b/new.txt\n");
		expect(patch).toContain("--- a/gone.txt\n+++ /dev/null\n");
		expect(patch).not.toContain("bin.dat");
		expect(patch.indexOf("a/edit.txt")).toBeLessThan(patch.indexOf("a/gone.txt"));
	});

	test("a null fixture compares against an empty directory", () => {
		const ws = tmp();
		write(ws, { "index.html": "<p>x</p>\n" });
		expect(computeChanges(null, ws)).toEqual({ added: ["index.html"], modified: [], deleted: [] });
	});
});

describe("runner", () => {
	/** A repo holding a suite with one fixture, plus a fake agent that edits the workspace. */
	function setup(mutate?: (s: Suite) => void) {
		const { repo, v2 } = skillRepo();
		const suiteDir = join(repo, "evals");
		write(suiteDir, { "fixtures/page/index.html": "<h1>hi</h1>\n" });
		const suite: Suite = {
			suite: "demo-suite",
			version: 1,
			sources: {},
			arms: { none: { skills: [] }, local: { skills: [{ source: "local", path: "skills/demo" }] } },
			cases: [
				{
					id: "c1",
					title: "case",
					covers: ["demo"],
					prompt: "polish the page",
					fixture: "page",
					arms: ["none", "local"],
					expectations: ["e"],
					rubric: ["r"],
					checks: [],
				},
			],
		};
		mutate?.(suite);
		const suiteFile = join(suiteDir, "suite.json");
		writeFileSync(suiteFile, JSON.stringify(suite, null, 2));
		const calls: AgentInvocation[] = [];
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
			runAgent: async (inv: AgentInvocation) => {
				calls.push(inv);
				writeFileSync(join(inv.cwd, "index.html"), "<h1>hello</h1>\n");
				writeFileSync(
					inv.stdoutPath,
					`${JSON.stringify({ type: "result", result: "Changed the heading.", num_turns: 2, total_cost_usd: 0.01, usage: { input_tokens: 1, output_tokens: 2 } })}\n`,
				);
				return { rc: 0, timedOut: false };
			},
		};
		const run = (...args: string[]) => main(["--suite", suiteFile, "--out-root", outRoot, ...args], deps);
		return { repo, v2, suiteFile, outRoot, calls, lines, deps, run, iterDir: (n: number) => join(outRoot, "demo-suite", `iteration-${n}`) };
	}

	test("runs every arm and writes the contract outputs", async () => {
		const t = setup();
		expect(await t.run("--model", "test-model")).toBe(0);
		expect(t.calls).toHaveLength(2);
		const none = t.calls.find((c) => c.cwd.includes("/none/"))!;
		const local = t.calls.find((c) => c.cwd.includes("/local/"))!;
		expect(none.args).not.toContain("--append-system-prompt-file");
		expect(local.args).toContain("--append-system-prompt-file");
		expect(none.cwd).toBe(join(t.deps.tmpRoot, "demo-suite", "iteration-1", "c1", "none", "run-1"));

		const iter = t.iterDir(1);
		const meta: IterationMeta = JSON.parse(readFileSync(join(iter, "iteration.json"), "utf8"));
		expect(meta).toMatchObject({ iteration: 1, model: "test-model", runs: 1, cases: ["c1"], localRefs: { local: t.v2 } });
		expect(readFileSync(join(iter, "suite.json"))).toEqual(readFileSync(t.suiteFile));

		const run = join(iter, "c1", "local", "run-1");
		const runMeta: RunMeta = JSON.parse(readFileSync(join(run, "meta.json"), "utf8"));
		expect(runMeta).toMatchObject({ case: "c1", arm: "local", run: 1, rc: 0, timedOut: false, numTurns: 2, costUsd: 0.01 });
		expect(runMeta.usage).toEqual({ inputTokens: 1, outputTokens: 2, cacheReadTokens: 0, cacheCreationTokens: 0 });
		expect(runMeta.skills).toHaveLength(1);
		expect(runMeta.skills[0].commit).toBe(t.v2);
		expect(readFileSync(join(run, "final.md"), "utf8")).toBe("Changed the heading.");
		expect(JSON.parse(readFileSync(join(run, "changes.json"), "utf8"))).toEqual({ added: [], modified: ["index.html"], deleted: [] });
		expect(readFileSync(join(run, "diff.patch"), "utf8")).toContain("+<h1>hello</h1>");
		expect(listFiles(join(run, "workspace"))).toEqual(["index.html"]);
		expect(readFileSync(join(run, "system-append.md"), "utf8")).toContain("## Skill: demo\n\n# demo v2\n");
		expect(existsSync(join(local.cwd, ".skills", "demo", "evals"))).toBe(false);
		expect(t.lines.some((l) => /^c1 local run-1 rc=0 [0-9.]+s$/.test(l))).toBe(true);
		expect(t.lines.at(-1)).toStartWith("done: 2 ok, 0 failed, 0 skipped");
	});

	test("new iterations increment; resuming skips finished runs unless forced", async () => {
		const t = setup();
		expect(await t.run("--arm", "none")).toBe(0);
		expect(await t.run("--arm", "none")).toBe(0);
		expect(existsSync(t.iterDir(2))).toBe(true);
		expect(t.calls).toHaveLength(2);

		expect(await t.run("--iteration", "1", "--runs", "2")).toBe(0);
		// none run-1 is skipped; none run-2, local run-1, local run-2 run.
		expect(t.calls).toHaveLength(5);
		expect(t.lines).toContain("c1 none run-1 skipped");
		const meta: IterationMeta = JSON.parse(readFileSync(join(t.iterDir(1), "iteration.json"), "utf8"));
		expect(meta).toMatchObject({ runs: 2, arms: ["none", "local"] });

		writeFileSync(join(t.iterDir(1), "c1", "judge.json"), "{}");
		expect(await t.run("--iteration", "1", "--arm", "none", "--force")).toBe(0);
		expect(t.calls).toHaveLength(7);
		expect(existsSync(join(t.iterDir(1), "c1", "judge.json"))).toBe(false);
	});

	test("resuming with a changed suite fails before running", async () => {
		const t = setup();
		expect(await t.run("--arm", "none")).toBe(0);
		const suite = JSON.parse(readFileSync(t.suiteFile, "utf8"));
		suite.cases[0].prompt = "polish the page again";
		writeFileSync(t.suiteFile, JSON.stringify(suite, null, 2));
		expect(await t.run("--iteration", "1", "--arm", "local")).toBe(1);
		expect(t.calls).toHaveLength(1);
		expect(t.lines.join("\n")).toMatch(/^\+ +"prompt": "polish the page again",$/m);
	});

	test("an invalid suite runs nothing", async () => {
		const t = setup((s) => {
			s.cases[0].arms = ["none"];
		});
		expect(await t.run()).toBe(1);
		expect(t.calls).toHaveLength(0);
		expect(t.lines.join("\n")).toContain("at least two arms required");
		expect(existsSync(join(t.outRoot, "demo-suite"))).toBe(false);
	});

	test("dry run lists runs and skill sources without writing", async () => {
		const t = setup();
		expect(await t.run("--dry-run", "--ref", "local=HEAD~1")).toBe(0);
		expect(t.calls).toHaveLength(0);
		expect(existsSync(join(t.outRoot, "demo-suite"))).toBe(false);
		const out = t.lines.join("\n");
		expect(out).toContain("c1 none run-1");
		expect(out).toContain("c1 local run-1");
		expect(out).toMatch(/arm local: local skills\/demo @ [0-9a-f]{40}/);
	});

	test("a failed run does not stop the others", async () => {
		const t = setup();
		const inner = t.deps.runAgent;
		t.deps.runAgent = async (inv) => {
			if (inv.cwd.includes("/none/")) throw new Error("boom");
			return inner(inv);
		};
		expect(await t.run()).toBe(1);
		expect(t.lines).toContain("c1 none run-1 failed: boom");
		expect(existsSync(join(t.iterDir(1), "c1", "local", "run-1", "meta.json"))).toBe(true);
		expect(t.lines.at(-1)).toStartWith("done: 1 ok, 1 failed, 0 skipped");
	});
});
