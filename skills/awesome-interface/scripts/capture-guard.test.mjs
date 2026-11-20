// Tests for capture-guard.mjs: the pure decision rules and installGuard against a fake page. No browser, no network.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { PREFIX_READ_VERBS, classifyName, decide, graphqlOps, graphqlProc, installGuard, isGraphqlPath, parseWrites, prove, tokens } from "./capture-guard.mjs";

const GUARD = join(import.meta.dirname, "capture-guard.mjs");

const base = "http://localhost:5173";
const rpc = (p) => `${base}/rpc/${p}`;
const prefix = { readVerbs: PREFIX_READ_VERBS };
const action = (method, url, opts = {}, postData) => decide({ method, url, postData }, opts).action;

let dir;
before(() => (dir = mkdtempSync(join(tmpdir(), "capture-guard-"))));
after(() => rmSync(dir, { recursive: true, force: true }));

test("a POST read is denied until listed by exact name", () => {
	assert.equal(classifyName("items/getItem").read, false);
	assert.equal(classifyName("items/getItem", { readProcedures: ["items/getItem"] }).read, true);
	assert.equal(action("POST", rpc("users/me")), "abort");
	assert.equal(action("POST", rpc("users/me"), { readProcedures: ["me"] }), "continue");
	const denied = decide({ method: "POST", url: rpc("files/get") }, {});
	assert.equal(denied.action, "abort");
	assert.match(denied.reason, /readProcedures/);
	assert.equal(decide({ method: "POST", url: rpc("files/get") }, { fixtures: { "files/get": { body: { url: "x" } } } }).response.status, 200);
});

test("read verbs match the first token only and lose to a write token", () => {
	assert.deepEqual(tokens("itemUrl"), ["item", "url"]);
	assert.deepEqual(tokens("getItem"), ["get", "item"]);
	assert.equal(classifyName("items/getItem", prefix).read, true);
	assert.equal(classifyName("files/itemUrl", prefix).read, false);
	assert.equal(classifyName("items/getOrCreate", prefix).read, false);
	assert.equal(classifyName("feed/listUpdates", prefix).read, true);
	assert.equal(action("POST", rpc("items/update"), prefix, "{}"), "abort");
	assert.equal(action("POST", rpc("items/list"), prefix), "continue");
});

test("methods and hosts", () => {
	assert.equal(action("POST", rpc("items/list"), { procedureStyle: "rest" }), "abort");
	for (const method of ["PUT", "PATCH", "DELETE"]) assert.equal(action(method, `${base}/api/x`), "abort", method);
	assert.equal(action("GET", `${base}/assets/app.js`), "continue");
	assert.equal(action("GET", "https://api.example.com/v1/x"), "abort");
	assert.equal(action("GET", "http://localhost.evil.example/x"), "abort");
	assert.equal(action("GET", "https://api.example.com/v1/x", { allowHosts: ["api.example.com"] }), "continue");
	assert.equal(action("OPTIONS", `${base}/api/x`), "continue");
	assert.equal(action("OPTIONS", "https://api.example.com/x"), "abort");
	assert.throws(() => decide({ method: "GET", url: base }, { procedureStyle: "x" }));
});

test("prove names every write a guard would let through", () => {
	const writes = [`POST ${rpc("items/update")}`, `PUT ${base}/api/x`, `POST ${rpc("items/list")}`];
	assert.equal(prove(writes, prefix).length, 1);
	assert.equal(prove(writes, { readProcedures: ["users/me"] }).length, 0);
});

// A row prove cannot read is a write it never judged, so it fails the file instead of passing as blocked.
test("prove refuses a malformed row with its line number", () => {
	const { writes, bad } = parseWrites(["# copied from the network log", "", "POST", `PUT ${base}/api/x`, "DELETE /api/items/1"]);
	assert.deepEqual(writes.map((w) => [w.line, w.method]), [[4, "PUT"]]);
	assert.deepEqual(bad.map((b) => b.line), [3, 5]);
	assert.throws(() => prove(["POST"]), /line 1/);
	assert.throws(() => prove([]), /no write is listed/);
	assert.throws(() => prove(["# only a comment", ""]), /no write is listed/);
	const file = join(dir, "malformed.txt");
	writeFileSync(file, `POST ${rpc("items/update")}\nPOST\n`);
	const r = spawnSync(process.execPath, [GUARD, "prove", "--writes", file], { encoding: "utf8" });
	assert.equal(r.status, 2, r.stdout + r.stderr);
	assert.match(r.stderr, /line 2/);
	assert.doesNotMatch(r.stdout, /blocked/);
});

test("GraphQL is judged by its body, never by its path", () => {
	const gq = `${base}/graphql`;
	const body = (query, operationName) => JSON.stringify({ query, operationName, variables: {} });
	const mutation = body("mutation UpdateItem($id: ID!) { updateItem(id: $id) { id } }", "UpdateItem");
	const query = body("query ListItems { items { id } }", "ListItems");
	assert.equal(action("POST", gq, { readProcedures: ["graphql"] }, mutation), "abort");
	assert.equal(action("POST", gq, { readProcedures: ["UpdateItem"] }, mutation), "abort");
	assert.equal(action("POST", gq, { readProcedures: ["ListItems"] }, query), "continue");
	assert.equal(action("POST", gq, {}, query), "abort");
	assert.equal(action("POST", gq, prefix, query), "continue");
	assert.equal(action("POST", gq, { readProcedures: ["graphql"] }, body("{ items { id } }")), "abort");
	assert.equal(action("POST", gq, { readProcedures: ["ListItems"] }, `[${query},${mutation}]`), "abort");
	assert.deepEqual(graphqlOps('query Q($f: In = {a: "}"}) { a } # mutation X { b }\nfragment F on T { c }'), [{ type: "query", name: "Q" }]);
	assert.equal(action("POST", gq, { readProcedures: ["ListItems", "UpdateItem"] }, body("query ListItems { a } mutation UpdateItem { b }", "UpdateItem")), "abort");
	assert.equal(action("POST", gq, { readProcedures: ["ListItems"] }, JSON.stringify({ operationName: "ListItems", extensions: {} })), "continue");
	assert.equal(action("POST", gq, prefix, JSON.stringify({ operationName: "UpdateItem" })), "abort");
	assert.equal(action("POST", gq, { readProcedures: ["graphql"] }, "x"), "abort");
	assert.equal(action("POST", gq, { fixtures: { UpdateItem: { body: {} } } }, mutation), "fulfill");
	assert.equal(action("GET", `${gq}?query=${encodeURIComponent("mutation { deleteItem(id: 1) }")}`), "abort");
	assert.equal(isGraphqlPath(`${base}/api/data`, { graphqlPaths: ["/api/data"] }), true);
	assert.equal(action("POST", `${base}/api/data`, { readProcedures: ["data"], graphqlPaths: ["/api/data"] }, mutation), "abort");
	assert.equal(action("POST", `${base}/api/data`, { readProcedures: ["data"] }, mutation), "continue");
	assert.equal(prove([`POST ${gq} ${mutation}`], { readProcedures: ["graphql"] }).length, 0);
	assert.equal(prove([`POST ${gq} ${query}`], { readProcedures: ["ListItems"] }).length, 1);
	assert.equal(graphqlProc({ method: "POST", url: gq, postData: '{"query":"mutation UpdateItem { a }"}' }), "graphql/UpdateItem");
});

/** A stand-in for a Playwright page: route() stores the handler, fire() sends one request through it. */
function fakePage() {
	const calls = [];
	let handler;
	return {
		calls,
		async route(_pattern, h) { handler = h; },
		async close() { calls.push("page.close"); },
		async fire(method, url, postData) {
			await handler({
				request: () => ({ method: () => method, url: () => url, postData: () => postData }),
				fulfill: async () => calls.push(`fulfill:${url}`),
				continue: async () => calls.push(`continue:${url}`),
				abort: async () => calls.push(`abort:${url}`),
			});
		},
	};
}

const readLog = (file) => readFileSync(file, "utf8").trim().split("\n").map((l) => JSON.parse(l));

test("installGuard aborts writes, aborts held routes before the page closes, and logs each decision", async () => {
	const logFile = join(dir, "held.log");
	const page = fakePage();
	const guard = installGuard(page, { logFile, hold: ["items/create", "items/list"], fixtures: { "users/me": { body: { id: "u1" } } } });
	await guard.ready;
	await page.fire("GET", `${base}/`);
	await page.fire("POST", rpc("users/me"));
	await page.fire("POST", rpc("items/create"), "{}");
	await page.fire("POST", rpc("items/list"));
	await page.fire("POST", rpc("items/update"), '{"id":1}');
	await page.fire("GET", "https://example.com/pixel.gif");
	assert.equal(guard.heldCount(), 2);
	await guard.closePage(page);
	const closeAt = page.calls.indexOf("page.close");
	assert.ok(page.calls.indexOf(`abort:${rpc("items/create")}`) > -1 && page.calls.indexOf(`abort:${rpc("items/create")}`) < closeAt, page.calls.join(" | "));
	assert.ok(page.calls.includes(`abort:${rpc("items/list")}`) && !page.calls.includes(`continue:${rpc("items/list")}`));
	assert.ok(page.calls.includes(`abort:${rpc("items/update")}`) && !page.calls.includes(`continue:${rpc("items/update")}`));
	assert.ok(page.calls.includes("abort:https://example.com/pixel.gif"));
	assert.ok(page.calls.includes(`fulfill:${rpc("users/me")}`));
	const lines = readLog(logFile);
	assert.ok(lines.length >= 8 && lines.every((l) => l.action && l.url && l.t), JSON.stringify(lines));
});

// A request body can carry personal data or a token, so the log keeps it only on request.
test("installGuard leaves request bodies out of the log by default", async () => {
	const logFile = join(dir, "default.log");
	const page = fakePage();
	await installGuard(page, { logFile }).ready;
	await page.fire("POST", rpc("items/update"), '{"id":1,"count":2}');
	await page.fire("PUT", `${base}/api/items/1`, '{"count":3}');
	const lines = readLog(logFile);
	assert.equal(lines.length, 2);
	assert.ok(lines.every((l) => l.action === "abort" && !("body" in l)), JSON.stringify(lines));
});

test("installGuard keeps each write's body when logBodies is on, and never a GET's", async () => {
	const logFile = join(dir, "bodies.log");
	const page = fakePage();
	const guard = installGuard(page, { logFile, logBodies: true });
	await guard.ready;
	await page.fire("GET", `${base}/api/items`);
	await page.fire("POST", rpc("items/update"), '{"id":1,"count":2}');
	const lines = readLog(logFile);
	assert.ok(lines.some((l) => l.action === "abort" && /items\/update/.test(l.url) && l.body === '{"id":1,"count":2}'), JSON.stringify(lines));
	assert.ok(lines.filter((l) => l.method === "GET").every((l) => !("body" in l)));
	assert.deepEqual(guard.log, lines);
});
