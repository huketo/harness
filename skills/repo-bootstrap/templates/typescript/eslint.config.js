// Each restriction below is one row of the rule table in AGENTS.md. A message names what to use instead, because
// the agent that trips the rule reads only that message.
import { builtinModules } from "node:module";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

// A feature is one flat directory under src/core. Code outside it imports its index.ts and nothing else.
const message = "Import a feature through its index.ts. If index.ts lacks what you need, export it there.";
const deepFeatureImport = { regex: "(^|/)core/[^/]+/(?!index\\.ts$).+", message };
const siblingFeatureImport = { regex: "^\\.\\./(?!\\.\\.)[^/]+/(?!index\\.ts$).+", message };
const shellFromCore = {
	regex: "(^|/)shell(/|$)",
	message: "src/core is pure. Declare the dependency as a type in core and pass the shell's implementation in as an argument.",
};
// Node built-ins with or without the node: prefix: "node:fs", "fs", "fs/promises".
const builtins = builtinModules.filter((name) => !name.startsWith("_") && !name.includes("/")).join("|");
const io = "src/core does no I/O. Move the call to src/shell and pass its result or a function into core.";
const nodeFromCore = { regex: `^(?:node:|(?:${builtins})(?:/|$))`, message: io };
const nodeFromCoreTest = { regex: `^(?!node:(?:test|assert(?:/strict)?)$)(?:node:|(?:${builtins})(?:/|$))`, message: io };

export default defineConfig(
	{ ignores: ["node_modules/"] },
	...tseslint.configs.recommendedTypeChecked,
	{
		languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } },
		rules: { "@typescript-eslint/switch-exhaustiveness-check": "error" },
	},
	{ files: ["eslint.config.js"], ...tseslint.configs.disableTypeChecked },
	// node:test returns a promise the runner already tracks.
	{ files: ["src/**/*.test.ts"], rules: { "@typescript-eslint/no-floating-promises": "off" } },
	{
		files: ["src/shell/**/*.ts"],
		rules: { "no-restricted-imports": ["error", { patterns: [deepFeatureImport] }] },
	},
	{
		files: ["src/core/**/*.ts"],
		rules: { "no-restricted-imports": ["error", { patterns: [deepFeatureImport, siblingFeatureImport, shellFromCore, nodeFromCore] }] },
	},
	{
		// A core test may import node:test and node:assert; every other core restriction still applies.
		files: ["src/core/**/*.test.ts"],
		rules: {
			"no-restricted-imports": ["error", { patterns: [deepFeatureImport, siblingFeatureImport, shellFromCore, nodeFromCoreTest] }],
		},
	},
);
