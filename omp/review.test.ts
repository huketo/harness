import { expect, test } from "bun:test";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import {
	loadProfiles,
	loadState,
	resolveProfile,
} from "./extensions/profiles/schema";
import {
	assertRestrictedReviewCapabilities,
	parseReviewArgs,
	type ReviewCapabilitySnapshot,
} from "./review";

const REVIEW_ENTRY = join(import.meta.dir, "review.ts");

const restricted: ReviewCapabilitySnapshot = {
	enabledTools: ["glob", "grep", "read"],
	registeredTools: ["glob", "grep", "read"],
	mountedTools: [],
	evalBridgeTools: ["glob", "grep", "read"],
	extensions: [],
	mcpEnabled: false,
};

/**
 * Plant one custom tool module and one stdio MCP server in each place omp
 * discovers them (agent directory and project `.omp/`). Each writes its own
 * marker file when evaluated or started.
 */
async function plantAmbientCapabilities(
	configDirs: Record<string, string>,
	markerDir: string,
): Promise<string[]> {
	const markers: string[] = [];
	for (const [scope, dir] of Object.entries(configDirs)) {
		const toolMarker = join(markerDir, `custom-tool-${scope}`);
		const mcpMarker = join(markerDir, `mcp-${scope}`);
		markers.push(toolMarker, mcpMarker);
		await mkdir(join(dir, "tools"), { recursive: true });
		await writeFile(
			join(dir, "tools", `ambient-${scope}.ts`),
			`import { writeFileSync } from "node:fs";\n` +
				`writeFileSync(${JSON.stringify(toolMarker)}, "imported");\n` +
				`export default () => ({ name: "ambient_${scope}", label: "ambient", description: "fixture", parameters: { type: "object", properties: {} }, execute: async () => ({ content: [] }) });\n`,
		);
		await writeFile(
			join(dir, "mcp.json"),
			JSON.stringify({
				mcpServers: {
					[`ambient-${scope}`]: {
						command: "/bin/sh",
						args: ["-c", `echo started > '${mcpMarker}'; exec sleep 2`],
					},
				},
			}),
		);
	}
	return markers;
}

/**
 * Run the real launcher against the PATH omp with an isolated agent directory
 * that also carries ambient custom tools and MCP servers. The synthetic key
 * only lets omp consider Anthropic models selectable; no test path prompts a
 * model. Returns the ambient markers that appeared.
 */
async function runReviewer(args: string[]) {
	const root = await mkdtemp(join(tmpdir(), "harness-review-test-"));
	try {
		const agentDir = join(root, "agent");
		const project = join(root, "project");
		const markerDir = join(root, "markers");
		await mkdir(markerDir);
		const markers = await plantAmbientCapabilities(
			{ user: agentDir, project: join(project, ".omp") },
			markerDir,
		);
		const child = Bun.spawn(
			[
				process.execPath,
				"--no-install",
				REVIEW_ENTRY,
				"--cwd",
				project,
				...args,
			],
			{
				env: {
					...process.env,
					PI_CODING_AGENT_DIR: agentDir,
					ANTHROPIC_API_KEY: "synthetic-test-key",
				},
				stdout: "pipe",
				stderr: "pipe",
			},
		);
		const [stdout, stderr, exitCode] = await Promise.all([
			new Response(child.stdout).text(),
			new Response(child.stderr).text(),
			child.exited,
		]);
		// The old host waited out omp's MCP startup window (250 ms) after spawning
		// the server, long after the marker write; no extra wait is needed.
		const ambientRan = markers.filter((marker) => existsSync(marker));
		return { stdout, stderr, exitCode, ambientRan };
	} finally {
		await rm(root, { recursive: true, force: true });
	}
}

test("capability guard accepts only the exact read-only tool boundary", () => {
	expect(() => assertRestrictedReviewCapabilities(restricted)).not.toThrow();
	for (const widened of [
		{ enabledTools: ["bash", "glob", "grep", "read"] },
		{ registeredTools: ["glob", "grep", "read", "write"] },
		{ evalBridgeTools: ["eval", "glob", "grep", "read"] },
		{ enabledTools: ["glob", "read"] },
		{ mountedTools: ["browser"] },
		{ extensions: ["/tmp/extension.ts"] },
		{ mcpEnabled: true },
	]) {
		expect(() =>
			assertRestrictedReviewCapabilities({ ...restricted, ...widened }),
		).toThrow(/Restricted reviewer/);
	}
});

test("relative --cwd resolves against the launcher, not the omp host directory", () => {
	expect(parseReviewArgs(["--cwd", "sub/dir", "--inspect-tools"])).toMatchObject(
		{ cwd: resolve("sub/dir") },
	);
});

test("installed omp resolves the opus-code profile model exactly with only read tools", async () => {
	const expected = resolveProfile(
		loadProfiles(),
		loadState(join(tmpdir(), "harness-review-no-state")),
		"opus-code",
	);
	// The synthetic credential above covers Anthropic only.
	expect(expected.provider).toBe("anthropic");
	const run = await runReviewer(["--profile", "opus-code", "--inspect-tools"]);
	expect(run.stderr).toBe("");
	expect(run.exitCode).toBe(0);
	expect(JSON.parse(run.stdout)).toMatchObject({
		model: `${expected.provider}/${expected.model}`,
		compactionMethodOrder: ["remote", "handoff", "soft"],
		...restricted,
	});
}, 60_000);

test("reviewer host never evaluates ambient custom tools or starts MCP servers", async () => {
	const run = await runReviewer(["--profile", "opus-code", "--inspect-tools"]);
	expect(run.exitCode).toBe(0);
	expect(run.ambientRan).toEqual([]);
}, 60_000);

test("installed omp rejects a partial model selector instead of a sibling model", async () => {
	const run = await runReviewer([
		"--model",
		"anthropic/claude-opus",
		"--thinking",
		"medium",
		"--inspect-tools",
	]);
	expect(run.exitCode).toBe(1);
	expect(run.stdout).toBe("");
	expect(run.stderr).toMatch(/exact model "anthropic\/claude-opus"/);
}, 60_000);
