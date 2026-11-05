import { parseArgs } from "node:util";
import { KEY_PATTERN } from "../schema.ts";

export const DEFAULT_MODEL = "claude-opus-5-5";
export const DEFAULT_RUNS = 1;
export const DEFAULT_PARALLEL = 3;
export const DEFAULT_TIMEOUT_SEC = 900;

export const USAGE =
	"usage: bun scripts/skill-eval/run.ts --suite <suite.json> [--iteration <n>] [--case <id,...>] [--arm <key,...>] [--runs <n>] [--model <m>] [--effort <e>] [--parallel <p>] [--ref <arm>=<gitref>] [--out-root <dir>] [--force] [--dry-run]";

export interface CliOptions {
	suite: string;
	iteration?: number;
	cases?: string[];
	arms?: string[];
	/** Undefined when not given, so a resumed iteration can keep its recorded value. */
	runs?: number;
	model?: string;
	effort?: string;
	parallel: number;
	/** `--ref <arm>=<gitref>` overrides, keyed by arm. */
	refs: Record<string, string>;
	outRoot?: string;
	force: boolean;
	dryRun: boolean;
}

function positiveInt(flag: string, value: string | undefined): number | undefined {
	if (value === undefined) return undefined;
	if (!/^[1-9][0-9]*$/.test(value)) throw new Error(`${flag}: positive integer required, got "${value}"`);
	return Number(value);
}

function list(values: string[] | undefined): string[] | undefined {
	if (!values) return undefined;
	return values.flatMap((v) => v.split(",")).map((v) => v.trim()).filter(Boolean);
}

export function parseCli(argv: string[]): CliOptions {
	const { values, positionals } = parseArgs({
		args: argv,
		strict: true,
		allowPositionals: true,
		options: {
			suite: { type: "string" },
			iteration: { type: "string" },
			case: { type: "string", multiple: true },
			arm: { type: "string", multiple: true },
			runs: { type: "string" },
			model: { type: "string" },
			effort: { type: "string" },
			parallel: { type: "string" },
			ref: { type: "string", multiple: true },
			"out-root": { type: "string" },
			force: { type: "boolean", default: false },
			"dry-run": { type: "boolean", default: false },
		},
	});
	if (positionals.length) throw new Error(`unexpected argument "${positionals[0]}"`);
	if (!values.suite) throw new Error("--suite is required");
	const refs: Record<string, string> = {};
	for (const r of values.ref ?? []) {
		const at = r.indexOf("=");
		const arm = r.slice(0, at);
		const ref = r.slice(at + 1);
		if (at < 1 || !ref || !KEY_PATTERN.test(arm)) throw new Error(`--ref: expected <arm>=<gitref>, got "${r}"`);
		if (arm in refs) throw new Error(`--ref: arm "${arm}" given twice`);
		refs[arm] = ref;
	}
	return {
		suite: values.suite,
		iteration: positiveInt("--iteration", values.iteration),
		cases: list(values.case),
		arms: list(values.arm),
		runs: positiveInt("--runs", values.runs),
		model: values.model,
		effort: values.effort,
		parallel: positiveInt("--parallel", values.parallel) ?? DEFAULT_PARALLEL,
		refs,
		outRoot: values["out-root"],
		force: values.force ?? false,
		dryRun: values["dry-run"] ?? false,
	};
}
