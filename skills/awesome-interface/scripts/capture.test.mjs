// Tests for capture.mjs against a local server whose page sends writes on load. Each case checks what reached
// the server. Cases that need Playwright and a Chromium skip when find-chromium finds none.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { launchChromium } from "./find-chromium.mjs";

const CAPTURE = join(import.meta.dirname, "capture.mjs");
const PIXDIFF = join(import.meta.dirname, "pixdiff.mjs");
const BROWSER_CASE = { timeout: 120_000 };

// The page fires one request of each method on load. window.writesDone settles once every one is answered or
// aborted, so the "sent" state below waits for all of them before the screenshot.
const itemsPage = (boxColor) => `<!doctype html><html><head><style>
body { margin: 0; font: 16px sans-serif; } #box { width: 120px; height: 60px; background: ${boxColor}; }
</style></head><body><h1>Items</h1><button>Save</button><div id="box"></div><script>
window.writesDone = Promise.allSettled([
  fetch("/rpc/items/update", { method: "POST", body: '{"id":1,"count":2}' }),
  fetch("/api/items/1", { method: "PUT", body: '{"count":3}' }),
  fetch("/api/items/1", { method: "PATCH", body: '{"count":4}' }),
  fetch("/api/items/1", { method: "DELETE" }),
  fetch("/rpc/items/list", { method: "POST", body: "{}" }),
  fetch("/api/items"),
]);
</script></body></html>`;

const WRITE = /^(POST|PUT|PATCH|DELETE) /;
let server, base, dir, page, noBrowser;
const hits = [];

before(async () => {
	dir = mkdtempSync(join(tmpdir(), "capture-test-"));
	page = itemsPage("#1f6feb");
	server = createServer((req, res) => {
		hits.push(`${req.method} ${req.url}`);
		const html = (body) => { res.writeHead(200, { "content-type": "text/html" }); res.end(body); };
		if (req.url === "/") html(page);
		else if (req.url === "/gone") { res.writeHead(404); res.end(); }
		else if (req.url === "/private") { res.writeHead(302, { location: "/login" }); res.end(); }
		else if (req.url === "/login") html("<!doctype html><html><body><h1>Log in</h1></body></html>");
		else if (req.url === "/blank") html("<!doctype html><html><body></body></html>");
		else { res.writeHead(200, { "content-type": "application/json" }); res.end("{}"); }
	});
	await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
	base = `http://127.0.0.1:${server.address().port}`;
	writeFileSync(join(dir, "surfaces.tsv"), "surface\troute\tstates\nitems\t/\tsent\n");
	writeFileSync(join(dir, "steps.mjs"), "export default { sent: (page) => page.evaluate(() => window.writesDone) };\n");
	writeFileSync(join(dir, "writes.txt"), [`POST ${base}/rpc/items/update`, `PUT ${base}/api/items/1`, `PATCH ${base}/api/items/1`, `DELETE ${base}/api/items/1`].join("\n") + "\n");
	const launched = await launchChromium();
	if (launched.browser) await launched.browser.close();
	else noBrowser = `no Playwright and Chromium: ${launched.error.split("\n")[0]}`;
});

after(() => {
	server?.close();
	if (dir) rmSync(dir, { recursive: true, force: true });
});

// The server lives in this process, so the child must not block the event loop. The child keeps this
// process's working folder, where find-chromium looks for Playwright.
const run = (script, ...args) => new Promise((ok) => {
	const child = spawn(process.execPath, [script, ...args]);
	let out = "";
	child.stdout.on("data", (d) => (out += d));
	child.stderr.on("data", (d) => (out += d));
	child.on("close", (code) => ok({ code, out }));
});
const capture = (...args) => run(CAPTURE, "--base", base, ...args);
const readLog = (file) => readFileSync(file, "utf8").trim().split("\n").map((l) => JSON.parse(l));

test("--status fails a route that answers other than expected", async () => {
	let r = await capture("--status", "--routes", "/", "/gone");
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /FAIL\t\/gone\t404/);
	r = await capture("--status", "--routes", "/", "gone=/gone", "--expect-status", "gone=404");
	assert.equal(r.code, 0, r.out);
});

test("--status reports a redirect with its Location unless it was expected", async () => {
	let r = await capture("--status", "--routes", "/private");
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /FAIL\t\/private\t302 -> \/login/);
	r = await capture("--status", "--routes", "private=/private", "--expect-status", "private=302");
	assert.equal(r.code, 0, r.out);
});

test("a non-local --base is refused without --allow-host", async () => {
	const r = await run(CAPTURE, "--base", "http://app.example.com", "--status", "--routes", "/");
	assert.equal(r.code, 2, r.out);
	assert.match(r.out, /not a local host/);
});

test("a capture with no proof that writes are blocked sends no request", async () => {
	const seen = hits.length;
	const r = await capture("--kind", "before", "--out", join(dir, "noproof"), "--routes", "/");
	assert.equal(r.code, 2, r.out);
	assert.match(r.out, /--writes <file>.*--no-backend/);
	assert.equal(hits.length, seen);
});

test("a write the guard would let through stops the run before any request", async () => {
	const seen = hits.length;
	const r = await capture("--kind", "before", "--out", join(dir, "leak"), "--routes", "/", "--writes", join(dir, "writes.txt"), "--read-procedures", "items/update");
	assert.equal(r.code, 2, r.out);
	assert.match(r.out, /LEAK\tPOST/);
	assert.equal(hits.length, seen);
});

test("no write reaches the server, GETs do, and guard.log keeps no request body by default", BROWSER_CASE, async (t) => {
	if (noBrowser) return t.skip(noBrowser);
	hits.length = 0;
	const out = join(dir, "default");
	const r = await capture("--kind", "before", "--out", out, "--surfaces", join(dir, "surfaces.tsv"), "--states", join(dir, "steps.mjs"), "--widths", "390", "--no-backend");
	assert.equal(r.code, 0, r.out);
	assert.match(r.out, /WARN\tthe app sent \d+ write/);
	assert.ok(existsSync(join(out, "items.sent-before-390.png")), r.out);
	assert.deepEqual(hits.filter((h) => WRITE.test(h)), []);
	assert.ok(hits.includes("GET /api/items"), hits.join(", "));
	const log = readLog(join(out, "guard.log"));
	for (const method of ["POST", "PUT", "PATCH", "DELETE"]) assert.ok(log.some((l) => l.method === method && l.action === "abort"), `${method} not aborted in ${JSON.stringify(log)}`);
	assert.ok(log.every((l) => !("body" in l)), JSON.stringify(log));
});

test("--bodies records each write's body, and a listed POST read continues", BROWSER_CASE, async (t) => {
	if (noBrowser) return t.skip(noBrowser);
	hits.length = 0;
	const out = join(dir, "bodies");
	const bodies = join(dir, "evidence", "bodies.before.json");
	const r = await capture("--kind", "before", "--out", out, "--surfaces", join(dir, "surfaces.tsv"), "--states", join(dir, "steps.mjs"), "--widths", "390", "--writes", join(dir, "writes.txt"), "--read-procedures", "items/list", "--bodies", bodies);
	assert.equal(r.code, 0, r.out);
	assert.match(r.out, /every one of 4 writes in --writes blocked/);
	assert.deepEqual(hits.filter((h) => WRITE.test(h) && h !== "POST /rpc/items/list"), []);
	assert.ok(hits.includes("POST /rpc/items/list") && hits.includes("GET /api/items"), hits.join(", "));
	const log = readLog(join(out, "guard.log"));
	assert.ok(log.some((l) => l.action === "abort" && /items\/update/.test(l.url) && l.body === '{"id":1,"count":2}'), JSON.stringify(log));
	assert.ok(log.filter((l) => l.method === "GET").every((l) => !("body" in l)));
	const rows = JSON.parse(readFileSync(bodies, "utf8")).rows;
	assert.ok(rows.some((x) => x.method === "POST" && x.proc === "items/update" && x.body === '{"id":1,"count":2}' && x.action === "abort"), JSON.stringify(rows));
	assert.ok(rows.some((x) => x.method === "PATCH" && x.body === '{"count":4}'), JSON.stringify(rows));
});

test("a blank render is not kept as a capture", BROWSER_CASE, async (t) => {
	if (noBrowser) return t.skip(noBrowser);
	const r = await capture("--kind", "before", "--out", join(dir, "blank"), "--routes", "/blank", "--widths", "16", "--height", "16", "--no-backend");
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /blank render/);
	assert.equal(existsSync(join(dir, "blank", "blank-before-16.png")), false);
});

test("a capture with a planned state missing exits 1 and names it", BROWSER_CASE, async (t) => {
	if (noBrowser) return t.skip(noBrowser);
	const r = await capture("--kind", "before", "--out", join(dir, "short"), "--surfaces", join(dir, "surfaces.tsv"), "--widths", "390", "--no-backend");
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /1 of 2 planned/);
	assert.match(r.out, /not captured\titems\.sent/);
});

test("pixdiff finds the one element changed between a before and an after capture, and nothing between two of the same page", BROWSER_CASE, async (t) => {
	if (noBrowser) return t.skip(noBrowser);
	const shots = join(dir, "shots");
	const again = join(dir, "again");
	const shoot = (kind, out) => capture("--kind", kind, "--out", out, "--routes", "/", "--widths", "390", "--no-backend", "--no-aria");
	page = itemsPage("#1f6feb");
	for (const [kind, out] of [["before", shots], ["after", again]]) { const r = await shoot(kind, out); assert.equal(r.code, 0, r.out); }
	let r = await run(PIXDIFF, shots, again, "--no-image");
	assert.equal(r.code, 0, r.out);
	assert.match(r.out, /home-before-390\.png\tsame size\t0%\tno change/);
	page = itemsPage("#d1242f");
	r = await shoot("after", shots);
	assert.equal(r.code, 0, r.out);
	r = await run(PIXDIFF, shots, shots);
	assert.equal(r.code, 1, r.out);
	assert.match(r.out, /bbox \d+,\d+ 120x60/);
	assert.ok(existsSync(join(shots, "home-after-390.diff.png")), r.out);
});
