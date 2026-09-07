#!/usr/bin/env bun
/**
 * Standalone CLI over omp/profiles.json + the harness-profiles-state.json
 * override store (agent dir found via `omp config path`). Runs OUTSIDE any
 * OMP process (invoked directly by Herdr, cron, or a human), so it never
 * imports `@oh-my-pi/*` packages -- see extensions/profiles/schema.ts's
 * header for why that import fails when done from a bare script. Model
 * existence / effort support are NOT re-validated against the live catalog
 * here (that would mean shelling out to `omp models --json`/`agy models` on
 * every invocation); trust omp/profiles.json's own installed-catalog-verified
 * data and let a stale entry fail at the runner instead.
 */
import { spawnSync } from "node:child_process";
import {
	buildArgv,
	loadProfiles,
	loadState,
	type ProfilesFile,
	type ProfilesState,
	resolveModelEffort,
	resolveProfile,
	resolveRoles,
	saveState,
	selectorString,
	validateProfilesFile,
} from "./extensions/profiles/schema";

function fail(message: string): never {
	process.stderr.write(`${message}\n`);
	process.exit(1);
}

function agentDir(): string {
	const result = spawnSync("omp", ["config", "path"], { encoding: "utf8" });
	if (result.status !== 0 || !result.stdout.trim()) {
		fail(
			`Could not resolve the OMP agent directory (ran \`omp config path\`): ` +
				`${result.stderr?.trim() || result.error?.message || `exit ${result.status}`}`,
		);
	}
	return result.stdout.trim();
}

function loadAll(): { profiles: ProfilesFile; state: ProfilesState } {
	const profiles = loadProfiles();
	const errors = validateProfilesFile(profiles);
	if (errors.length > 0) fail(`Invalid profiles:\n${errors.join("\n")}`);
	const state = loadState(agentDir());
	return { profiles, state };
}

function cmdList(): void {
	const { profiles, state } = loadAll();
	const rows = Object.keys(profiles.profiles)
		.sort()
		.map((name) => {
			const resolved = resolveProfile(profiles, state, name);
			return {
				name,
				runner: resolved.runner,
				model: `${resolved.provider}/${resolved.model}`,
				effort: resolved.effort,
				purpose: resolved.purpose,
			};
		});
	const nameWidth = Math.max(...rows.map((r) => r.name.length), 4);
	const modelWidth = Math.max(...rows.map((r) => r.model.length), 5);
	for (const row of rows) {
		process.stdout.write(
			`${row.name.padEnd(nameWidth)}  ${row.runner.padEnd(4)}  ${row.model.padEnd(modelWidth)}  ${row.effort.padEnd(7)}  ${row.purpose}\n`,
		);
	}
}

function cmdShow(name: string): void {
	const { profiles, state } = loadAll();
	const resolved = resolveProfile(profiles, state, name);
	process.stdout.write(
		`${JSON.stringify(
			{
				name: resolved.name,
				runner: resolved.runner,
				provider: resolved.provider,
				model: resolved.model,
				effort: resolved.effort,
				purpose: resolved.purpose,
			},
			null,
			2,
		)}\n`,
	);
}

function parseArgvFlags(rest: string[]): { addDir: string[]; agent?: string } {
	const addDir: string[] = [];
	let agent: string | undefined;
	for (let i = 0; i < rest.length; i++) {
		if (rest[i] === "--add-dir")
			addDir.push(rest[++i] ?? fail("--add-dir requires a value"));
		else if (rest[i] === "--agent")
			agent = rest[++i] ?? fail("--agent requires a value");
		else fail(`Unknown flag "${rest[i]}"`);
	}
	return { addDir, agent };
}

function cmdArgv(name: string, rest: string[]): void {
	const { profiles, state } = loadAll();
	const resolved = resolveProfile(profiles, state, name);
	process.stdout.write(
		`${JSON.stringify(buildArgv(resolved, parseArgvFlags(rest)))}\n`,
	);
}

function cmdRoles(): void {
	const profiles = loadProfiles();
	process.stdout.write(`${JSON.stringify(resolveRoles(profiles), null, 2)}\n`);
}

function cmdSelector(name: string, defaults = false): void {
	const profiles = loadProfiles();
	const state = defaults
		? { version: 1 as const, modelEffort: {}, profileEffort: {} }
		: loadState(agentDir());
	const resolved = resolveProfile(profiles, state, name);
	try {
		process.stdout.write(`${selectorString(resolved)}\n`);
	} catch (err) {
		fail(err instanceof Error ? err.message : String(err));
	}
}

function cmdEffortGet(name: string): void {
	const { profiles, state } = loadAll();
	if (profiles.profiles[name]) {
		const resolved = resolveProfile(profiles, state, name);
		process.stdout.write(`${resolved.effort} (${resolved.effortSource})\n`);
		return;
	}
	if (profiles.models[name]) {
		const { effort, source } = resolveModelEffort(profiles, state, name);
		process.stdout.write(`${effort} (${source})\n`);
		return;
	}
	fail(`"${name}" is neither a known profile nor a known model key.`);
}

function cmdEffortSet(name: string, level: string): void {
	const dir = agentDir();
	const profiles = loadProfiles();
	const state = loadState(dir);
	const key = profiles.profiles[name]?.model ?? name;
	const model = profiles.models[key];
	if (!model) fail(`Unknown profile or model: ${name}`);
	const supported =
		model.provider === "agy"
			? ["low", "medium", "high"]
			: ["low", "medium", "high", "xhigh", "max"];
	if (level !== "reset" && !supported.includes(level))
		fail(`Supported efforts: ${supported.join(", ")}; or reset`);
	if (profiles.profiles[name]) {
		if (level === "reset") delete state.profileEffort[name];
		else state.profileEffort[name] = level;
		saveState(dir, state);
		process.stdout.write(
			`Saved effort "${level}" for profile "${name}" (independent of its model's saved effort).\n`,
		);
		return;
	}
	if (profiles.models[name]) {
		if (level === "reset") delete state.modelEffort[name];
		else state.modelEffort[name] = level;
		saveState(dir, state);
		process.stdout.write(
			`Saved effort "${level}" for model "${name}" (independent of any profile).\n`,
		);
		return;
	}
	fail(`"${name}" is neither a known profile nor a known model key.`);
}

function usage(): never {
	fail(
		[
			"Usage: bun omp/profiles.ts <command> [args]",
			"",
			"  list                            List every named profile, its resolved model + effort",
			"  show NAME                       Resolved JSON: {name,runner,provider,model,effort,purpose}",
			"  argv NAME [--add-dir DIR]... [--agent NAME]",
			"                                  JSON argv array for launching NAME as a native CLI process",
			"  roles                           Declared compatibility roles (ignores personal effort overrides)",
			"  selector NAME [--defaults]      provider/model:effort; --defaults ignores personal overrides",
			"  effort get NAME                 Resolved effort + its source, for a profile or a model key",
			"  effort set NAME LEVEL           Persist a model/profile override; LEVEL=reset restores inheritance",
		].join("\n"),
	);
}

const [command, ...args] = process.argv.slice(2);
switch (command) {
	case "list":
		cmdList();
		break;
	case "show":
		args[0] ? cmdShow(args[0]) : usage();
		break;
	case "argv":
		args[0] ? cmdArgv(args[0], args.slice(1)) : usage();
		break;
	case "roles":
		cmdRoles();
		break;
	case "selector":
		args[0] ? cmdSelector(args[0], args.includes("--defaults")) : usage();
		break;
	case "effort":
		if (args[0] === "get" && args[1]) cmdEffortGet(args[1]);
		else if (args[0] === "set" && args[1] && args[2])
			cmdEffortSet(args[1], args[2]);
		else usage();
		break;
	default:
		usage();
}
