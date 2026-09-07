import { expect, test } from "bun:test";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { spawn } from "node:child_process";
import {
	mkdirSync,
	mkdtempSync,
	realpathSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import type * as AuthModule from "@oh-my-pi/pi-ai/auth-storage";

const installedOmp = Bun.which("omp");
if (!installedOmp)
	throw new Error("Account runtime tests require an installed OMP CLI.");
const omp = process.env.HARNESS_ACCOUNTS_RUNTIME_OMP ?? installedOmp;
// Overrides are test-only seams for proving the forward compatibility contract
// against a patched private copy; the default invocation always runs the real install.
const installedRoot = dirname(realpathSync(installedOmp));
// Runtime resolution is intentional: the installed compiled CLI owns the native
// auth-storage build, while a static test import can resolve Bun's package cache.
const { AuthStorage, SqliteAuthCredentialStore } = (await import(
	Bun.resolveSync("@oh-my-pi/pi-ai/auth-storage", installedRoot)
)) as typeof AuthModule;
const accountExtension =
	process.env.HARNESS_ACCOUNTS_RUNTIME_EXTENSION ??
	join(import.meta.dir, "index.ts");
const providerFixture = join(import.meta.dir, "accounts.runtime-fixture.ts");
const model = "openai-codex/runtime-routing-model";

type Frame = Record<string, unknown>;
type RequestRecord = {
	authorization: string | null;
	body: Record<string, unknown>;
};

function isFrame(value: unknown): value is Frame {
	return typeof value === "object" && value !== null;
}

async function deadline<T>(
	promise: Promise<T>,
	label: string,
	milliseconds = 10_000,
): Promise<T> {
	// Real child processes cannot use a fake clock; this bounds failure, not successful waiting.
	const timeout = Promise.withResolvers<never>();
	const timer = setTimeout(
		() => timeout.reject(new Error(`${label} timed out`)),
		milliseconds,
	);
	try {
		return await Promise.race([promise, timeout.promise]);
	} finally {
		clearTimeout(timer);
	}
}

class RpcClient {
	readonly #process: ChildProcessWithoutNullStreams;
	readonly #exited: Promise<number | null>;
	readonly #frames: Frame[] = [];
	readonly #waiters: Array<{
		predicate: (frame: Frame) => boolean;
		resolve: (frame: Frame) => void;
		reject: (error: Error) => void;
	}> = [];
	readonly #stderr: Promise<string>;
	#failure?: Error;
	#nextId = 0;

	private constructor(child: ChildProcessWithoutNullStreams) {
		this.#process = child;
		const exited = Promise.withResolvers<number | null>();
		this.#exited = exited.promise;
		child.once("exit", (code) => exited.resolve(code));
		child.once("error", (error) => {
			this.#failure = error;
			exited.resolve(null);
		});
		this.#stderr = (async () => {
			let output = "";
			for await (const chunk of child.stderr) output += chunk.toString();
			return output;
		})();
		void this.#readFrames();
	}

	static async start(
		agentDir: string,
		baseUrl: string,
		providerSessionId?: string,
		resume?: string,
	): Promise<RpcClient> {
		const home = join(agentDir, "home");
		mkdirSync(home, { recursive: true });
		const args = [
			"--mode",
			"rpc",
			"--model",
			model,
			"--thinking",
			"off",
			"--no-extensions",
			"--extension",
			providerFixture,
			"--extension",
			accountExtension,
			"--no-rules",
			"--no-skills",
			"--no-lsp",
			"--no-title",
			"--tools",
			"bash",
			"--approval-mode",
			"yolo",
			"--cwd",
			agentDir,
		];
		if (providerSessionId)
			args.push("--provider-session-id", providerSessionId);
		if (resume) args.push("--resume", resume);
		const child = spawn(omp, args, {
			cwd: agentDir,
			env: {
				PATH: process.env.PATH,
				HOME: home,
				PI_CODING_AGENT_DIR: agentDir,
				HARNESS_ACCOUNTS_RUNTIME_BASE_URL: baseUrl,
				NO_PROXY: "127.0.0.1,localhost",
				no_proxy: "127.0.0.1,localhost",
			},
			// A separate process group lets cleanup terminate the real bash tool too.
			detached: true,
			stdio: ["pipe", "pipe", "pipe"],
		});
		const client = new RpcClient(child);
		try {
			await client.waitFor((frame) => frame.type === "ready", "RPC ready");
			return client;
		} catch (error) {
			await client.kill();
			throw error;
		}
	}

	async command(message: string): Promise<void> {
		const id = this.#id();
		this.#send({ id, type: "prompt", message });
		await this.#successfulResponse(id, "prompt");
		const result = await this.waitFor(
			(frame) => frame.type === "prompt_result" && frame.id === id,
			`local command ${message}`,
		);
		expect(result.agentInvoked).toBe(false);
	}

	async prompt(message: string): Promise<void> {
		// Startup's lifecycle frame must not complete a later prompt.
		for (let index = this.#frames.length - 1; index >= 0; index -= 1) {
			if (this.#frames[index]?.type === "agent_end")
				this.#frames.splice(index, 1);
		}
		const id = this.#id();
		this.#send({ id, type: "prompt", message });
		await this.#successfulResponse(id, "prompt");
		const terminal = await this.waitFor(
			(frame) =>
				(frame.type === "agent_end" && frame.isTerminal !== false) ||
				(frame.type === "response" &&
					frame.id === id &&
					frame.success === false),
			`agent completion for ${message}`,
		);
		if (terminal.type === "response")
			throw new Error(`RPC prompt failed: ${JSON.stringify(terminal)}`);
	}

	async sessionFile(): Promise<string> {
		const id = this.#id();
		this.#send({ id, type: "get_state" });
		const frame = await this.#successfulResponse(id, "get_state");
		const data = frame.data;
		if (!isFrame(data) || typeof data.sessionFile !== "string")
			throw new Error(
				`RPC state omitted sessionFile: ${JSON.stringify(frame)}`,
			);
		return data.sessionFile;
	}

	async close(): Promise<void> {
		this.#process.stdin.end();
		const exitCode = await deadline(this.#exited, "RPC shutdown");
		const stderr = await deadline(this.#stderr, "RPC stderr shutdown");
		if (exitCode !== 0)
			throw new Error(`OMP RPC exited ${exitCode}: ${stderr}`);
	}

	async kill(): Promise<void> {
		if (this.#process.pid) {
			try {
				process.kill(-this.#process.pid, "SIGKILL");
			} catch (error) {
				if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
			}
		}
		await deadline(
			Promise.all([this.#exited, this.#stderr]),
			"RPC process-group cleanup",
			5_000,
		);
	}

	async waitFor(
		predicate: (frame: Frame) => boolean,
		label: string,
	): Promise<Frame> {
		if (this.#failure) throw this.#failure;
		for (const [index, frame] of this.#frames.entries()) {
			if (predicate(frame)) {
				this.#frames.splice(index, 1);
				return frame;
			}
		}
		const { promise, resolve, reject } = Promise.withResolvers<Frame>();
		const waiter = { predicate, resolve, reject };
		this.#waiters.push(waiter);
		const processExit = this.#exited.then(async (exitCode) => {
			const stderr = await deadline(this.#stderr, "RPC stderr");
			throw (
				this.#failure ??
				new Error(
					`OMP RPC exited ${exitCode} while waiting for ${label}; stderr=${stderr}; frames=${JSON.stringify(this.#frames)}`,
				)
			);
		});
		try {
			return await deadline(Promise.race([promise, processExit]), label);
		} finally {
			const index = this.#waiters.indexOf(waiter);
			if (index !== -1) this.#waiters.splice(index, 1);
		}
	}

	async #successfulResponse(id: string, command: string): Promise<Frame> {
		const frame = await this.waitFor(
			(candidate) => candidate.type === "response" && candidate.id === id,
			`${command} response`,
		);
		if (frame.success !== true)
			throw new Error(`RPC ${command} failed: ${JSON.stringify(frame)}`);
		return frame;
	}

	#id(): string {
		this.#nextId += 1;
		return `request-${this.#nextId}`;
	}

	#send(frame: Frame): void {
		this.#process.stdin.write(`${JSON.stringify(frame)}\n`);
	}

	async #readFrames(): Promise<void> {
		let buffered = "";
		this.#process.stdout.setEncoding("utf8");
		try {
			for await (const chunk of this.#process.stdout) {
				buffered += chunk;
				let newline = buffered.indexOf("\n");
				while (newline !== -1) {
					const line = buffered.slice(0, newline).trim();
					buffered = buffered.slice(newline + 1);
					if (line) this.#pushFrame(JSON.parse(line));
					newline = buffered.indexOf("\n");
				}
			}
		} catch (error) {
			this.#failure = error instanceof Error ? error : new Error(String(error));
			for (const waiter of this.#waiters.splice(0))
				waiter.reject(this.#failure);
		}
	}

	#pushFrame(value: unknown): void {
		if (!isFrame(value)) return;
		const waiter = this.#waiters.find((candidate) =>
			candidate.predicate(value),
		);
		if (!waiter) {
			this.#frames.push(value);
			return;
		}
		this.#waiters.splice(this.#waiters.indexOf(waiter), 1);
		waiter.resolve(value);
	}
}

function assistantText(responseId: string): Response {
	const item = {
		id: `message-${responseId}`,
		type: "message",
		role: "assistant",
		status: "completed",
		content: [{ type: "output_text", text: "ok", annotations: [] }],
	};
	return sse([
		...started(responseId),
		{
			type: "response.output_item.added",
			output_index: 0,
			item: { ...item, status: "in_progress", content: [] },
		},
		{
			type: "response.content_part.added",
			item_id: item.id,
			output_index: 0,
			content_index: 0,
			part: { type: "output_text", text: "", annotations: [] },
		},
		{
			type: "response.output_text.delta",
			item_id: item.id,
			output_index: 0,
			content_index: 0,
			delta: "ok",
			logprobs: [],
		},
		{
			type: "response.output_text.done",
			item_id: item.id,
			output_index: 0,
			content_index: 0,
			text: "ok",
			logprobs: [],
		},
		{ type: "response.output_item.done", output_index: 0, item },
		completed(responseId, [item]),
	]);
}

function assistantTool(responseId: string, gate: string): Response {
	const callId = `call-${responseId}`;
	const itemId = `function-${responseId}`;
	const args = JSON.stringify({
		command: `while [ ! -f ${JSON.stringify(gate)} ]; do sleep 0.01; done`,
	});
	const item = {
		id: itemId,
		type: "function_call",
		call_id: callId,
		name: "bash",
		arguments: args,
		status: "completed",
	};
	return sse([
		...started(responseId),
		{
			type: "response.output_item.added",
			output_index: 0,
			item: { ...item, arguments: "", status: "in_progress" },
		},
		{
			type: "response.function_call_arguments.delta",
			item_id: itemId,
			output_index: 0,
			delta: args,
		},
		{
			type: "response.function_call_arguments.done",
			item_id: itemId,
			output_index: 0,
			arguments: args,
		},
		{ type: "response.output_item.done", output_index: 0, item },
		completed(responseId, [item]),
	]);
}
function started(responseId: string): Frame[] {
	const response = {
		id: responseId,
		object: "response",
		created_at: 0,
		status: "in_progress",
		model: "runtime-routing-model",
		output: [],
	};
	return [
		{ type: "response.created", sequence_number: 0, response },
		{ type: "response.in_progress", sequence_number: 1, response },
	];
}

function completed(responseId: string, output: unknown[]): Frame {
	return {
		type: "response.completed",
		sequence_number: 10,
		response: {
			id: responseId,
			object: "response",
			created_at: 0,
			status: "completed",
			model: "runtime-routing-model",
			output,
			incomplete_details: null,
			usage: {
				input_tokens: 1,
				output_tokens: 1,
				total_tokens: 2,
				input_tokens_details: { cached_tokens: 0 },
				output_tokens_details: { reasoning_tokens: 0 },
			},
		},
	};
}

function sse(events: Frame[]): Response {
	const body = events
		.map(
			(event) =>
				`event: ${String(event.type)}\ndata: ${JSON.stringify(event)}\n\n`,
		)
		.join("");
	return new Response(`${body}data: [DONE]\n\n`, {
		headers: { "content-type": "text/event-stream" },
	});
}

async function seed(agentDir: string): Promise<void> {
	mkdirSync(agentDir, { recursive: true });
	const auth = new AuthStorage(
		await SqliteAuthCredentialStore.open(join(agentDir, "agent.db")),
		{
			usageProviderResolver: () => undefined,
		},
	);
	try {
		await auth.reload();
		await auth.set(
			"openai-codex",
			[1, 2].map((id) => ({
				type: "oauth" as const,
				access: `fake-access-${id}`,
				refresh: `fake-refresh-${id}`,
				expires: Date.now() + 3_600_000,
				accountId: `synthetic-account-${id}`,
				email: `synthetic-${id}@example.test`,
			})),
		);
	} finally {
		auth.close();
	}
}

async function runtimeFixture() {
	const records: RequestRecord[] = [];
	const clients: RpcClient[] = [];
	let sequence = 0;
	let toolGate = "";
	const server = Bun.serve({
		hostname: "127.0.0.1",
		port: 0,
		async fetch(request) {
			const url = new URL(request.url);
			if (
				request.method !== "POST" ||
				!url.pathname.endsWith("/codex/responses")
			) {
				return new Response("not found", { status: 404 });
			}
			const body = (await request.json()) as Record<string, unknown>;
			records.push({
				authorization: request.headers.get("authorization"),
				body,
			});
			sequence += 1;
			const serialized = JSON.stringify(body);
			const isToolTurn =
				serialized.includes("runtime-tool") &&
				!serialized.includes("function_call_output");
			return isToolTurn
				? assistantTool(`response-${sequence}`, toolGate)
				: assistantText(`response-${sequence}`);
		},
	});
	let root: string;
	try {
		root = mkdtempSync(join(tmpdir(), "harness-account-runtime-"));
	} catch (error) {
		server.stop(true);
		throw error;
	}
	toolGate = join(root, "tool-gate");
	return {
		root,
		records,
		async start(agentDir: string, providerSessionId?: string, resume?: string) {
			const client = await RpcClient.start(
				agentDir,
				`http://127.0.0.1:${server.port}`,
				providerSessionId,
				resume,
			);
			clients.push(client);
			return client;
		},
		async closeClient(client: RpcClient) {
			await client.close();
			clients.splice(clients.indexOf(client), 1);
		},
		setToolGate(path: string) {
			toolGate = path;
		},
		async close() {
			const results = await Promise.allSettled(
				clients.map((client) => client.kill()),
			);
			server.stop(true);
			const failures = results.filter((result) => result.status === "rejected");
			if (failures.length)
				throw new AggregateError(
					failures.map((result) => result.reason),
					`Runtime cleanup failed; retained ${root}`,
				);
			rmSync(root, { recursive: true, force: true });
		},
	};
}

test("default provider identity keeps a local account across compiled-CLI requests", async () => {
	const fixture = await runtimeFixture();
	const agentDir = join(fixture.root, "agent");
	try {
		await seed(agentDir);
		const selected = await fixture.start(agentDir);
		const sibling = await fixture.start(agentDir);

		await sibling.prompt("default sibling baseline");
		await selected.command("/account 2");
		await selected.prompt("default selected request one");
		await selected.prompt("default selected request two");
		await sibling.prompt("sibling after local selection");

		expect(fixture.records.map((record) => record.authorization)).toEqual([
			"Bearer fake-access-1",
			"Bearer fake-access-2",
			"Bearer fake-access-2",
			"Bearer fake-access-1",
		]);
	} finally {
		await fixture.close();
	}
}, 90_000);

test("divergent provider identity keeps a local account across requests and resume", async () => {
	const fixture = await runtimeFixture();
	const agentDir = join(fixture.root, "agent");
	try {
		await seed(agentDir);
		// /fresh, context reset, and explicit provider overrides can separate these IDs.
		const selected = await fixture.start(agentDir, "selected-provider-session");
		const sibling = await fixture.start(agentDir, "sibling-provider-session");

		await sibling.prompt("sibling baseline");
		await selected.command("/account 2");
		await selected.prompt("selected request one");
		await selected.prompt("selected request two");
		await sibling.prompt("sibling after local selection");
		const sessionFile = await selected.sessionFile();
		await fixture.closeClient(selected);

		const resumed = await fixture.start(
			agentDir,
			"selected-provider-session",
			sessionFile,
		);
		await resumed.prompt("selected request after resume");

		expect(fixture.records.map((record) => record.authorization)).toEqual([
			"Bearer fake-access-1",
			"Bearer fake-access-2",
			"Bearer fake-access-2",
			"Bearer fake-access-1",
			"Bearer fake-access-2",
		]);
	} finally {
		await fixture.close();
	}
}, 90_000);

test("profile account reaches sibling, fresh, and tool-continuation requests without crossing agent dirs", async () => {
	const fixture = await runtimeFixture();
	const sharedDir = join(fixture.root, "shared-agent");
	const isolatedDir = join(fixture.root, "isolated-agent");
	try {
		await seed(sharedDir);
		await seed(isolatedDir);
		const controller = await fixture.start(
			sharedDir,
			"controller-provider-session",
		);
		const sibling = await fixture.start(sharedDir, "sibling-provider-session");
		const isolated = await fixture.start(
			isolatedDir,
			"isolated-provider-session",
		);

		await sibling.command("/account 1");
		await sibling.prompt("existing local selection");

		await controller.command("/account 2 --profile");
		await sibling.prompt("existing sibling request");
		await sibling.command("/account 1");
		await sibling.prompt("shared preference wins over local command");
		const fresh = await fixture.start(sharedDir, "fresh-provider-session");
		await fresh.prompt("fresh shared request");
		await isolated.prompt("isolated request");

		await controller.command("/account 1 --profile");
		const gate = join(fixture.root, "release-tool");
		fixture.setToolGate(gate);
		const toolPrompt = sibling.prompt("runtime-tool").then(
			() => undefined,
			(error: Error) => error,
		);
		await sibling.waitFor(
			(frame) =>
				frame.type === "tool_execution_start" && frame.toolName === "bash",
			"bash tool start",
		);
		await controller.command("/account 2 --profile");
		writeFileSync(gate, "continue\n");
		const toolError = await toolPrompt;
		if (toolError) throw toolError;

		expect(fixture.records.map((record) => record.authorization)).toEqual([
			"Bearer fake-access-1",
			"Bearer fake-access-2",
			"Bearer fake-access-2",
			"Bearer fake-access-2",
			"Bearer fake-access-1",
			"Bearer fake-access-1",
			"Bearer fake-access-2",
		]);
	} finally {
		await fixture.close();
	}
}, 90_000);
