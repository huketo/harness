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
	writeFileSync(
		join(dir, "herdr-hitl"),
		`#!/bin/sh
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
`,
		{ mode: 0o755 },
	);
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
	const child = Bun.spawn(
		[
			process.execPath,
			"--eval",
			`
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
		let active = ["read"];
		herdrExtension({
			zod: z,
			on(name, handler) { handlers[name] = handler; },
			registerCommand() {},
			registerTool() {},
			getActiveTools() { return active; },
			async setActiveTools(names) { active = names; },
		});
		const result = await handlers.tool_call({
			type: "tool_call", toolCallId: "test",
			toolName: ${JSON.stringify(toolName)}, input: {},
		});
		console.log(JSON.stringify(result ?? null));
	`,
		],
		{ env: process.env, stdout: "pipe", stderr: "pipe" },
	);
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
	expect(result?.reason).toContain(
		"herdr-hitl channel failed (exit 1): channel unavailable.",
	);
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
	expect(result?.reason).toContain(
		"herdr-hitl channel failed (exit 0): not json.",
	);
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

async function trial(enabled: boolean) {
	const child = Bun.spawn(
		[
			process.execPath,
			"--eval",
			`
		import herdrExtension from ${JSON.stringify(extensionURL)};
		const schema = { min(){return this}, optional(){return this},
			describe(){return this}, int(){return this}, positive(){return this} };
		const z = Object.fromEntries(["object","array","string","boolean","number","enum"]
			.map(name => [name, () => schema]));
		const handlers = {}, tools = {};
		let active = ["read","browser","goal","eval","task","herdr_agent"];
		herdrExtension({
			zod:z, on(name,fn){handlers[name]=fn},
			registerCommand(){},
			registerTool(tool){tools[tool.name]=tool},
			getActiveTools(){return active},
			async setActiveTools(names){active=names},
		});
		await handlers.session_start?.();
		const startup = [...active];
		active.push("task", "eval");
		await handlers.before_agent_start({systemPrompt:["base"]});
		const blocked = await handlers.tool_call({toolName:"task",input:{}});
		const completed = await handlers.tool_call({toolName:"goal",input:{op:"get"}});
		console.log(JSON.stringify({active,startup,blocked,completed,
			loadMode:tools.herdr_agent.loadMode}));
	`,
		],
		{
			env: {
				...process.env,
				HERDR_ENV: "1",
				HARNESS_DELEGATION: enabled ? "agy" : "",
			},
			stdout: "pipe",
			stderr: "pipe",
		},
	);
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	if (code) throw new Error(stderr);
	return JSON.parse(stdout);
}

test("trial routes delegation away from native task without disabling ordinary tools", async () => {
	const result = await trial(true);
	expect(result.active).not.toContain("task");
	expect(result.active).not.toContain("eval");
	expect(result.active).toContain("read");
	expect(result.active).toContain("browser");
	expect(result.active).toContain("goal");
	expect(result.startup).not.toContain("task");
	expect(result.startup).not.toContain("eval");
	expect(result.blocked?.block).toBe(true);
	expect(result.completed).toBeUndefined();
	expect(result.loadMode).toBe("essential");
});

test("normal sessions keep native delegation available", async () => {
	const result = await trial(false);
	expect(result.active).toContain("task");
	expect(result.blocked).toBeUndefined();
});

test("slash command transitions restore only removed tools and reset mode and model on session switch", async () => {
	const child = Bun.spawn(
		[
			process.execPath,
			"--eval",
			`
		import herdrExtension from ${JSON.stringify(extensionURL)};
		const schema = {min(){return this},optional(){return this},describe(){return this},
			int(){return this},positive(){return this}};
		const z = Object.fromEntries(["object","array","string","boolean","number","enum"]
			.map(name => [name, () => schema]));
		const handlers={},commands={},notices=[];
		let active=["read","task","other"];
		herdrExtension({zod:z,on(name,fn){handlers[name]=fn},
			registerCommand(name,command){commands[name]=command},
			registerTool(){},
			getActiveTools(){return active},
			async setActiveTools(names){active=names},
			sendMessage(){}});
		const ctx={hasUI:true,isIdle(){return true},ui:{
			notify(message,level){notices.push({message,level})},
			async select(){return "agy-opus-thinking"}
		}};
		await handlers.session_start();
		await commands.delegation.handler("",ctx);
		const initial={active:[...active],notice:notices.at(-1)};
		await commands.delegation.handler("agy",ctx);
		const agy={active:[...active],notice:notices.at(-1)};
		active.push("late");
		await commands.delegation.handler("native",ctx);
		const native={active:[...active],notice:notices.at(-1)};
		await commands.delegation.handler("model",ctx);
		const selected=notices.at(-1);
		await commands.delegation.handler("off",ctx);
		const off={active:[...active],notice:notices.at(-1)};
		const blocked=await handlers.tool_call({toolName:"eval",input:{}});
		await handlers.session_switch();
		await commands.delegation.handler("",ctx);
		console.log(JSON.stringify({initial,agy,native,selected,off,blocked,
			reset:{active,notice:notices.at(-1)}}));
	`,
		],
		{
			env: { ...process.env, HERDR_ENV: "1", HARNESS_DELEGATION: "" },
			stdout: "pipe",
			stderr: "pipe",
		},
	);
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	if (code) throw new Error(stderr);
	const result = JSON.parse(stdout);
	expect(result.initial.active).toEqual(["read", "task", "other"]);
	expect(result.initial.notice.message).toContain("Delegation mode: native");
	expect(result.initial.notice.message).toContain(
		"default worker model: agy-flash",
	);
	expect(result.agy.active).toEqual(["read", "other", "herdr_agent"]);
	expect(result.agy.notice.message).toContain("Delegation mode: agy");
	expect(result.native.active).toEqual(["read", "other", "late", "task"]);
	expect(result.native.active).not.toContain("eval");
	expect(result.native.notice.message).toContain("Delegation mode: native");
	expect(result.selected.message).toContain(
		"default worker model: agy-opus-thinking (profile agy-review)",
	);
	expect(result.off.active).toEqual(["read", "other", "late", "herdr_agent"]);
	expect(result.blocked.block).toBe(true);
	expect(result.reset.active).toEqual(["read", "other", "late", "task"]);
	expect(result.reset.notice.message).toContain("Delegation mode: native");
	expect(result.reset.notice.message).toContain(
		"default worker model: agy-flash (profile agy-work)",
	);
});

test("agy mode is rejected outside Herdr without changing native tools", async () => {
	const child = Bun.spawn(
		[
			process.execPath,
			"--eval",
			`
		import herdrExtension from ${JSON.stringify(extensionURL)};
		const schema={min(){return this},optional(){return this},describe(){return this},
			int(){return this},positive(){return this}};
		const z=Object.fromEntries(["object","array","string","boolean","number","enum"]
			.map(name=>[name,()=>schema]));
		const commands={},notices=[];
		let active=["read","task","eval"];
		herdrExtension({zod:z,on(){},registerTool(){},
			registerCommand(name,command){commands[name]=command},
			getActiveTools(){return active},async setActiveTools(names){active=names}});
		await commands.delegation.handler("agy",{hasUI:false,isIdle(){return true},
			ui:{notify(message,level){notices.push({message,level})}}});
		console.log(JSON.stringify({active,notice:notices.at(-1)}));
	`,
		],
		{
			env: { ...process.env, HERDR_ENV: "", HARNESS_DELEGATION: "agy" },
			stdout: "pipe",
			stderr: "pipe",
		},
	);
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	if (code) throw new Error(stderr);
	const result = JSON.parse(stdout);
	expect(result.active).toEqual(["read", "task", "eval"]);
	expect(result.notice.level).toBe("warning");
	expect(result.notice.message).toContain("mode remains unchanged");
});

test("trial delivers a retained worker result and prevents overlapping follow-ups", async () => {
	writeFileSync(
		join(dir, "bun"),
		`#!${process.execPath}
import { appendFileSync, existsSync, watch } from "node:fs";
const args = process.argv.slice(3);
appendFileSync(process.env.FAKE_RUN_CALLS, JSON.stringify({
	args,
	delegation: process.env.HARNESS_DELEGATION
}) + "\\n");
if (args[0] === "agent" && args.includes("failed")) {
	console.error("launch failed after retention");
	process.exit(1);
}
if (args[0] === "wait") {
	const gate = Promise.withResolvers();
	const watcher = watch(process.env.FAKE_WAIT_DIR, () => {
		if (existsSync(process.env.FAKE_WAIT_RELEASE)) gate.resolve();
	});
	if (existsSync(process.env.FAKE_WAIT_RELEASE)) gate.resolve();
	await gate.promise;
	watcher.close();
	console.log(JSON.stringify({ok:true, agentStatus:"idle", output:"worker answer"}));
} else {
	console.log(JSON.stringify({ok:true, agentStatus:"working"}));
}
`,
		{ mode: 0o755 },
	);
	const child = Bun.spawn(
		[
			process.execPath,
			"--eval",
			`
		import {readFileSync,writeFileSync} from "node:fs";
		import herdrExtension from ${JSON.stringify(extensionURL)};
		const schema = {min(){return this},optional(){return this},describe(){return this},
			int(){return this},positive(){return this}};
		const z = Object.fromEntries(["object","array","string","boolean","number","enum"]
			.map(name => [name, () => schema]));
		const handlers={},commands={},tools={},messages=[],notices=[];
		const {promise:delivery,resolve:delivered} = Promise.withResolvers();
		let active=["read","goal","task","eval"];
		herdrExtension({zod:z,on(name,fn){handlers[name]=fn},
			registerCommand(name,command){commands[name]=command},
			registerTool(tool){tools[tool.name]=tool},
			getActiveTools(){return active},
			async setActiveTools(names){active=names},
			sendMessage(message){messages.push(message);delivered()}});
		const tool=tools.herdr_agent;
		const ctx={cwd:${JSON.stringify(dir)}};
		const commandCtx={hasUI:false,isIdle(){return true},
			ui:{notify(message,level){notices.push({message,level})}}};
		await commands.delegation.handler("model agy-opus-thinking",commandCtx);
		const failed=await tool.execute("failed",{action:"start",name:"failed",prompt:"Inspect failure"},undefined,undefined,ctx);
		const start=await tool.execute("1",{action:"start",name:"worker",profile:"agy-work",role:"implementer",prompt:"Implement the assigned behavior"},undefined,undefined,ctx);
		await commands.delegation.handler("off",commandCtx);
		const blockedStart=await tool.execute("off",{action:"start",name:"other",prompt:"Do more"},undefined,undefined,ctx);
		const readFailed=await tool.execute("read-failed",{action:"read",name:"failed"},undefined,undefined,ctx);
		const readOff=await tool.execute("read-off",{action:"read",name:"worker"},undefined,undefined,ctx);
		await commands.delegation.handler("native",commandCtx);
		const retainedToolVisible=active.includes("herdr_agent");
		const readNative=await tool.execute("read-native",{action:"read",name:"worker"},undefined,undefined,ctx);
		const overlap=await tool.execute("2",{action:"send",name:"worker",text:"Replace the task"},undefined,undefined,ctx);
		await handlers.session_switch();
		await commands.delegation.handler("",commandCtx);
		const resetStatus=notices.at(-1);
		const goal=await handlers.tool_call({toolName:"goal",input:{op:"complete"}});
		writeFileSync(process.env.FAKE_WAIT_RELEASE,"go");
		await delivery;
		const completed=await handlers.tool_call({toolName:"goal",input:{op:"complete"}});
		await tool.execute("close-worker",{action:"close",name:"worker"},undefined,undefined,ctx);
		await tool.execute("close-failed",{action:"close",name:"failed"},undefined,undefined,ctx);
		await commands.delegation.handler("",commandCtx);
		const closedStatus=notices.at(-1);
		await handlers.session_shutdown();
		const calls=readFileSync(process.env.FAKE_RUN_CALLS,"utf8").trim().split("\\n").map(JSON.parse);
		console.log(JSON.stringify({start,failed,blockedStart,readOff,readFailed,
			readNative,overlap,goal,completed,messages,resetStatus,calls,retainedToolVisible,closedStatus}));
	`,
		],
		{
			env: {
				...process.env,
				HERDR_ENV: "1",
				HARNESS_DELEGATION: "agy",
				FAKE_RUN_CALLS: join(dir, "calls"),
				FAKE_WAIT_RELEASE: join(dir, "release"),
				FAKE_WAIT_DIR: dir,
			},
			stdout: "pipe",
			stderr: "pipe",
		},
	);
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	if (code) throw new Error(stderr);
	const result = JSON.parse(stdout);
	expect(result.start.isError).toBe(false);
	expect(result.blockedStart.isError).toBe(true);
	expect(result.failed.isError).toBe(true);
	expect(result.readFailed.isError).toBe(false);
	expect(result.readOff.isError).toBe(false);
	expect(result.readNative.isError).toBe(false);
	expect(result.overlap.isError).toBe(true);
	expect(result.goal.block).toBe(true);
	expect(result.completed).toBeUndefined();
	expect(result.retainedToolVisible).toBe(true);
	expect(result.closedStatus.message).toContain("managed workers: none");
	expect(result.resetStatus.message).toContain("Delegation mode: agy");
	expect(result.resetStatus.message).toContain(
		"default worker model: agy-flash",
	);
	expect(result.resetStatus.message).toContain("pending workers: worker");
	expect(result.resetStatus.message).toContain(
		"managed workers: failed, worker",
	);
	const launch = result.calls.find((call: { args: string[] }) =>
		call.args.includes(
			"--prompt=Role: implementer\nImplement the assigned behavior",
		),
	);
	expect(launch.args).toContain("agy-review");
	const retainedReads = result.calls.filter(
		(call: { args: string[] }) => call.args[0] === "read",
	);
	expect(retainedReads).toHaveLength(3);
	expect(
		retainedReads.every(
			(call: { delegation?: string }) => call.delegation === "agy",
		),
	).toBe(true);
	expect(result.messages).toHaveLength(1);
	expect(result.messages[0].content).toContain("worker answer");
}, 10000);
