#!/usr/bin/env node
// capture-guard.mjs: deny-by-default guard for the HTTP requests a Playwright page or context routes.
// Node 18+, no dependencies. Works as a module (installGuard, decide, classifyName) and as a CLI.
// Adapted from design.how skills/build-design-system/scripts (MIT, see ../LICENSE.design-how).
import { appendFileSync, readFileSync, realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

const HELP = `capture-guard.mjs: deny-by-default network guard for browser capture scripts

Usage
  node capture-guard.mjs names <procedure>... [--procedure-style rpc-post|rest] [--read-procedures a,b] [--read-verbs ...]
      Prints read or deny for each procedure name. Run it on the app's real procedure list before a capture.
  node capture-guard.mjs decide --method POST --url <url> [--body <text>] [--fixtures <json>] [options]
      Prints the decision as JSON: {action: fulfill|continue|abort, reason}.
  node capture-guard.mjs prove --writes <file> [options]
      The dry run before any run that can reach a backend. It checks the guard's decision on each request the
      file lists, and only on those. Each line is "METHOD URL" for a write the app really sends, copied from its
      network log in the shape it has there, or "METHOD URL BODY" when the endpoint is GraphQL, with the request
      body as one line of JSON. Blank lines and lines starting with # are skipped. Exits 1 if any one would
      continue, 2 if a line has no method and absolute URL (each is named by its line number).
      Pass the same options the capture uses. Then fire the same writes from the page and read guard.log.
  node capture-guard.mjs --help

Options (CLI and the opts object of decide and installGuard)
  --procedure-style <s>   rpc-post (default) or rest. Many RPC styles send reads as POST, so
                          "abort every non-GET" blocks the app. rest allows GET/HEAD only.
  --app-origin <url>      repeatable. Origins that serve the app and its assets. Default: any local host.
  --allow-host <host>     repeatable. A non-local host that may be reached (almost never right).
  --read-procedures <a,b> exact procedure names (items/list) that continue. By default only these do.
                          For GraphQL these are operation names (ListItems), never the endpoint itself.
  --graphql <path>        repeatable. A path that serves GraphQL. Any path whose last segment is graphql or gql
                          already counts. Its bodies are read: see rule 5.
  --read-verbs <a,b>      opt in to prefix matching: a POST whose name starts with one of these verbs also
                          continues. "default" means ${"get,list,me,find,search,read,check,preview,count"}. A name like
                          getOrCreate can write, so prefer exact names for any run that reaches a real backend.
  --fixtures <json>       {"<procedure or last segment>": {"status":200,"body":{...}}}. Matched calls are
                          fulfilled in the browser and never reach the backend, whatever the method.

installGuard only (opts object)
  logFile                 JSON lines, one per decision (capture.mjs writes it as guard.log).
  logBodies               true to keep the request body of every request that is not GET, HEAD or OPTIONS in the
                          log. Off by default, because a body can carry personal data or a token. Turn it on only
                          to compare request bodies between two captures.
  hold                    procedure names to leave unanswered, to capture a pending state. releaseAll() aborts
                          them before the page closes.

Scope
  The guard sees only the HTTP requests Playwright routes for the page or context it is installed on.
  capture.mjs installs it on every browser context before the first navigation. A script of your own does
  the same: await installGuard(context, opts).ready, then navigate. Create the context with
  serviceWorkers: "block", because a service worker's requests go around page and context routes.
  Outside the guard: WebSocket traffic (never routed, so an app that writes over one is not guarded), any
  request a script sends from Node rather than the page, such as capture.mjs's route status check (a GET), and
  every hop after a redirect. Playwright calls the route handler only for a request's first URL
  (https://playwright.dev/docs/api/class-page#page-route), so a request the guard continues, such as a listed
  POST read, that is answered 307 or 308 is sent again with its body to the Location, which the guard never judges.
  Point captures at a local build with fixed data or state you can throw away.

Rules
  1. A host that is not local is aborted, unless --allow-host names it.
  2. A fixture match is fulfilled. A GraphQL operation matches a fixture by its operation name.
  3. GET and HEAD to the app origin continue (documents, assets, GET reads). A GET to a GraphQL path whose
     query parameter holds a mutation or subscription is aborted.
  4. In rpc-post style a POST continues only when --read-procedures lists it. With --read-verbs, it also
     continues when the last path segment, split into tokens on / . - _ and camelCase boundaries, starts
     with a read verb and holds no write token. Anything else is aborted, and the reason names the two
     ways out: add a fixture or list the procedure in --read-procedures.
  5. A POST to a GraphQL path is judged by its body, never by its path. Every operation in it (a batch is a
     JSON array) must be a query whose operation name passes rule 4. A mutation or subscription is aborted
     even when its name is listed. A persisted query with no query text continues only when its name is
     listed exactly. A body that is not JSON is aborted.
  6. OPTIONS to a local host continues. It is the CORS preflight a browser sends before a cross-origin read,
     it carries no body, and the request it precedes is judged on its own. Set no fixture on it.
  7. PUT, PATCH, DELETE and every other method are aborted.
  8. A write is never continued. Held routes are aborted by releaseAll() before the page closes.
  A GET that writes (a logout or unsubscribe link) passes rule 3. List it in the prove file, which then fails,
  and answer it with a fixture.`;

export const PREFIX_READ_VERBS = ["get", "list", "me", "find", "search", "read", "check", "preview", "count"];
export const WRITE_TOKENS = ["create", "update", "delete", "remove", "set", "modify", "add", "send", "submit", "upload", "invite", "approve", "reject", "cancel", "save", "write", "publish", "revoke", "archive", "restore", "grant", "execute", "mutate", "patch", "put", "post", "import", "reset", "confirm", "accept", "decline", "assign", "move", "merge", "enable", "disable", "toggle", "sync", "start", "stop", "trigger"];
const ASSET_EXT = /\.(js|mjs|css|map|png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|otf|json|html|txt|wasm)$/i;

export function tokens(name) {
	return String(name)
		.replace(/([a-z0-9])([A-Z])/g, "$1 $2")
		.replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
		.split(/[\s/._\-]+/)
		.filter(Boolean)
		.map((t) => t.toLowerCase());
}

export function lastSegment(procOrPath) {
	const parts = String(procOrPath).split("/").filter(Boolean);
	return parts[parts.length - 1] || "";
}

// Judges one procedure name. Exact names only, unless readVerbs opts in to prefix matching: then the first
// token must be a read verb and no later token may be a write token.
export function classifyName(name, opts = {}) {
	const verbs = (opts.readVerbs || []).filter(Boolean);
	const exact = opts.readProcedures || [];
	if (exact.includes(name) || exact.includes(lastSegment(name))) return { read: true, why: "listed in readProcedures" };
	if (!verbs.length) return { read: false, why: "not listed in readProcedures" };
	const t = tokens(lastSegment(name));
	if (!t.length) return { read: false, why: "empty name" };
	if (!verbs.includes(t[0])) return { read: false, why: `first token "${t[0]}" is not a read verb` };
	const w = t.slice(1).find((x) => WRITE_TOKENS.includes(x));
	if (w) return { read: false, why: `read verb "${t[0]}" followed by write token "${w}"` };
	return { read: true, why: `read verb "${t[0]}"` };
}

export function isLocalHost(host) {
	const h = String(host).replace(/^\[|\]$/g, "").toLowerCase();
	return h === "localhost" || h === "127.0.0.1" || h === "::1" || h.endsWith(".localhost");
}

export function procedureOf(url) {
	let u;
	try { u = new URL(url); } catch { return ""; }
	return u.pathname.split("/").filter(Boolean).slice(-2).join("/");
}

export function isGraphqlPath(url, opts = {}) {
	let path;
	try { path = new URL(url).pathname; } catch { return false; }
	if ((opts.graphqlPaths || []).some((p) => path === p || path.endsWith(p))) return true;
	return /^(graphql|gql)$/i.test(lastSegment(path));
}

// The operations a GraphQL document defines, as [{type, name}], read at the top level only. Strings, block
// strings and comments are skipped, and braces inside variable definitions do not open a selection set.
export function graphqlOps(text) {
	const ops = [];
	let depth = 0, parens = 0, pending = null, i = 0;
	const src = String(text);
	while (i < src.length) {
		const c = src[i];
		if (c === "#") { while (i < src.length && src[i] !== "\n") i++; continue; }
		if (c === '"') {
			if (src.startsWith('"""', i)) { const e = src.indexOf('"""', i + 3); i = e < 0 ? src.length : e + 3; continue; }
			i++;
			while (i < src.length && src[i] !== '"') i += src[i] === "\\" ? 2 : 1;
			i++;
			continue;
		}
		if (c === "(") { parens++; i++; continue; }
		if (c === ")") { parens--; i++; continue; }
		if (c === "{" && parens === 0) {
			if (depth === 0) { ops.push(pending || { type: "query", name: null }); pending = null; }
			depth++; i++; continue;
		}
		if (c === "}" && parens === 0) { depth--; i++; continue; }
		if (depth === 0 && parens === 0 && /[_A-Za-z]/.test(c)) {
			let j = i;
			while (j < src.length && /\w/.test(src[j])) j++;
			const word = src.slice(i, j);
			if (!pending && ["query", "mutation", "subscription", "fragment"].includes(word)) pending = { type: word, name: null, named: false };
			else if (pending && !pending.named) { pending.name = word; pending.named = true; }
			i = j;
			continue;
		}
		i++;
	}
	return ops.filter((o) => o.type !== "fragment").map(({ type, name }) => ({ type, name }));
}

// Judges one GraphQL request ({query, operationName}) for rules 4 and 5. {read, name, why}.
export function judgeGraphql(one, opts = {}) {
	if (!one || typeof one !== "object") return { read: false, name: "", why: "a GraphQL body that is not an object" };
	const exact = opts.readProcedures || [];
	const named = typeof one.operationName === "string" && one.operationName ? one.operationName : null;
	if (typeof one.query !== "string" || !one.query.trim()) {
		if (named && exact.includes(named)) return { read: true, name: named, why: "persisted query listed by name in readProcedures" };
		return { read: false, name: named || "", why: "a persisted query with no query text continues only when its name is listed exactly" };
	}
	const ops = graphqlOps(one.query);
	const op = named ? ops.find((o) => o.name === named) : ops.length === 1 ? ops[0] : null;
	if (!op) return { read: false, name: named || "", why: ops.length ? "several operations and no operationName picks one" : "no operation in the query" };
	const name = named || op.name || "";
	if (op.type !== "query") return { read: false, name, why: `GraphQL ${op.type} ${name || "(anonymous)"}` };
	if (!name) return { read: false, name, why: "an anonymous query has no name to list" };
	const c = classifyName(name, opts);
	return { read: c.read, name, why: `query ${name}: ${c.why}` };
}

// The name a GraphQL request is logged and grouped under: graphql/<operation names>, so bodies compare per operation.
export function graphqlProc(req) {
	let list = [];
	try {
		if (String(req.method).toUpperCase() === "GET") list = [{ operationName: new URL(req.url).searchParams.get("operationName"), query: new URL(req.url).searchParams.get("query") }];
		else { const b = JSON.parse(req.postData ?? ""); list = Array.isArray(b) ? b : [b]; }
	} catch { return procedureOf(req.url); }
	const names = list.map((one) => one?.operationName || (typeof one?.query === "string" ? graphqlOps(one.query)[0]?.name : null) || "anonymous");
	return `graphql/${names.join(",")}`;
}

function findFixture(fixtures, url) {
	if (!fixtures) return null;
	let path;
	try { path = new URL(url).pathname; } catch { return null; }
	const segs = path.split("/").filter(Boolean);
	const keys = [segs.slice(-2).join("/"), segs[segs.length - 1], path];
	for (const k of keys) if (k && Object.prototype.hasOwnProperty.call(fixtures, k)) return { key: k, fx: fixtures[k] };
	return null;
}

// Pure. {method, url, postData} in, {action, reason, response?} out.
export function decide(req, opts = {}) {
	const style = opts.procedureStyle || "rpc-post";
	if (!["rpc-post", "rest"].includes(style)) throw new Error(`procedureStyle must be rpc-post or rest, got ${style}`);
	const method = String(req.method || "GET").toUpperCase();
	let u;
	try { u = new URL(req.url); } catch { return { action: "abort", reason: "unparseable url" }; }
	if (["data:", "blob:", "about:"].includes(u.protocol)) return { action: "continue", reason: `${u.protocol} is not network` };
	const allowed = (opts.allowHosts || []).map((h) => h.toLowerCase());
	if (!isLocalHost(u.hostname) && !allowed.includes(u.hostname.toLowerCase()))
		return { action: "abort", reason: `non-local host ${u.hostname}` };
	if (opts.appOrigins?.length && !opts.appOrigins.includes(u.origin) && !allowed.includes(u.hostname.toLowerCase()))
		return { action: "abort", reason: `origin ${u.origin} is not an app origin` };
	const fulfill = (key, fx) => ({ action: "fulfill", reason: `fixture ${key}`, response: { status: fx.status ?? 200, contentType: fx.contentType || "application/json", body: typeof fx.body === "string" ? fx.body : JSON.stringify(fx.body ?? null) } });
	if (method === "OPTIONS") return { action: "continue", reason: "CORS preflight to a local host (rule 6)" };
	const gql = isGraphqlPath(req.url, opts);
	const hit = findFixture(opts.fixtures, req.url);
	if (hit) return fulfill(hit.key, hit.fx);
	if (gql && (method === "GET" || method === "POST")) {
		let list;
		if (method === "GET") {
			const q = u.searchParams.get("query");
			if (!q) return { action: "continue", reason: "GET to a GraphQL path with no query" };
			list = [{ query: q, operationName: u.searchParams.get("operationName") || undefined }];
		} else {
			try { const b = JSON.parse(req.postData ?? ""); list = Array.isArray(b) ? b : [b]; } catch { return { action: "abort", reason: "a GraphQL POST whose body is not JSON" }; }
			if (!list.length) return { action: "abort", reason: "an empty GraphQL batch" };
		}
		const judged = list.map((one) => judgeGraphql(one, opts));
		const fx = opts.fixtures || {};
		if (judged.length === 1 && judged[0].name && Object.prototype.hasOwnProperty.call(fx, judged[0].name)) return fulfill(judged[0].name, fx[judged[0].name]);
		const bad = judged.find((j) => !j.read);
		if (method === "GET" && (!bad || !/mutation|subscription/.test(bad.why))) return { action: "continue", reason: "GET to a GraphQL path with a query" };
		if (bad) return { action: "abort", reason: `deny ${bad.why}. Fixture it by operation name or list the query in readProcedures` };
		return { action: "continue", reason: `read ${judged.map((j) => j.why).join("; ")}` };
	}
	if (method === "GET" || method === "HEAD") return { action: "continue", reason: "GET to a local host" };
	if (method === "POST") {
		const proc = procedureOf(req.url);
		const exact = opts.readProcedures || [];
		if (style === "rest" && !(exact.includes(proc) || exact.includes(lastSegment(proc))))
			return { action: "abort", reason: `POST ${proc} in rest style; fixture it or list it in readProcedures` };
		if (ASSET_EXT.test(u.pathname)) return { action: "abort", reason: "POST to an asset path" };
		const c = classifyName(proc, opts);
		if (c.read) return { action: "continue", reason: `read ${proc}: ${c.why}` };
		return { action: "abort", reason: `deny ${proc}: ${c.why}. Fixture it or list it in readProcedures if it is a read` };
	}
	return { action: "abort", reason: `${method} is never continued` };
}

// target: a Playwright Page or BrowserContext, or anything with route(pattern, handler).
// The handler's route object needs request() with method(), url(), postData(), and fulfill, continue, abort.
// Pure. The lines of a writes file in, {writes: [{line, method, url, body}], bad: [{line, why}]} out, with
// 1-based line numbers. Blank lines and lines starting with # are skipped; any other line must be
// "METHOD URL" or "METHOD URL BODY" with an absolute URL, or it is bad.
export function parseWrites(lines) {
	const writes = [], bad = [];
	lines.forEach((text, i) => {
		const line = i + 1;
		if (!text.trim() || text.trimStart().startsWith("#")) return;
		const m = /^\s*(\S+)\s+(\S+)(?:\s+(.+?))?\s*$/.exec(text);
		if (!m) return bad.push({ line, why: "needs METHOD URL" });
		const [, method, url, body] = m;
		if (!/^[A-Za-z]+$/.test(method)) return bad.push({ line, why: "the method is not an HTTP method" });
		try { new URL(url); } catch { return bad.push({ line, why: "the URL is not absolute" }); }
		writes.push({ line, method: method.toUpperCase(), url, body });
	});
	return { writes, bad };
}

// Pure. The lines of a writes file in, the ones a guard with these options would let through out.
// A third field is the request body, for an endpoint judged by its body (GraphQL). Throws on a bad line, because
// a line it cannot read is a write it never judged.
export function prove(lines, opts = {}) {
	const { writes, bad } = parseWrites(lines);
	// A GraphQL POST is judged by its body, so a row without one would read as blocked and prove nothing.
	for (const w of writes) if (w.method === "POST" && !w.body && isGraphqlPath(w.url, opts)) bad.push({ line: w.line, why: "a GraphQL POST needs its body" });
	bad.sort((a, b) => a.line - b.line);
	// Reasons only: a row can carry a request body, which is not printed unless --bodies asks for it.
	if (bad.length) throw new Error(bad.map((b) => `line ${b.line}: ${b.why}`).join("\n"));
	// An empty list proves nothing; a surface that sends no writes is captured with --no-backend instead.
	if (!writes.length) throw new Error("no write is listed, so nothing was judged; list the surface's writes, or capture with --no-backend if it sends none");
	return writes.map(({ method, url, body }) => ({ method, url, ...decide({ method, url, postData: body }, opts) })).filter((d) => d.action === "continue");
}

export function installGuard(target, opts = {}) {
	const log = [];
	const held = new Set();
	const holdNames = opts.hold || [];
	const record = (entry, body) => {
		const line = { t: new Date().toISOString(), ...entry };
		if (opts.logBodies && !["GET", "HEAD", "OPTIONS"].includes(String(entry.method).toUpperCase())) line.body = body ?? "";
		log.push(line);
		if (opts.logFile) appendFileSync(opts.logFile, JSON.stringify(line) + "\n");
	};
	const handler = async (route) => {
		const r = route.request();
		const req = { method: r.method(), url: r.url(), postData: r.postData ? r.postData() : undefined };
		const d = decide(req, opts);
		const proc = isGraphqlPath(req.url, opts) ? graphqlProc(req) : procedureOf(req.url);
		const wantsHold = holdNames.some((h) => h === proc || h === lastSegment(proc));
		if (wantsHold) {
			held.add(route);
			return record({ method: req.method, url: req.url, proc, action: "hold", reason: `held (${d.reason}); aborted by releaseAll` }, req.postData);
		}
		record({ method: req.method, url: req.url, proc, action: d.action, reason: d.reason }, req.postData);
		try {
			if (d.action === "fulfill") await route.fulfill(d.response);
			else if (d.action === "continue") await route.continue();
			else await route.abort();
		} catch (e) {
			record({ method: req.method, url: req.url, proc, action: "error", reason: String(e.message || e) }, req.postData);
		}
	};
	const ready = target.route(opts.pattern || "**/*", handler);
	return {
		ready,
		log,
		heldCount: () => held.size,
		// Aborts every held route. Call it before page.close(); a route released after close can still reach the backend.
		async releaseAll() {
			const routes = [...held];
			held.clear();
			for (const route of routes) {
				const r = route.request();
				record({ method: r.method(), url: r.url(), proc: procedureOf(r.url()), action: "abort", reason: "held route aborted at release" });
				try { await route.abort(); } catch { /* page already gone */ }
			}
			return routes.length;
		},
		async closePage(page) {
			await this.releaseAll();
			await page.close();
		},
	};
}

// ---- CLI ----
// The installer links the skill folder into place, so the path the script was started by can be a link. A first
// argument that is not a file (`node --input-type=module -`) means this module was imported, not run.
function isMain() {
	try { return !!process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url)); }
	catch { return false; }
}
function parse(argv) {
	const o = { _: [], appOrigins: [], allowHosts: [], graphqlPaths: [] };
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		const next = () => argv[++i];
		if (a === "--procedure-style") o.procedureStyle = next();
		else if (a === "--app-origin") o.appOrigins.push(next());
		else if (a === "--allow-host") o.allowHosts.push(next());
		else if (a === "--graphql") o.graphqlPaths.push(next());
		else if (a === "--read-verbs") { const v = next(); o.readVerbs = v === "default" ? PREFIX_READ_VERBS : v.split(","); }
		else if (a === "--read-procedures") o.readProcedures = next().split(",");
		else if (a === "--fixtures") o.fixtures = JSON.parse(readFileSync(next(), "utf8"));
		else if (a === "--method") o.method = next();
		else if (a === "--url") o.url = next();
		else if (a === "--body") o.body = next();
		else if (a === "--writes") o.writes = next();
		else if (a === "--help" || a === "-h") o.help = true;
		else if (a.startsWith("-")) { console.error(`capture-guard: unknown flag ${a}. See --help`); process.exit(2); }
		else o._.push(a);
	}
	return o;
}

if (isMain()) {
	const o = parse(process.argv.slice(2));
	if (o.help) console.log(HELP);
	else if (o._[0] === "names") {
		for (const n of o._.slice(1)) {
			const c = classifyName(n, o);
			console.log(`${c.read ? "read" : "deny"}\t${n}\t${c.why}`);
		}
	} else if (o._[0] === "decide") {
		if (!o.url) { console.error("decide needs --url"); process.exit(2); }
		console.log(JSON.stringify(decide({ method: o.method || "GET", url: o.url, postData: o.body }, o)));
	} else if (o._[0] === "prove") {
		if (!o.writes) { console.error("prove needs --writes <file>"); process.exit(2); }
		let leaks;
		try { leaks = prove(readFileSync(o.writes, "utf8").split("\n"), o); }
		catch (e) { console.error(`capture-guard: ${o.writes} has lines prove cannot read, so nothing was judged:\n${e.message}`); process.exit(2); }
		for (const l of leaks) console.log(`LEAK\t${l.method} ${l.url}\t${l.reason}`);
		console.log(leaks.length ? `${leaks.length} writes would reach the backend` : "every listed write is blocked");
		process.exitCode = leaks.length ? 1 : 0;
	} else { console.error("usage: capture-guard.mjs names|decide|prove|--help"); process.exit(2); }
}
