import { afterEach, beforeEach, expect, test } from "bun:test";
import {
	existsSync,
	mkdirSync,
	mkdtempSync,
	readFileSync,
	rmSync,
	symlinkSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const launcher = fileURLToPath(new URL("./herdr-trial.ts", import.meta.url));
const extensionDir = fileURLToPath(
	new URL("./extensions/herdr", import.meta.url),
);

interface FakeCall {
	argv: string[];
	delegation?: string;
	marker?: string;
	configPath?: string;
	config?: string;
}

let root: string;
let binDir: string;
let agentDir: string;
let callsPath: string;
let savedEnv: NodeJS.ProcessEnv;

beforeEach(() => {
	savedEnv = { ...process.env };
	root = mkdtempSync(join(tmpdir(), "herdr-trial-test-"));
	binDir = join(root, "bin");
	agentDir = join(root, "agent");
	callsPath = join(root, "calls.jsonl");
	mkdirSync(binDir, { recursive: true });
	mkdirSync(agentDir, { recursive: true });
	writeFileSync(
		join(binDir, "omp"),
		`#!/usr/bin/env bun
import { once } from "node:events";
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
const argv = process.argv.slice(2);
function record(value) {
  const line = JSON.stringify(value) + "\\n";
  appendFileSync(process.env.FAKE_CALLS, line);
}
if (argv.at(-2) === "config" && argv.at(-1) === "path") {
  record({ argv, marker: process.env.PRESERVE_MARKER });
  console.log(process.env.FAKE_AGENT_DIR);
  process.exit(Number(process.env.FAKE_CONFIG_EXIT ?? "0"));
}
const configIndex = argv.lastIndexOf("--config");
const configPath = configIndex === -1 ? undefined : argv[configIndex + 1];
record({
  argv,
  delegation: process.env.HARNESS_DELEGATION,
  marker: process.env.PRESERVE_MARKER,
  configPath,
  config: configPath === undefined ? undefined : readFileSync(configPath, "utf8"),
});
if (process.env.FAKE_STARTED) console.log("FAKE_STARTED");
if (process.env.FAKE_WAIT_SIGNAL === "1") {
  process.on("SIGTERM", () => {
    writeFileSync(process.env.FAKE_SIGNAL, "SIGTERM");
    process.exit(44);
  });
  await once(process, "FAKE_NEVER");
}
process.exit(Number(process.env.FAKE_EXIT ?? "0"));
`,
		{ mode: 0o755 },
	);
	process.env.PATH = `${binDir}:${savedEnv.PATH ?? ""}`;
	process.env.HERDR_ENV = "1";
	process.env.FAKE_AGENT_DIR = agentDir;
	process.env.FAKE_CALLS = callsPath;
	process.env.PRESERVE_MARKER = "preserved";
	delete process.env.FAKE_CONFIG_EXIT;
	delete process.env.FAKE_EXIT;
	delete process.env.FAKE_SIGNAL;
	delete process.env.FAKE_STARTED;
	delete process.env.FAKE_WAIT_SIGNAL;
});

afterEach(() => {
	rmSync(root, { recursive: true, force: true });
	for (const key of Object.keys(process.env)) {
		if (!(key in savedEnv)) delete process.env[key];
	}
	Object.assign(process.env, savedEnv);
});

async function run(args: string[], env: NodeJS.ProcessEnv = process.env) {
	const child = Bun.spawn([process.execPath, launcher, ...args], {
		env,
		stdout: "pipe",
		stderr: "pipe",
	});
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	return { stdout, stderr, code };
}

function calls(): FakeCall[] {
	if (!existsSync(callsPath)) return [];
	return readFileSync(callsPath, "utf8")
		.trim()
		.split("\n")
		.filter(Boolean)
		.map((line) => JSON.parse(line));
}

test("help documents the opt-in, uninstalled, session-only experiment without invoking OMP", async () => {
	const env = { ...process.env };
	delete env.HERDR_ENV;
	const result = await run(["--help"], env);

	expect(result.code).toBe(0);
	expect(calls()).toEqual([]);
});

test("refuses to launch outside Herdr", async () => {
	const env = { ...process.env };
	delete env.HERDR_ENV;
	const result = await run(["--"], env);

	expect(result.code).toBe(1);
	expect(result.stderr).toContain("HERDR_ENV=1 is required");
	expect(calls()).toEqual([]);
});

test("launches through the external OMP boundary with only temporary trial state", async () => {
	const userConfig = join(root, "user-config.yml");
	const originalConfig = "theme:\n  dark: titanium\n";
	writeFileSync(userConfig, originalConfig);
	process.env.HARNESS_DELEGATION = "native";

	const result = await run([
		"--",
		"--config",
		userConfig,
		"--model",
		"synthetic-model",
		"synthetic prompt",
	]);

	expect(result.code).toBe(0);
	const observed = calls();
	expect(observed[0]).toEqual({
		argv: ["config", "path"],
		marker: "preserved",
	});
	const launch = observed[1];
	expect(launch.delegation).toBe("agy");
	expect(launch.marker).toBe("preserved");
	expect(launch.argv.slice(0, 5)).toEqual([
		"--config",
		userConfig,
		"--model",
		"synthetic-model",
		"synthetic prompt",
	]);
	expect(launch.config).toBe(
		"magicKeywords:\n  orchestrate: false\n  workflow: false\ntask:\n  eager: default\n",
	);
	expect(launch.configPath).toBeDefined();
	expect(existsSync(launch.configPath!)).toBe(false);
	expect(readFileSync(userConfig, "utf8")).toBe(originalConfig);

	const extensionIndex = launch.argv.lastIndexOf("--extension");
	expect(launch.argv[extensionIndex + 1]).toBe(join(extensionDir, "index.ts"));
	expect(launch.argv).not.toContain("--tools");
});

test("uses an installed symlink spelling so OMP lexical de-duplication loads Herdr once", async () => {
	const installed = join(agentDir, "extensions", "harness-herdr");
	mkdirSync(dirname(installed), { recursive: true });
	symlinkSync(extensionDir, installed, "dir");

	const result = await run(["--", "--profile", "trial-profile"]);

	expect(result.code).toBe(0);
	const observed = calls();
	expect(observed[0].argv).toEqual([
		"--profile",
		"trial-profile",
		"config",
		"path",
	]);
	const argv = observed[1].argv;
	const extensionIndex = argv.lastIndexOf("--extension");
	expect(argv[extensionIndex + 1]).toBe(installed);
	expect(argv.filter((arg) => arg === "--extension")).toHaveLength(1);
});

test("inserts enforced flags before OMP's positional separator", async () => {
	const result = await run(["--", "message", "--", "--flag-shaped-message"]);

	expect(result.code).toBe(0);
	const argv = calls()[1].argv;
	const separator = argv.indexOf("--");
	expect(argv[separator + 1]).toBe("--flag-shaped-message");
	expect(argv.indexOf("--config")).toBeLessThan(separator);
	expect(argv.indexOf("--extension")).toBeLessThan(separator);
});

test("preserves caller tool selection without maintaining a frozen OMP tool catalog", async () => {
	const result = await run(["--", "--tools=read,browser,herdr_agent"]);
	expect(result.code).toBe(0);
	expect(calls()[1].argv).toContain("--tools=read,browser,herdr_agent");
});

test("propagates the OMP child exit status", async () => {
	process.env.FAKE_EXIT = "37";
	const result = await run(["--"]);

	expect(result.code).toBe(37);
});

test("forwards termination signals to the OMP child", async () => {
	const signal = join(root, "signal");
	const env = {
		...process.env,
		FAKE_STARTED: "1",
		FAKE_SIGNAL: signal,
		FAKE_WAIT_SIGNAL: "1",
	};
	const child = Bun.spawn([process.execPath, launcher, "--"], {
		env,
		stdout: "pipe",
		stderr: "pipe",
	});
	const reader = child.stdout.getReader();
	const decoder = new TextDecoder();
	let output = "";
	while (!output.includes("FAKE_STARTED")) {
		const chunk = await reader.read();
		if (chunk.done)
			throw new Error("fake OMP exited before signaling readiness");
		output += decoder.decode(chunk.value, { stream: true });
	}
	reader.releaseLock();
	child.kill("SIGTERM");
	const code = await child.exited;

	expect(code).toBe(44);
	expect(readFileSync(signal, "utf8")).toBe("SIGTERM");
}, 5_000);
