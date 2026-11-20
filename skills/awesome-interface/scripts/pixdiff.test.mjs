// Tests for pixdiff.mjs on synthetic PNGs. Every comparison runs in a Chromium, so the cases skip when
// find-chromium finds none.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { deflateSync } from "node:zlib";
import { after, before, test } from "node:test";
import { launchChromium } from "./find-chromium.mjs";

const PIXDIFF = join(import.meta.dirname, "pixdiff.mjs");

/** A w x h RGBA PNG, every pixel from px(x, y) -> [r, g, b, a]. Enough to test the diff without an image library. */
function png(w, h, px) {
	const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
	const crc = (buf) => { let c = 0xffffffff; for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
	const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
	const head = Buffer.alloc(13); head.writeUInt32BE(w, 0); head.writeUInt32BE(h, 4); head[8] = 8; head[9] = 6;
	const raw = Buffer.alloc(h * (1 + w * 4));
	for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) Buffer.from(px(x, y)).copy(raw, y * (1 + w * 4) + 1 + x * 4);
	return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", head), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

let dir, noBrowser;
const grey = () => [200, 200, 200, 255];
const shot = (name) => join(dir, "shots", name);

before(async () => {
	dir = mkdtempSync(join(tmpdir(), "pixdiff-test-"));
	mkdirSync(join(dir, "shots"));
	writeFileSync(shot("home-before-390.png"), png(20, 10, grey));
	writeFileSync(shot("home-after-390.png"), png(20, 10, grey));
	writeFileSync(shot("card-before-390.png"), png(20, 10, grey));
	writeFileSync(shot("card-after-390.png"), png(20, 10, (x, y) => (x === 3 && y === 4 ? [201, 200, 200, 255] : grey())));
	writeFileSync(join(dir, "wide.png"), png(21, 10, grey));
	const launched = await launchChromium();
	if (launched.browser) await launched.browser.close();
	else noBrowser = `no Playwright and Chromium: ${launched.error.split("\n")[0]}`;
});
after(() => dir && rmSync(dir, { recursive: true, force: true }));

// The child keeps this process's working folder, where find-chromium looks for Playwright.
const pixdiff = (...args) => {
	const r = spawnSync(process.execPath, [PIXDIFF, ...args], { encoding: "utf8" });
	return { code: r.status, out: (r.stdout || "") + (r.stderr || "") };
};

test("a bad --tolerance is refused before any browser starts", () => {
	const r = pixdiff(shot("home-before-390.png"), shot("home-after-390.png"), "--tolerance", "300");
	assert.equal(r.code, 2, r.out);
	assert.match(r.out, /--tolerance takes a whole number/);
});

test("identical images pass at tolerance 0", (t) => {
	if (noBrowser) return t.skip(noBrowser);
	const r = pixdiff(shot("home-before-390.png"), shot("home-after-390.png"));
	assert.equal(r.code, 0, r.out);
	assert.match(r.out, /\t0%\tno change/);
});

test("one channel step on one pixel fails at tolerance 0 and passes at 1", (t) => {
	if (noBrowser) return t.skip(noBrowser);
	let r = pixdiff(shot("card-before-390.png"), shot("card-after-390.png"), "--no-image");
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /bbox 3,4 1x1/);
	assert.match(r.out, /max delta 1/);
	r = pixdiff(shot("card-before-390.png"), shot("card-after-390.png"), "--no-image", "--tolerance", "1");
	assert.equal(r.code, 0, r.out);
});

test("a size change fails", (t) => {
	if (noBrowser) return t.skip(noBrowser);
	const r = pixdiff(shot("card-before-390.png"), join(dir, "wide.png"), "--no-image");
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /20x10 vs 21x10/);
});

test("folder mode pairs before with after, and --surface keeps one surface", (t) => {
	if (noBrowser) return t.skip(noBrowser);
	let r = pixdiff(join(dir, "shots"), join(dir, "shots"), "--surface", "home");
	assert.equal(r.code, 0, r.out);
	assert.match(r.out, /1 compared/);
	assert.match(r.out, /1 of other surfaces skipped/);
	r = pixdiff(join(dir, "shots"), join(dir, "shots"), "--no-image");
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /2 compared, 1 over 0%/);
});
