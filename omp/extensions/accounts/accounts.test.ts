import { expect, test } from "bun:test";
import {
	mkdirSync,
	mkdtempSync,
	readFileSync,
	realpathSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import type * as AuthModule from "@oh-my-pi/pi-ai/auth-storage";
import type {
	ExtensionAPI,
	ExtensionCommandContext,
} from "@oh-my-pi/pi-coding-agent";
import extension from "./index";

// Resolve from the installed OMP CLI, not Bun's auto-install cache (the latter
// lacks OMP's native addon). Only the extension host/UI is substituted.
const omp = Bun.which("omp");
if (!omp)
	throw new Error("Account integration tests require an installed OMP CLI.");
const { AuthStorage, SqliteAuthCredentialStore } = (await import(
	Bun.resolveSync("@oh-my-pi/pi-ai/auth-storage", dirname(realpathSync(omp)))
)) as typeof AuthModule;
async function fixture() {
	const dir = mkdtempSync(join(tmpdir(), "harness-accounts-"));
	const stores: AuthModule.AuthStorage[] = [];
	type Entry = { type: "custom"; customType: string; data: unknown };
	const histories = new Map<string, Entry[]>();
	const open = async () => {
		const auth = new AuthStorage(
			await SqliteAuthCredentialStore.open(join(dir, "auth.db")),
			{
				usageProviderResolver: () => undefined,
			},
		);
		stores.push(auth);
		await auth.reload();
		return auth;
	};
	const seed = await open();
	await seed.set(
		"openai-codex",
		[1, 2].map((id) => ({
			type: "oauth" as const,
			access: `fake-access-${id}`,
			refresh: `fake-refresh-${id}`,
			expires: Date.now() + 3_600_000,
			accountId: `account-${id}`,
			email: `person-${id}@example.test`,
		})),
	);
	async function session(id: string, agentDir = dir) {
		const auth = await open();
		type Hook = (
			event: { type: string; messages: unknown[] },
			ctx: ExtensionCommandContext,
		) => unknown;
		const hooks = new Map<string, Hook>();
		const entries = histories.get(id) ?? [];
		histories.set(id, entries);
		const notices: string[] = [];
		let command: Parameters<ExtensionAPI["registerCommand"]>[1];
		let picked: string | undefined;
		// The extension only uses the modeled host capabilities below.
		const ctx = {
			model: { provider: "openai-codex" },
			modelRegistry: { authStorage: auth },
			sessionManager: { getSessionId: () => id, getBranch: () => entries },
			isIdle: () => true,
			hasUI: false,
			ui: {
				notify: (message: string) => notices.push(message),
				select: async () => picked,
			},
		} as unknown as ExtensionCommandContext;
		extension({
			pi: { getAgentDir: () => agentDir },
			on: (name: string, hook: Hook) => hooks.set(name, hook),
			appendEntry: (customType: string, data: unknown) =>
				entries.push({ type: "custom", customType, data }),
			registerCommand: (
				_: string,
				value: Parameters<ExtensionAPI["registerCommand"]>[1],
			) => {
				command = value;
			},
		} as unknown as ExtensionAPI);
		const event = async (type: string) =>
			hooks.get(type)?.({ type, messages: [] }, ctx);
		await event("session_start");
		return {
			auth,
			ctx,
			notices,
			event,
			command: (args: string) => command.handler(args, ctx),
			pick: (label?: string) => {
				ctx.hasUI = true;
				picked = label;
			},
			active: () =>
				auth.listOAuthAccounts("openai-codex", id).find((a) => a.active)
					?.accountId,
			request: async () => {
				await event("context");
				return auth.getApiKey("openai-codex", id);
			},
		};
	}
	return {
		dir,
		session,
		close: () => {
			for (const store of stores) store.close();
			rmSync(dir, { recursive: true, force: true });
		},
	};
}

test("profile account overrides existing sessions and survives a new extension instance", async () => {
	const f = await fixture();
	try {
		const a = await f.session("a");
		const b = await f.session("b");
		await b.command("2");
		await a.command("1 --profile");
		expect(await b.request()).toBe("fake-access-1");
		const c = await f.session("c");
		expect(await c.request()).toBe("fake-access-1");
		await b.command("2");
		expect(await b.request()).toBe("fake-access-1");
		await c.command("2 --profile");
		expect(await a.request()).toBe("fake-access-2");
		expect(await b.request()).toBe("fake-access-2");
	} finally {
		f.close();
	}
});

test("shared auto releases every session once without erasing later local choices on resume", async () => {
	const f = await fixture();
	try {
		const a = await f.session("a");
		const b = await f.session("b");
		await a.command("1 --profile");
		await b.request();
		await a.command("auto --profile");
		await b.event("context");
		expect(b.active()).toBeUndefined();
		await b.command("2");
		expect(await b.request()).toBe("fake-access-2");
		const resumed = await f.session("b");
		expect(await resumed.request()).toBe("fake-access-2");
	} finally {
		f.close();
	}
});

test("profile scopes are isolated and unflagged account changes remain session-local", async () => {
	const f = await fixture();
	try {
		const a = await f.session("a");
		const b = await f.session("b");
		const isolated = await f.session("isolated", join(f.dir, "other-profile"));
		await b.command("2");
		await isolated.command("2");
		await a.command("1");
		expect(await b.request()).toBe("fake-access-2");
		await a.command("1 --profile");
		expect(await b.request()).toBe("fake-access-1");
		expect(await isolated.request()).toBe("fake-access-2");
	} finally {
		f.close();
	}
});

test("shared selection follows credential identity when account positions shift", async () => {
	const f = await fixture();
	try {
		const a = await f.session("a");
		await a.command("2 --profile");
		const first = a.auth.listOAuthAccounts("openai-codex")[0];
		await a.auth.removeCredential("openai-codex", first.credentialId);
		const b = await f.session("b");
		expect(await b.request()).toBe("fake-access-2");
		await a.auth.removeCredential(
			"openai-codex",
			a.auth.listOAuthAccounts("openai-codex")[0].credentialId,
		);
		await b.event("context");
		expect(b.active()).toBeUndefined();
		await b.command("auto --profile");
		expect(
			JSON.parse(
				readFileSync(join(f.dir, "harness-accounts/openai-codex.json"), "utf8"),
			).credentialId,
		).toBeNull();
	} finally {
		f.close();
	}
});

test("picker cancellation, invalid selectors, and streaming do not overwrite the shared choice", async () => {
	const f = await fixture();
	try {
		const a = await f.session("a");
		const b = await f.session("b");
		a.pick("2. person-2@example.test");
		await a.command("--profile");
		expect(await b.request()).toBe("fake-access-2");
		a.pick();
		await a.command("--profile");
		await a.command("99 --profile");
		await a.command("1 --unknown");
		a.ctx.isIdle = () => false;
		await a.command("1 --profile");
		expect(await b.request()).toBe("fake-access-2");
	} finally {
		f.close();
	}
});

test("failed persistence does not leave an unsaved session account change", async () => {
	const f = await fixture();
	try {
		const a = await f.session("a");
		await a.command("2");
		a.ctx.hasUI = true;
		a.ctx.ui.select = async () => {
			// A destination appearing while the picker is open makes the real
			// atomic rename fail, after the native session pin has succeeded.
			mkdirSync(join(f.dir, "harness-accounts/openai-codex.json"), {
				recursive: true,
			});
			return "1. person-1@example.test";
		};
		await a.command("--profile");
		expect(a.active()).toBe("account-2");
		expect(a.notices.at(-1)).toMatch(/EISDIR|EEXIST|EPERM/);
	} finally {
		f.close();
	}
});

test("another provider's shared preference is retained when selecting this provider", async () => {
	const f = await fixture();
	try {
		mkdirSync(join(f.dir, "harness-accounts"));
		const other = join(f.dir, "harness-accounts/anthropic.json");
		const saved = '{\"revision\":\"other\",\"credentialId\":42}\\n';
		writeFileSync(other, saved);
		const a = await f.session("a");
		await a.command("1 --profile");
		expect(readFileSync(other, "utf8")).toBe(saved);
	} finally {
		f.close();
	}
});
