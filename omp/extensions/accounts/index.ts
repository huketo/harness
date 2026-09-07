/**
 * Account preferences use the live AuthStorage, as `/session pin` does.
 * --profile persists a provider-wide preference shared by this OMP agent dir.
 * Native auth/usage recovery remains enabled; this is not a credential lock.
 * Notifications are visible in TUI/RPC, not plain print mode.
 */
import { randomUUID } from "node:crypto";
import {
	mkdirSync,
	readFileSync,
	renameSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { join } from "node:path";
import type {
	ExtensionAPI,
	ExtensionCommandContext,
	ExtensionContext,
} from "@oh-my-pi/pi-coding-agent";

/** Fields this extension reads off `OAuthAccountSummary`; kept structural so it
 *  never needs a runtime import of the type's home package. */
interface AccountLike {
	position: number;
	credentialId: number;
	accountId?: string;
	email?: string;
	projectId?: string;
	enterpriseUrl?: string;
	orgId?: string;
	orgName?: string;
	active: boolean;
}

interface ProfileAccount {
	revision: string;
	credentialId: number | null;
}

type SaveProfile = (credentialId: number | null) => void;
const PROFILE_ENTRY = "harness-account-profile";

function profilePath(agentDir: string, provider: string): string {
	return join(
		agentDir,
		"harness-accounts",
		`${encodeURIComponent(provider)}.json`,
	);
}

function readProfile(
	agentDir: string,
	provider: string,
): ProfileAccount | undefined {
	let raw: string;
	try {
		raw = readFileSync(profilePath(agentDir, provider), "utf8");
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
		throw error;
	}
	const state: unknown = JSON.parse(raw);
	if (
		typeof state !== "object" ||
		state === null ||
		!("revision" in state) ||
		typeof state.revision !== "string" ||
		!("credentialId" in state) ||
		(state.credentialId !== null &&
			(typeof state.credentialId !== "number" ||
				!Number.isSafeInteger(state.credentialId)))
	)
		throw new Error(`Invalid saved account preference for ${provider}.`);
	return { revision: state.revision, credentialId: state.credentialId };
}

function writeProfile(
	agentDir: string,
	provider: string,
	credentialId: number | null,
): ProfileAccount {
	const state = { revision: randomUUID(), credentialId };
	const path = profilePath(agentDir, provider);
	const temporary = `${path}.${state.revision}.tmp`;
	mkdirSync(join(agentDir, "harness-accounts"), { recursive: true });
	try {
		writeFileSync(temporary, `${JSON.stringify(state)}\n`, { mode: 0o600 });
		renameSync(temporary, path);
	} finally {
		rmSync(temporary, { force: true });
	}
	return state;
}

/** Safe, non-secret display label for one stored account. Mirrors the native
 *  `/session pin` labeling (`toSessionPinAccounts` + `formatActiveAccountLabel`)
 *  so the same account renders identically in both places. */
function labelFor(account: AccountLike): string {
	const base = account.email || account.accountId || account.projectId;
	const org = account.orgName || account.orgId;
	if (base) return org && org !== base ? `${base} (${org})` : base;
	const enterprise = account.enterpriseUrl?.trim();
	return enterprise || `OAuth credential #${account.credentialId}`;
}

/** Resolve a `/account <selector>` argument to matching accounts: 1-based
 *  position, or an exact (case-insensitive) match against any identity field. */
function matchSelector(
	accounts: readonly AccountLike[],
	selector: string,
): AccountLike[] {
	const wanted = selector.trim().toLowerCase();
	if (!wanted) return [];
	if (/^\d+$/.test(wanted)) {
		const position = Number(wanted) - 1;
		const positioned = accounts.find(
			(account) => account.position === position,
		);
		if (positioned) return [positioned];
	}
	return accounts.filter((account) =>
		[
			labelFor(account),
			account.email,
			account.accountId,
			account.projectId,
			account.enterpriseUrl,
			account.orgId,
			account.orgName,
			`OAuth credential #${account.credentialId}`,
		].some((value) => value?.trim().toLowerCase() === wanted),
	);
}

/** Keep multi-word identity selectors intact while accepting the scope flag. */
function parseVerb(rawArgs: string): {
	verb: "list" | "auto" | "pin";
	selector: string;
	profile: boolean;
} {
	const tokens = rawArgs.trim().split(/\s+/);
	const profile = tokens.includes("--profile");
	if (tokens.some((token) => token.startsWith("--") && token !== "--profile"))
		throw new Error(
			"Usage: /account [list|auto|number|email|account id] [--profile]",
		);
	const trimmed = rawArgs.replace(/(?:^|\s)--profile(?=\s|$)/g, "").trim();
	if (!trimmed) return { verb: "list", selector: "", profile };
	const lowered = trimmed.toLowerCase();
	if (lowered === "auto" || lowered === "automatic")
		return { verb: "auto", selector: "", profile };
	if (lowered === "list" || lowered === "ls")
		return { verb: "list", selector: "", profile };
	return { verb: "pin", selector: trimmed, profile };
}

async function handlePin(
	ctx: ExtensionCommandContext,
	provider: string,
	sessionId: string,
	accounts: readonly AccountLike[],
	selector: string,
	saveProfile?: SaveProfile,
): Promise<void> {
	const matches = matchSelector(accounts, selector);
	if (matches.length === 0) {
		ctx.ui.notify(`No ${provider} account matches "${selector}".`, "warning");
		return;
	}
	if (matches.length > 1) {
		ctx.ui.notify(
			`"${selector}" matches multiple ${provider} accounts: ${matches
				.map((account) => `${account.position + 1}. ${labelFor(account)}`)
				.join(", ")}. Use the account number.`,
			"warning",
		);
		return;
	}
	const account = matches[0];
	if (!account) return;
	const pinned = ctx.modelRegistry.authStorage.pinSessionOAuthAccount(
		provider,
		sessionId,
		account.credentialId,
	);
	if (pinned && saveProfile) {
		try {
			saveProfile(account.credentialId);
		} catch (error) {
			const previous = accounts.find((candidate) => candidate.active);
			if (previous)
				ctx.modelRegistry.authStorage.pinSessionOAuthAccount(
					provider,
					sessionId,
					previous.credentialId,
				);
			else
				ctx.modelRegistry.authStorage.releaseSessionCredentialForReselection(
					provider,
					sessionId,
				);
			throw error;
		}
	}
	ctx.ui.notify(
		pinned
			? `Selected ${labelFor(account)} for ${provider}${saveProfile ? " across sessions in this OMP profile (other sessions apply it before their next request)" : " in this session"}. OMP may switch accounts after authentication or usage-limit failures.`
			: `${labelFor(account)} is no longer available to pin.`,
		pinned ? "info" : "error",
	);
}

async function handleAuto(
	ctx: ExtensionCommandContext,
	provider: string,
	sessionId: string,
	saveProfile?: SaveProfile,
): Promise<void> {
	saveProfile?.(null);
	const released =
		ctx.modelRegistry.authStorage.releaseSessionCredentialForReselection(
			provider,
			sessionId,
		);
	ctx.ui.notify(
		saveProfile
			? `Restored automatic account selection for ${provider} across sessions in this OMP profile. Other sessions apply it before their next request.`
			: released
				? `Restored automatic account selection for ${provider}. The next request re-ranks by usage headroom.`
				: `${provider} is already on automatic account selection.`,
	);
}

/** Interactive picker for `/account` with no argument in a UI-capable session.
 *  `ctx.ui.select` returns the selected LABEL (not an index), so each option's
 *  label is prefixed with its 1-based position to resolve the pick back to an
 *  account unambiguously; "Automatic" is a distinct, unprefixed sentinel. */
async function handleInteractivePick(
	ctx: ExtensionCommandContext,
	provider: string,
	sessionId: string,
	accounts: readonly AccountLike[],
	saveProfile?: SaveProfile,
): Promise<void> {
	const AUTOMATIC_LABEL = "Automatic (usage-based ranking)";
	const options = [
		...accounts.map((account) => ({
			label: `${account.position + 1}. ${labelFor(account)}`,
			description: account.active ? "active" : undefined,
		})),
		{
			label: AUTOMATIC_LABEL,
			description: accounts.some((account) => account.active)
				? undefined
				: "active",
		},
	];
	const picked = await ctx.ui.select(
		`OAuth accounts for ${provider}${saveProfile ? " — shared OMP profile" : ""}`,
		options,
	);
	if (picked === undefined) return; // cancelled
	if (picked === AUTOMATIC_LABEL) {
		await handleAuto(ctx, provider, sessionId, saveProfile);
		return;
	}
	const position = Number(picked.slice(0, picked.indexOf("."))) - 1;
	const account = accounts.find((candidate) => candidate.position === position);
	if (!account) {
		ctx.ui.notify("Selection is no longer available.", "error");
		return;
	}
	await handlePin(
		ctx,
		provider,
		sessionId,
		accounts,
		String(account.position + 1),
		saveProfile,
	);
}

function listText(
	provider: string,
	accounts: readonly AccountLike[],
	profile?: ProfileAccount,
): string {
	const lines = [`OAuth accounts for ${provider}:`];
	for (const account of accounts) {
		lines.push(
			`${account.position + 1}. ${labelFor(account)}${account.active ? " (active)" : ""}`,
		);
	}
	const selected = accounts.find(
		(account) => account.credentialId === profile?.credentialId,
	);
	lines.push(
		profile?.credentialId != null
			? `Shared profile: ${selected ? labelFor(selected) : `unavailable credential #${profile.credentialId}`} (overrides session preferences).`
			: "Shared profile: automatic.",
	);
	lines.push(
		"",
		"Pin one with `/account <number|email|account id>`.",
		"Restore automatic selection with `/account auto`.",
		"Use `/account <selector> --profile` to select across sessions; `/account auto --profile` to release.",
	);
	return lines.join("\n");
}

export default function accountsExtension(pi: ExtensionAPI): void {
	const agentDir = pi.pi.getAgentDir();
	const applied = new Map<string, string>();
	const remember = (provider: string, state: ProfileAccount) => {
		pi.appendEntry(PROFILE_ENTRY, { provider, revision: state.revision });
		applied.set(provider, state.revision);
	};
	const saveFor =
		(provider: string): SaveProfile =>
		(credentialId) => {
			remember(provider, writeProfile(agentDir, provider, credentialId));
		};

	async function syncProfile(ctx: ExtensionContext) {
		const provider = ctx.model?.provider;
		if (!provider) return;
		const state = readProfile(agentDir, provider);
		if (!state) return;
		const auth = ctx.modelRegistry.authStorage;
		const sessionId = ctx.sessionManager.getSessionId();
		if (state.credentialId !== null) {
			await auth.reload();
			if (
				!auth.pinSessionOAuthAccount(provider, sessionId, state.credentialId)
			) {
				ctx.ui.notify(
					`Shared ${provider} account is unavailable or overridden by an API key. Use /account list or /account auto --profile.`,
					"warning",
				);
				return;
			}
		} else if (applied.get(provider) !== state.revision) {
			auth.releaseSessionCredentialForReselection(provider, sessionId);
		}
		if (applied.get(provider) !== state.revision) remember(provider, state);
	}

	async function restoreProfile(_event: unknown, ctx: ExtensionContext) {
		applied.clear();
		for (const entry of ctx.sessionManager.getBranch()) {
			if (entry.type !== "custom" || entry.customType !== PROFILE_ENTRY)
				continue;
			const data: unknown = entry.data;
			if (
				typeof data === "object" &&
				data !== null &&
				"provider" in data &&
				typeof data.provider === "string" &&
				"revision" in data &&
				typeof data.revision === "string"
			)
				applied.set(data.provider, data.revision);
		}
		await syncProfile(ctx);
	}
	pi.on("session_start", restoreProfile);
	pi.on("session_switch", restoreProfile);
	pi.on("session_tree", restoreProfile);
	// context is awaited before API-key resolution, including tool continuations.
	// before_provider_request is too late: credentials have already been resolved.
	pi.on("context", async (_event, ctx) => {
		await syncProfile(ctx);
	});

	pi.registerCommand("account", {
		description:
			"Choose an OAuth account; --profile saves a shared preference across sessions",
		getArgumentCompletions(argumentPrefix) {
			const options = [
				{
					value: "list",
					label: "list",
					description: "List stored accounts for the active provider",
				},
				{
					value: "auto",
					label: "auto",
					description: "Restore automatic account selection",
				},
				{
					value: "--profile",
					label: "--profile",
					description:
						"Save account selection across sessions in this OMP profile",
				},
			];
			const start = argumentPrefix.lastIndexOf(" ") + 1;
			const tail = argumentPrefix.slice(start).toLowerCase();
			const filtered = options
				.filter((option) => option.value.startsWith(tail))
				.map((option) => ({
					...option,
					value: argumentPrefix.slice(0, start) + option.value,
				}));
			return filtered.length > 0 ? filtered : null;
		},
		async handler(rawArgs, ctx) {
			// Mirrors `/session pin`'s streaming guard: account routing is read
			// alongside in-flight request state, and a pin/release mid-turn must
			// not race the request that is already using the prior credential.
			if (!ctx.isIdle()) {
				ctx.ui.notify(
					"Cannot manage accounts while the session is streaming.",
					"warning",
				);
				return;
			}

			const provider = ctx.model?.provider;
			if (!provider) {
				ctx.ui.notify("Select a model before choosing an account.", "warning");
				return;
			}

			try {
				const { verb, selector, profile } = parseVerb(rawArgs);
				const shared = readProfile(agentDir, provider);
				const saveProfile = profile ? saveFor(provider) : undefined;
				const interactive =
					verb === "list" &&
					ctx.hasUI &&
					!rawArgs.replace(/(?:^|\s)--profile(?=\s|$)/g, "").trim();
				if (
					!profile &&
					shared?.credentialId != null &&
					(verb !== "list" || interactive)
				) {
					ctx.ui.notify(
						"A shared account preference is active. Use /account <selector> --profile to change it or /account auto --profile to release it.",
						"warning",
					);
					return;
				}
				await syncProfile(ctx);
				const sessionId = ctx.sessionManager.getSessionId();
				const authStorage = ctx.modelRegistry.authStorage;

				// Refresh from the backing store (broker or local SQLite) before
				// reading, exactly like `listCurrentProviderOAuthAccounts` — otherwise
				// a login/logout in another process would be invisible here.
				await authStorage.reload();
				const accounts: AccountLike[] = authStorage.listOAuthAccounts(
					provider,
					sessionId,
				);

				if (verb === "auto") {
					await handleAuto(ctx, provider, sessionId, saveProfile);
					return;
				}

				if (accounts.length === 0) {
					const source = authStorage.describeCredentialSource(
						provider,
						sessionId,
					);
					ctx.ui.notify(
						source
							? `No stored OAuth accounts for ${provider}. Current auth comes from ${source}.`
							: `No stored OAuth accounts for ${provider}. Use /login to add one.`,
					);
					return;
				}

				if (verb === "pin") {
					await handlePin(
						ctx,
						provider,
						sessionId,
						accounts,
						selector,
						saveProfile,
					);
					return;
				}

				// verb === "list": bare `/account` in a UI-capable session gets the
				// interactive picker (a real supported ExtensionUIContext operation);
				// everything else (headless, or the explicit `list`/`ls` keyword) gets
				// deterministic text, which is also what a scripted RPC caller sees.
				if (interactive) {
					await handleInteractivePick(
						ctx,
						provider,
						sessionId,
						accounts,
						saveProfile,
					);
					return;
				}
				ctx.ui.notify(listText(provider, accounts, shared));
			} catch (error) {
				ctx.ui.notify(
					error instanceof Error ? error.message : String(error),
					"error",
				);
			}
		},
	});
}
