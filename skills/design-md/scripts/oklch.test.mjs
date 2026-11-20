// Contract tests for skills/design-md/scripts/oklch.mjs: the color forms it reads, the ones it refuses, and the CLI output.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { test } from "node:test";
import { NAMED_COLORS, deltaEOK, format, labToLch, parseColor } from "./oklch.mjs";

const SCRIPT = join(import.meta.dirname, "oklch.mjs");

function cli(...args) {
	return spawnSync(process.execPath, [SCRIPT, ...args], { encoding: "utf8" });
}

// [input, L, C, H, alpha]; H is null when chroma is under 0.0001 (grays).
const KNOWN = [
	["#fff", 1, 0, null, 1],
	["#ffffff", 1, 0, null, 1],
	["#000000", 0, 0, null, 1],
	["#808080", 0.5999, 0, null, 1],
	["#f00", 0.628, 0.2577, 29.23, 1],
	["#ff0000", 0.628, 0.2577, 29.23, 1],
	["#00ff00", 0.8664, 0.2948, 142.5, 1],
	["#0000ff", 0.452, 0.3132, 264.05, 1],
	["#f008", 0.628, 0.2577, 29.23, 136 / 255],
	["#ff000080", 0.628, 0.2577, 29.23, 128 / 255],
	["#FF0000", 0.628, 0.2577, 29.23, 1],
	["rgb(255, 0, 0)", 0.628, 0.2577, 29.23, 1],
	["rgb(100% 0% 0%)", 0.628, 0.2577, 29.23, 1],
	["rgb(255 0 0 / 50%)", 0.628, 0.2577, 29.23, 0.5],
	["rgba(255, 0, 0, .25)", 0.628, 0.2577, 29.23, 0.25],
	["hsl(0 100% 50%)", 0.628, 0.2577, 29.23, 1],
	["hsla(120, 100%, 25%, 0.5)", 0.5183, 0.1764, 142.5, 0.5],
	["hsl(0.5turn 100% 50%)", 0.9054, 0.1546, 194.77, 1],
	["hwb(0 0% 0%)", 0.628, 0.2577, 29.23, 1],
	["hwb(0 60% 60%)", 0.5982, 0, null, 1],
	["hwb(0 0% 0% / 0.4)", 0.628, 0.2577, 29.23, 0.4],
	["oklch(0.628 0.2577 29.23)", 0.628, 0.2577, 29.23, 1],
	["oklch(62.8% 64.425% 29.23deg / 0.8)", 0.628, 0.2577, 29.23, 0.8],
	["oklab(0.628 0.2249 0.1258)", 0.628, 0.2577, 29.22, 1],
	["oklab(0.628 0.2249 0.1258 / 30%)", 0.628, 0.2577, 29.22, 0.3],
	["red", 0.628, 0.2577, 29.23, 1],
	["Green", 0.5197, 0.1765, 142.5, 1],
	["rebeccapurple", 0.4403, 0.1603, 303.37, 1],
	["transparent", 0, 0, null, 0],
];

test("reads hex, rgb(), hsl(), hwb(), oklch(), oklab() and named colors with their alpha", () => {
	for (const [input, L, C, H, alpha] of KNOWN) {
		const color = parseColor(input);
		assert.ok(color, `${input} is read`);
		const [l, c, h] = labToLch(color.lab);
		assert.ok(Math.abs(l - L) < 0.001, `${input}: L ${l}, want ${L}`);
		assert.ok(Math.abs(c - C) < 0.001, `${input}: C ${c}, want ${C}`);
		if (H === null) assert.equal(h, null, `${input}: hue is none`);
		else assert.ok(Math.abs(h - H) < 0.05, `${input}: H ${h}, want ${H}`);
		assert.ok(Math.abs(color.alpha - alpha) < 0.001, `${input}: alpha ${color.alpha}, want ${alpha}`);
	}
});

test("knows the 148 CSS named colors", () => {
	assert.equal(Object.keys(NAMED_COLORS).length, 148);
});

test("refuses color forms it does not read and malformed input", () => {
	const refused = [
		"color(srgb 1 0 0)",
		"color(display-p3 1 0 0)",
		"lab(50% 40 59)",
		"lch(50% 70 40)",
		"color-mix(in oklch, red, blue)",
		"rgb(from red r g b)",
		"oklch(from #ff0000 l c h)",
		"hsl(from red h s l / 0.5)",
		"var(--color-text)",
		"currentColor",
		"#12",
		"#12345",
		"rgb(1 2)",
		"hsl(x 1% 1%)",
		"oklch(0.5 0.1 10 / )",
		"notacolor",
	];
	for (const input of refused) assert.equal(parseColor(input), null, `${input} is refused`);
});

test("measures deltaE OK on the x100 scale", () => {
	const pairs = [
		["#ffffff", "#000000", 100],
		["#6b7280", "#6b7280", 0],
		["#6b7280", "#737373", 2.38],
		["hsl(0 100% 50%)", "red", 0],
		["oklch(0.628 0.2577 29.23)", "#ff0000", 0],
	];
	for (const [a, b, want] of pairs) {
		const d = deltaEOK(parseColor(a), parseColor(b));
		assert.ok(Math.abs(d - want) < 0.02, `${a} ${b}: ${d}, want ${want}`);
	}
});

test("formats OKLCH with alpha only when it is below 1", () => {
	assert.equal(format(labToLch(parseColor("#ff0000").lab), 1), "oklch(0.6280 0.2577 29.23)");
	assert.equal(format(labToLch(parseColor("#808080").lab), 0.5), "oklch(0.5999 0.0000 none / 0.5)");
});

test("CLI prints one OKLCH line per color and a Coverage line", () => {
	const run = cli("#ff0000", "rgb(255 0 0 / 50%)");
	assert.equal(run.status, 0, run.stderr);
	const lines = run.stdout.trim().split("\n");
	assert.equal(lines[0], "#ff0000\toklch(0.6280 0.2577 29.23)");
	assert.equal(lines[1], "rgb(255 0 0 / 50%)\toklch(0.6280 0.2577 29.23 / 0.5)");
	assert.match(lines[2], /^Coverage: 2 color\(s\)/);
});

test("CLI --delta prints deltaE OK and both alphas", () => {
	const run = cli("--delta", "#6b7280", "#737373");
	assert.equal(run.status, 0, run.stderr);
	const [line, coverage] = run.stdout.trim().split("\n");
	assert.equal(line, "#6b7280\t#737373\tdeltaE OK x100 2.38\talpha 1 and 1");
	assert.match(coverage, /^Coverage: 2 colors/);
});

test("CLI --delta says alpha differs past the opacity tolerance and not within it", () => {
	const apart = cli("--delta", "#0f172a", "#0f172acc");
	assert.equal(apart.status, 0, apart.stderr);
	assert.equal(apart.stdout.split("\n")[0], "#0f172a\t#0f172acc\tdeltaE OK x100 0.00\talpha 1 and 0.8\talpha differs");

	const close = cli("--delta", "rgb(15 23 42 / 0.99)", "#0f172a");
	assert.equal(close.status, 0, close.stderr);
	assert.doesNotMatch(close.stdout, /alpha differs/);
});

test("CLI exits 2 on an unreadable color, a bad --delta, an unknown flag or no input", () => {
	for (const args of [["lab(50% 40 59)"], ["#ff0000", "color-mix(in oklch, red, blue)"], ["--delta", "red"], ["--delta", "red", "lch(50% 70 40)"], ["--nope"], []]) {
		const run = cli(...args);
		assert.equal(run.status, 2, `${JSON.stringify(args)} exits 2; stdout ${run.stdout}`);
		assert.match(run.stderr, /^oklch: /, `${JSON.stringify(args)} explains on stderr`);
	}
	assert.match(cli("lch(50% 70 40)").stderr, /cannot read the color lch\(50% 70 40\)/);
});

test("CLI --help exits 0 and names the forms it does not read", () => {
	const run = cli("--help");
	assert.equal(run.status, 0);
	assert.match(run.stdout, /Not read: color\(\), lab\(\), lch\(\), color-mix\(\)/);
});
