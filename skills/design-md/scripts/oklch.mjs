#!/usr/bin/env node
// oklch.mjs: read a CSS color, print it as OKLCH, and measure the OK distance (deltaE OK, x100 scale) between two.
// Node 18+, no dependencies. Run `node scripts/oklch.mjs --help`; tests are in oklch.test.mjs.
// Adapted from design.how's build-design-system/scripts/oklch.mjs (MIT, Copyright (c) 2026 Arlan Marat); see ../LICENSE.design-how.

const HELP = `oklch.mjs: a CSS color to OKLCH, and deltaE OK between two colors

Usage:
  node scripts/oklch.mjs <color>...          one line per color: input, oklch(L C H / alpha), L in 0 to 1
  node scripts/oklch.mjs --delta <a> <b>     the deltaE OK between two colors, 0 to about 100, and their alphas

A color is hex (#rgb, #rgba, #rrggbb, #rrggbbaa), rgb() or rgba(), hsl() or hsla(), hwb(), oklch(), oklab(),
a named color (the CSS list, transparent included). Commas or spaces both work, alpha after a slash or a fourth
comma, as a number or a percent. Angles take deg, grad, rad or turn. Quote functions in the shell.
Alpha is part of the color: it prints after the slash, and --delta prints both alphas and says "alpha differs"
when they are more than 0.02 apart (the opacity tolerance), which makes the pair two colors whatever the
distance. Hue prints as "none" when chroma is under 0.0001, as it is for grays. deltaE OK is the straight-line
distance in OKLab times 100, the scale design-md's references/mapping-rules.md uses: under 0.5 counts as identical, the color
tolerance is 2, and a near pair is under 5. Not read: color(), lab(), lch(), color-mix(), var(), currentColor,
relative colors and system colors.

Exit 0 on success, 2 on bad input.`;

import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

const ALPHA_TOLERANCE = 0.02;

// The CSS named colors, as name and hex.
const NAMED = Object.fromEntries(("aliceblue f0f8ff antiquewhite faebd7 aqua 00ffff aquamarine 7fffd4 azure f0ffff beige f5f5dc bisque ffe4c4 black 000000 blanchedalmond ffebcd blue 0000ff blueviolet 8a2be2 brown a52a2a burlywood deb887 cadetblue 5f9ea0 chartreuse 7fff00 chocolate d2691e coral ff7f50 cornflowerblue 6495ed cornsilk fff8dc crimson dc143c cyan 00ffff darkblue 00008b darkcyan 008b8b darkgoldenrod b8860b darkgray a9a9a9 darkgreen 006400 darkgrey a9a9a9 darkkhaki bdb76b darkmagenta 8b008b darkolivegreen 556b2f darkorange ff8c00 darkorchid 9932cc darkred 8b0000 darksalmon e9967a darkseagreen 8fbc8f darkslateblue 483d8b darkslategray 2f4f4f darkslategrey 2f4f4f darkturquoise 00ced1 darkviolet 9400d3 deeppink ff1493 deepskyblue 00bfff dimgray 696969 dimgrey 696969 dodgerblue 1e90ff firebrick b22222 floralwhite fffaf0 forestgreen 228b22 fuchsia ff00ff gainsboro dcdcdc ghostwhite f8f8ff gold ffd700 goldenrod daa520 gray 808080 green 008000 greenyellow adff2f grey 808080 honeydew f0fff0 hotpink ff69b4 indianred cd5c5c indigo 4b0082 ivory fffff0 khaki f0e68c lavender e6e6fa lavenderblush fff0f5 lawngreen 7cfc00 lemonchiffon fffacd lightblue add8e6 lightcoral f08080 lightcyan e0ffff lightgoldenrodyellow fafad2 lightgray d3d3d3 lightgreen 90ee90 lightgrey d3d3d3 lightpink ffb6c1 lightsalmon ffa07a lightseagreen 20b2aa lightskyblue 87cefa lightslategray 778899 lightslategrey 778899 lightsteelblue b0c4de lightyellow ffffe0 lime 00ff00 limegreen 32cd32 linen faf0e6 magenta ff00ff maroon 800000 mediumaquamarine 66cdaa mediumblue 0000cd mediumorchid ba55d3 mediumpurple 9370db mediumseagreen 3cb371 mediumslateblue 7b68ee mediumspringgreen 00fa9a mediumturquoise 48d1cc mediumvioletred c71585 midnightblue 191970 mintcream f5fffa mistyrose ffe4e1 moccasin ffe4b5 navajowhite ffdead navy 000080 oldlace fdf5e6 olive 808000 olivedrab 6b8e23 orange ffa500 orangered ff4500 orchid da70d6 palegoldenrod eee8aa palegreen 98fb98 paleturquoise afeeee palevioletred db7093 papayawhip ffefd5 peachpuff ffdab9 peru cd853f pink ffc0cb plum dda0dd powderblue b0e0e6 purple 800080 rebeccapurple 663399 red ff0000 rosybrown bc8f8f royalblue 4169e1 saddlebrown 8b4513 salmon fa8072 sandybrown f4a460 seagreen 2e8b57 seashell fff5ee sienna a0522d silver c0c0c0 skyblue 87ceeb slateblue 6a5acd slategray 708090 slategrey 708090 snow fffafa springgreen 00ff7f steelblue 4682b4 tan d2b48c teal 008080 thistle d8bfd8 tomato ff6347 turquoise 40e0d0 violet ee82ee wheat f5deb3 white ffffff whitesmoke f5f5f5 yellow ffff00 yellowgreen 9acd32")
  .split(" ").reduce((pairs, word, i, all) => (i % 2 ? pairs : [...pairs, [word, all[i + 1]]]), []));
export const NAMED_COLORS = NAMED;

const lin = (v) => (v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));

// sRGB channels 0 to 255 to OKLab.
function toOklab(rgb) {
  const [r, g, b] = rgb.map((v) => lin(v / 255));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

// "none" is 0, a percent is a share of `full`, a bare number stays as it is.
const num = (p, full) => {
  if (p === "none") return 0;
  if (p.endsWith("%")) { const v = parseFloat(p); return /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?%$/.test(p) ? (v / 100) * full : NaN; }
  return /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/.test(p) ? parseFloat(p) : NaN;
};
const angle = (p) => {
  if (p === "none") return 0;
  const m = /^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(deg|grad|rad|turn)?$/.exec(p);
  if (!m) return NaN;
  const v = parseFloat(m[1]);
  return { deg: v, grad: v * 0.9, rad: (v * 180) / Math.PI, turn: v * 360 }[m[2] || "deg"];
};
const alphaOf = (p) => (p === undefined ? 1 : Math.min(1, Math.max(0, num(p, 1))));

function hslToRgb(h, s, l) {
  h = ((h % 360) + 360) % 360;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  return [0, 8, 4].map((n) => 255 * (l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1))));
}

function hwbToRgb(h, w, b) {
  if (w + b >= 1) { const g = (255 * w) / (w + b); return [g, g, g]; }
  return hslToRgb(h, 1, 0.5).map((v) => v * (1 - w - b) + 255 * w);
}

// A CSS color to {lab: [L, a, b], alpha}, or null when it cannot be read.
export function parseColor(input) {
  const s = String(input).trim().toLowerCase();
  if (s === "transparent") return { lab: toOklab([0, 0, 0]), alpha: 0 };
  if (NAMED[s]) return parseColor(`#${NAMED[s]}`);
  let m = s.match(/^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/);
  if (m) {
    let h = m[1];
    if (h.length <= 4) h = [...h].map((c) => c + c).join("");
    const rgb = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
    return { lab: toOklab(rgb), alpha: h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1 };
  }
  m = s.match(/^(rgba?|hsla?|hwb|oklch|oklab)\(\s*([^)]*)\)$/);
  if (!m) return null;
  const [fn, body] = [m[1], m[2]];
  const slash = body.split("/");
  if (slash.length > 2) return null;
  // Comma syntax keeps empty slots so "255,,0" fails to read instead of collapsing to three channels.
  const channels = slash[0].trim();
  let parts = channels.includes(",") ? channels.split(",").map((p) => p.trim()) : channels.split(/\s+/).filter(Boolean);
  let a = slash[1]?.trim();
  if (a === "") return null;
  if (a === undefined && parts.length === 4) a = parts.pop();
  if (parts.length !== 3) return null;
  const alpha = alphaOf(a);
  let lab;
  if (fn.startsWith("rgb")) {
    const rgb = parts.map((p) => num(p, 255));
    if (rgb.some((v) => !Number.isFinite(v))) return null;
    lab = toOklab(rgb.map((v) => Math.min(255, Math.max(0, v))));
  } else if (fn.startsWith("hsl") || fn === "hwb") {
    const [h, x, y] = [angle(parts[0]), num(parts[1], 100) / 100, num(parts[2], 100) / 100];
    if (![h, x, y].every(Number.isFinite)) return null;
    const clamp = (v) => Math.min(1, Math.max(0, v));
    lab = toOklab(fn === "hwb" ? hwbToRgb(h, clamp(x), clamp(y)) : hslToRgb(h, clamp(x), clamp(y)));
  } else if (fn === "oklch") {
    const [L, C, H] = [num(parts[0], 1), num(parts[1], 0.4), angle(parts[2])];
    if (![L, C, H].every(Number.isFinite)) return null;
    const c = Math.max(0, C);
    lab = [Math.min(1, Math.max(0, L)), c * Math.cos((H * Math.PI) / 180), c * Math.sin((H * Math.PI) / 180)];
  } else {
    const [L, A, B] = [num(parts[0], 1), num(parts[1], 0.4), num(parts[2], 0.4)];
    if (![L, A, B].every(Number.isFinite)) return null;
    lab = [Math.min(1, Math.max(0, L)), A, B];
  }
  if (a !== undefined && !Number.isFinite(alpha)) return null;
  return { lab, alpha };
}

export const labToLch = ([L, a, b]) => {
  const C = Math.hypot(a, b);
  return [L, C, C < 0.0001 ? null : ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360];
};

// deltaE OK between two colors returned by parseColor.
export function deltaEOK({ lab: p }, { lab: q }) {
  return 100 * Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
}

// A difference equal to the tolerance is inside it; the epsilon absorbs float error such as 1 - 0.98.
const alphaDiffers = (a, b) => Math.abs(a - b) > ALPHA_TOLERANCE + 1e-9;

export const format = ([L, C, H], alpha = 1) => `oklch(${L.toFixed(4)} ${C.toFixed(4)} ${H === null ? "none" : H.toFixed(2)}${alpha < 1 ? ` / ${+alpha.toFixed(4)}` : ""})`;

// The installer links skill directories, so compare real paths: a symbolic link must still run the CLI.
if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
  const argv = process.argv.slice(2);
  const bad = (msg) => { console.error(`oklch: ${msg}\n\n${HELP}`); process.exit(2); };
  if (!argv.length) bad("give a color or --delta <a> <b>");
  if (argv.includes("--help") || argv.includes("-h")) { console.log(HELP); process.exit(0); }
  if (argv[0] === "--delta") {
    if (argv.length !== 3) bad("--delta takes exactly two colors");
    const [a, b] = argv.slice(1).map((c) => parseColor(c) || bad(`cannot read the color ${c}`));
    const differs = alphaDiffers(a.alpha, b.alpha);
    console.log(`${argv[1]}\t${argv[2]}\tdeltaE OK x100 ${deltaEOK(a, b).toFixed(2)}\talpha ${+a.alpha.toFixed(4)} and ${+b.alpha.toFixed(4)}${differs ? "\talpha differs" : ""}`);
    console.log("Coverage: 2 colors, alpha compared on its own. Not read: color spaces beyond sRGB, OKLab and OKLCH");
    process.exit(0);
  }
  const unknown = argv.find((a) => a.startsWith("--"));
  if (unknown) bad(`unknown ${unknown}`);
  for (const c of argv) {
    const p = parseColor(c);
    if (!p) bad(`cannot read the color ${c}`);
    console.log(`${c}\t${format(labToLch(p.lab), p.alpha)}`);
  }
  console.log(`Coverage: ${argv.length} color(s) with alpha. Not read: color spaces beyond sRGB, OKLab and OKLCH`);
}
