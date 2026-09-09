import { afterEach, beforeEach, expect, test } from "bun:test";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const extensionURL = new URL("./index.ts", import.meta.url).href;

let dir: string;
let savedEnv: NodeJS.ProcessEnv;
beforeEach(() => {
	savedEnv = { ...process.env };
	dir = mkdtempSync(join(tmpdir(), "herdr-ask-gate-"));
	writeFileSync(join(dir, "herdr-hitl"), `#!/bin/sh
printf called > "$FAKE_HITL_MARKER"
if [ "$FAKE_HITL_EXIT" != 0 ]; then
	printf 'channel unavailable\\nsecond line\\n' >&2
	exit "$FAKE_HITL_EXIT"
fi
if [ -n "$FAKE_HITL_RAW" ]; then
	printf '%s\\n' "$FAKE_HITL_RAW"
else
	printf '{"channel":"%s","policy":"auto","reason":"test"}\\n' "$FAKE_HITL_CHANNEL"
fi
`, { mode: 0o755 });
	process.env.PATH = `${dir}:${savedEnv.PATH ?? ""}`;
	process.env.FAKE_HITL_MARKER = join(dir, "called");
	process.env.FAKE_HITL_CHANNEL = "terminal";
	process.env.FAKE_HITL_EXIT = "0";
	delete process.env.FAKE_HITL_RAW;
	delete process.env.HERDR_ENV;
});
afterEach(() => {
	rmSync(dir, { recursive: true, force: true });
	for (const key of Object.keys(process.env)) {
		if (!(key in savedEnv)) delete process.env[key];
	}
	Object.assign(process.env, savedEnv);
});

async function call(toolName = "ask") {
	const child = Bun.spawn([process.execPath, "--eval", `
		import herdrExtension from ${JSON.stringify(extensionURL)};
		const schema = {
			min() { return this; }, optional() { return this; },
			describe() { return this; }, int() { return this; },
			positive() { return this; },
		};
		const z = Object.fromEntries(
			["object", "array", "string", "boolean", "number", "enum"]
				.map(name => [name, () => schema]),
		);
		const handlers = {};
		herdrExtension({
			zod: z,
			on(name, handler) { handlers[name] = handler; },
			registerTool() {},
		});
		const result = await handlers.tool_call({
			type: "tool_call", toolCallId: "test",
			toolName: ${JSON.stringify(toolName)}, input: {},
		});
		console.log(JSON.stringify(result ?? null));
	`], { env: process.env, stdout: "pipe", stderr: "pipe" });
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	if (code !== 0) throw new Error(stderr);
	return JSON.parse(stdout) ?? undefined;
}

test("other tools bypass channel resolution", async () => {
	expect(await call("bash")).toBeUndefined();
	expect(existsSync(join(dir, "called"))).toBe(false);
});

test("terminal allows ask", async () => {
	expect(await call()).toBeUndefined();
});

test("messenger blocks ask with CLI guidance", async () => {
	process.env.FAKE_HITL_CHANNEL = "messenger";
	const result = await call();
	expect(result?.block).toBe(true);
	expect(result?.reason).toContain("herdr-hitl ask");
});

test("afk blocks ask with autonomy guidance", async () => {
	process.env.FAKE_HITL_CHANNEL = "afk";
	const result = await call();
	expect(result?.block).toBe(true);
	expect(result?.reason).toContain("autonomous/quorum/defer");
});

test("failed channel command blocks ask", async () => {
	process.env.FAKE_HITL_EXIT = "1";
	const result = await call();
	expect(result?.block).toBe(true);
	expect(result?.reason).toContain("herdr-hitl channel failed (exit 1): channel unavailable.");
	expect(result?.reason).not.toContain("second line");
});

test("missing binary allows ask", async () => {
	process.env.PATH = mkdtempSync(join(dir, "empty-"));
	expect(await call()).toBeUndefined();
});

test("malformed channel output blocks ask", async () => {
	process.env.FAKE_HITL_RAW = "not json\nsecond line";
	const result = await call();
	expect(result?.block).toBe(true);
	expect(result?.reason).toContain("herdr-hitl channel failed (exit 0): not json.");
});

test("non-string channel blocks ask", async () => {
	process.env.FAKE_HITL_RAW = '{"channel":null}';
	const result = await call();
	expect(result?.block).toBe(true);
	expect(result?.reason).toContain("herdr-hitl channel failed (exit 0)");
});

test("unknown channel blocks ask", async () => {
	process.env.FAKE_HITL_CHANNEL = "unexpected";
	const result = await call();
	expect(result?.block).toBe(true);
	expect(result?.reason).toContain('unknown channel "unexpected"');
});
