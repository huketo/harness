#!/usr/bin/env bun
/**
 * Opt-in launcher for the Harness AGY-first Herdr delegation trial.
 * It only composes public OMP CLI flags and a temporary per-invocation config.
 */
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import {
	mkdtempSync,
	readdirSync,
	realpathSync,
	rmSync,
	statSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const HERDR_EXTENSION = realpathSync.native(
	join(import.meta.dir, "extensions/herdr/index.ts"),
);
const HERDR_EXTENSION_DIR = realpathSync.native(
	join(import.meta.dir, "extensions/herdr"),
);
const TRIAL_CONFIG = `magicKeywords:
  orchestrate: false
  workflow: false
task:
  eager: default
`;

const HELP = `Usage: bun omp/herdr-trial.ts -- [OMP args]

Experimental, opt-in AGY-first Herdr delegation launcher.

Requirements and scope:
  - HERDR_ENV=1 is required.
  - HARNESS_DELEGATION=agy is set only for the launched OMP session.
  - Initial routing is AGY-first; /delegation can change the current session's mode.
  - AGY/off routing omits task and eval, including eval's native agent()/workpool().
  - The repository's omp/extensions/herdr/index.ts is loaded explicitly.
  - Interactive OMP is the default; existing -p/--print and other OMP args pass through.

This launcher installs nothing, creates no profile or home, copies no auth, and never
writes global or project configuration. It uses a temporary --config overlay that is
removed when OMP exits, so live settings remain unchanged.

Bun consumes the first -- separator. Use \`omp --help\` for OMP's own CLI help.
`;

function fail(message: string): never {
	process.stderr.write(`herdr-trial: ${message}\n`);
	process.exit(1);
}

function optionArea(args: string[]): string[] {
	const separator = args.indexOf("--");
	return separator === -1 ? args : args.slice(0, separator);
}

function rejectConflicts(args: string[]): void {
	for (const arg of optionArea(args)) {
		if (
			arg === "--trusted-extension" ||
			arg.startsWith("--trusted-extension=")
		) {
			fail(
				"--trusted-extension cannot be combined with the trial's required --extension.",
			);
		}
	}
}

function profileArgs(args: string[]): string[] {
	const options = optionArea(args);
	let selected: string[] = [];
	for (let index = 0; index < options.length; index++) {
		const arg = options[index];
		if (arg === "--profile") {
			const value = options[index + 1];
			if (!value || value.startsWith("-")) fail("--profile requires a value.");
			selected = ["--profile", value];
			index++;
		} else if (arg.startsWith("--profile=")) {
			const value = arg.slice("--profile=".length);
			if (!value) fail("--profile requires a value.");
			selected = [`--profile=${value}`];
		}
	}
	return selected;
}

function resolveAgentDir(args: string[]): string {
	const result = spawnSync("omp", [...profileArgs(args), "config", "path"], {
		encoding: "utf8",
		stdio: ["ignore", "pipe", "pipe"],
	});
	const path = result.stdout?.trim();
	if (result.status !== 0 || !path) {
		fail(
			`could not resolve the active OMP agent directory with \`omp config path\`: ${
				result.stderr?.trim() ||
				result.error?.message ||
				`exit ${result.status}`
			}`,
		);
	}
	return path;
}

/**
 * OMP de-duplicates extension paths lexically after path.resolve(), not by
 * realpath. If the trial extension is already installed as a symlink, pass
 * that installed spelling explicitly so ambient and explicit discovery meet
 * at the same lexical path instead of binding the extension twice.
 */
function extensionArgument(agentDir: string): string {
	const extensionsDir = join(agentDir, "extensions");
	let entries: string[];
	try {
		entries = readdirSync(extensionsDir);
	} catch {
		return HERDR_EXTENSION;
	}
	for (const entry of entries) {
		const candidate = join(extensionsDir, entry);
		try {
			const resolved = realpathSync.native(candidate);
			if (resolved === HERDR_EXTENSION) return candidate;
			if (
				resolved !== HERDR_EXTENSION_DIR ||
				!statSync(candidate).isDirectory()
			)
				continue;
			// A directory argument makes OMP discover its index.ts using the same
			// installed lexical prefix used by ambient extension discovery.
			return candidate;
		} catch {
			// Ignore unrelated dangling or unreadable extension entries.
		}
	}
	return HERDR_EXTENSION;
}

function insertBeforeSeparator(args: string[], enforced: string[]): string[] {
	const separator = args.indexOf("--");
	if (separator === -1) return [...args, ...enforced];
	return [...args.slice(0, separator), ...enforced, ...args.slice(separator)];
}

function mirrorSignal(signal: NodeJS.Signals): never {
	try {
		process.kill(process.pid, signal);
	} catch {
		const numbers: Partial<Record<NodeJS.Signals, number>> = {
			SIGHUP: 1,
			SIGINT: 2,
			SIGQUIT: 3,
			SIGTERM: 15,
		};
		process.exit(128 + (numbers[signal] ?? 1));
	}
	throw new Error(`failed to terminate with ${signal}`);
}

async function launch(args: string[]): Promise<never> {
	rejectConflicts(args);
	const extension = extensionArgument(resolveAgentDir(args));
	const configDir = mkdtempSync(join(tmpdir(), "harness-herdr-trial-"));
	const configPath = join(configDir, "config.yml");
	writeFileSync(configPath, TRIAL_CONFIG, { mode: 0o600 });

	const ompArgs = insertBeforeSeparator(args, [
		"--config",
		configPath,
		"--extension",
		extension,
		// Tool selection is filtered dynamically by the extension's public hooks.
	]);
	let child: ChildProcess;
	try {
		child = spawn("omp", ompArgs, {
			stdio: "inherit",
			env: { ...process.env, HARNESS_DELEGATION: "agy" },
		});
	} catch (error) {
		rmSync(configDir, { recursive: true, force: true });
		fail(`could not start omp: ${String(error)}`);
	}

	const signals: NodeJS.Signals[] = ["SIGHUP", "SIGINT", "SIGQUIT", "SIGTERM"];
	const handlers = new Map<NodeJS.Signals, () => void>();
	for (const signal of signals) {
		const handler = () => child.kill(signal);
		handlers.set(signal, handler);
		process.on(signal, handler);
	}

	const { promise, resolve } = Promise.withResolvers<{
		code: number | null;
		signal: NodeJS.Signals | null;
		error?: Error;
	}>();
	child.once("error", (error) => resolve({ code: null, signal: null, error }));
	child.once("exit", (code, signal) => resolve({ code, signal }));
	const outcome = await promise;
	for (const [signal, handler] of handlers) process.off(signal, handler);
	rmSync(configDir, { recursive: true, force: true });

	if (outcome.error) fail(`omp failed to start: ${outcome.error.message}`);
	if (outcome.signal) mirrorSignal(outcome.signal);
	process.exit(outcome.code ?? 1);
}

const rawArgs = process.argv.slice(2);
if (rawArgs.length === 1 && (rawArgs[0] === "--help" || rawArgs[0] === "-h")) {
	process.stdout.write(HELP);
	process.exit(0);
}
if (process.env.HERDR_ENV !== "1")
	fail("HERDR_ENV=1 is required; run this launcher inside Herdr.");
await launch(rawArgs);
