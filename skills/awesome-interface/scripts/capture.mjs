#!/usr/bin/env node
// capture.mjs: screenshots of every route, width, theme and state, behind capture-guard. Node 18+, Playwright 1.49+.
// Run `node capture.mjs --help` for usage. Tests: capture.test.mjs.
// Adapted from design.how skills/build-design-system/scripts (MIT, see ../LICENSE.design-how).
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { launchChromium, repoRoot } from "./find-chromium.mjs";
import { installGuard, isLocalHost, parseWrites, prove } from "./capture-guard.mjs";

const HELP = `capture.mjs: screenshots and accessibility trees for every route, width and theme, with page writes blocked

Usage
  node capture.mjs --base <url> --kind before|after --out <folder> (--routes <r>... | --surfaces <tsv>)
                   (--writes <file> | --no-backend) [options]
  node capture.mjs --base <url> --status (--routes <r>... | --surfaces <tsv>)
  node capture.mjs --help

  Example, with the app served on port 3000 and the captures kept outside the checkout:
  node capture.mjs --base http://localhost:3000 --kind before --out /tmp/ui-review/captures \\
    --surfaces /tmp/ui-review/surfaces.tsv --writes /tmp/ui-review/writes.txt

Routes
  --routes <r>...      each a path (/settings/profile) or surface=path (profile=/settings/profile), separated by
                       spaces or commas. The surface name defaults to the path as a slug, without its query or
                       hash: / is home. Routes that would share file names are refused. Load state only
  --surfaces <tsv>     a TSV with a header row holding surface and route (or path or url), and optionally states
                       (comma separated) and status (the HTTP code the route should answer, 200 when blank).
                       It is the only way to capture states
  --expect-status <s=code>...  a surface or route that should answer another code, such as notfound=404

Files, in --out
  <surface>-<kind>-<width>.png              the page as it loads, first theme
  <surface>-<kind>-<width>-<theme>.png      the other themes
  <surface>.<state>-<kind>-<width>.png      a listed state other than the load state
  ...same name with .aria.yml               the accessibility tree (roles, names, states). Diff before and after
  ...same name with .<audit>.json           what each --eval script returned
  guard.log                                 one JSON line per network decision. Request bodies only with --bodies

The guard (capture-guard.mjs) is installed on the browser context before the first navigation. For every HTTP
request Playwright routes there, it aborts every non-local host, every PUT, PATCH and DELETE, and every POST not
listed as a read. Service workers are blocked so their requests cannot go around the context route.
Outside the guard: WebSocket traffic, so an app that writes over one is not safe to capture live; the route
status check below, a plain GET from Node before any browser opens; and every hop after a redirect, because
Playwright calls the route handler only for a request's first URL. A request the guard continues, such as a
listed POST read, that is answered 307 or 308 is sent again with its body to the Location, unjudged. A GET that
writes (a logout link) is continued like any GET. Capture a local build with fixed data or state you can throw away.
A capture needs one of these two, so no run starts before the guard's decision on its writes is checked:
  --writes <file>      lines of "METHOD URL", every write the app sends, copied from its network log ("METHOD URL
                       BODY" for GraphQL). capture runs capture-guard prove on them first, which checks the
                       guard's decision on each listed request and nothing more, and exits 2 before opening a
                       browser if any one would get through or a line is not METHOD URL
  --no-backend         the app sends no writes (a static site, or every call answered by --guard-fixtures). Skips
                       the --writes dry run and nothing else: the guard's configured rules stay in effect, and
                       one WARN line summarizes the blocked requests whose method is not GET, HEAD or OPTIONS
  --read-procedures <a,b>  exact POST procedure names, or GraphQL operation names, that are reads and may continue
  --procedure-style <s>    rpc-post (default) or rest
  --graphql <path>...      a path that serves GraphQL, beyond any ending in /graphql or /gql
  --guard-fixtures <json>  {"<procedure>": {"status": 200, "body": {...}}}, answered in the browser
  --app-origin <url>...    origins that serve the app. Default: any local host
  --allow-host <host>...   a non-local host the page may reach. A non-local --base is refused unless named here

Request bodies are not recorded by default, because a body can carry personal data or a token.
  --bodies <file>      record the body of every write the page sent, blocked or not, in guard.log, and write
                       {"rows": [{method, url, proc, body, action}]} to <file>, in the order sent. A GraphQL
                       row's proc is graphql/<operation name>. Use it only to compare request bodies: run the
                       same states before and after, each with its own --bodies file, and diff the two

Options
  --root <dir>         the app's repo root, where Playwright is looked for first. Default: the git root of --out,
                       else of the current folder, else the current folder
  --widths 390,1280    viewport widths: the narrowest and widest the app supports
  --height 900         viewport height. 320 at --widths 390 shows overlays that run past a short screen
  --themes light,dark  the first is the default theme. Default: light
  --theme-via <how>    media (prefers-color-scheme, default), class (toggles .dark on <html>) or storage:<key>
                       (sets localStorage <key> before load). media is what a dark OS does
  --states <file.mjs>  a module whose default export maps a state name, or surface.state, to async (page) => {}
                       that reaches it. A listed state with no function is not captured, which fails the run
  --eval <file.js>...  in-page audit scripts. What each returns is written as JSON beside the screenshot
  --full               full-page screenshots (default: the viewport)
  --mobile             isMobile and hasTouch on, for a review of a phone
  --storage-state <f>  a Playwright storage state the person provides, to reach signed-in screens. Never a real
                       account's session
  --no-aria            skip the accessibility trees
  --status             only request every route and print its HTTP status. Exit 1 unless each answers as expected.
                       Redirects are not followed: a 3xx is reported with its Location and fails unless
                       --expect-status or the status column names that code

It requests every route first (the status check, outside the guard) and exits 1 if any answers other than
expected, after capturing the rest. The
clock is fixed, Math.random is seeded, reduced motion is on, lazy images load eagerly, and it waits for fonts
and, on a React app, for handlers to attach.
Exit 0 every planned capture written, 1 a route or capture failed or any capture is missing (each is listed),
2 bad input, a write that would get through, or no browser.`;

const die = (m) => { console.error(`capture: ${m}`); process.exit(2); };
const slug = (p) => p.replace(/[?#].*$/, "").replace(/^\/+|\/+$/g, "").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase() || "home";

async function main(argv) {
	if (!argv.length || argv.includes("--help") || argv.includes("-h")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
	const KNOWN = new Set(["--height", "--root", "--base", "--kind", "--out", "--routes", "--surfaces", "--widths", "--themes", "--theme-via", "--states", "--full", "--status", "--no-aria", "--expect-status", "--mobile", "--storage-state", "--eval", "--writes", "--read-procedures", "--procedure-style", "--guard-fixtures", "--app-origin", "--allow-host", "--no-backend", "--bodies", "--graphql"]);
	const bad = argv.filter((a) => a.startsWith("--") && !KNOWN.has(a));
	if (bad.length) die(`unknown ${bad.join(", ")}. See --help`);
	const val = (f, d) => { const i = argv.indexOf(f); return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : d; };
	const list = (f) => { const i = argv.indexOf(f); if (i < 0) return null; const out = []; for (let k = i + 1; k < argv.length && !argv[k].startsWith("--"); k++) out.push(argv[k]); return out; };

	const base = val("--base"); if (!base || !/^https?:\/\//.test(base)) die("--base <http://host:port> is required");
	const statusOnly = argv.includes("--status");
	const kind = val("--kind");
	const out = val("--out") && resolve(val("--out"));
	if (!statusOnly) {
		if (!/^(before|after)$/.test(kind || "")) die("--kind before or --kind after is required");
		if (!out) die("--out <folder> is required");
		if (!val("--writes") && !argv.includes("--no-backend")) die("give --writes <file> (every write the app sends, proven blocked before the browser opens) or --no-backend (the app sends none). See --help");
		if (val("--writes") && argv.includes("--no-backend")) die("give --writes or --no-backend, not both");
	}
	const bodiesFile = val("--bodies") && resolve(val("--bodies"));
	if (argv.includes("--bodies") && !bodiesFile) die("--bodies takes a file, such as /tmp/ui-review/bodies.before.json");
	if (bodiesFile && statusOnly) die("--bodies records request bodies from a capture, so it does not go with --status");
	const widths = val("--widths", "390,1280").split(",").map(Number);
	if (widths.some((w) => !w)) die("--widths takes numbers, such as 390,1280");
	const height = Number(val("--height", "900"));
	if (!height) die("--height takes a number, such as 320");
	const via = val("--theme-via", "media");
	if (!/^(media|class|storage:.+)$/.test(via)) die("--theme-via is media, class or storage:<key>");
	const aria = !argv.includes("--no-aria");
	const storageState = val("--storage-state") && resolve(val("--storage-state"));
	if (storageState && !existsSync(storageState)) die(`no storage state at ${storageState}`);
	const audits = (list("--eval") || []).flatMap((f) => f.split(",")).filter(Boolean).map((f) => {
		const p = resolve(f); if (!existsSync(p)) die(`--eval: no file at ${p}`);
		const n = p.split("/").pop().replace(/\.(m?js)$/, ""); if (n === "aria") die("--eval: a script named aria would overwrite the .aria files. Rename it");
		return { name: n, src: readFileSync(p, "utf8") };
	});

	let surfaces = [];
	const routeArgs = (list("--routes") || []).flatMap((r) => r.split(",")).map((r) => r.trim()).filter(Boolean);
	if (argv.includes("--routes") && !routeArgs.length) die("--routes needs one or more paths, such as --routes /,/settings/profile");
	if (routeArgs.length && val("--surfaces")) die("give --routes or --surfaces, not both");
	if (routeArgs.length && val("--states")) die("--states needs --surfaces, whose states column lists each surface's states");
	if (routeArgs.length) surfaces = routeArgs.map((r) => { const m = /^([\w-]+)=(\/.*)$/.exec(r); return m ? { surface: m[1], route: m[2], states: [] } : { surface: slug(r), route: r.startsWith("/") ? r : `/${r}`, states: [] }; });
	else if (val("--surfaces")) {
		const p = resolve(val("--surfaces")); if (!existsSync(p)) die(`no file at ${p}`);
		const rows = readFileSync(p, "utf8").split("\n").filter((l) => l.trim() && !l.startsWith("#")).map((l) => l.split("\t"));
		const head = rows.shift().map((h) => h.trim().toLowerCase());
		const col = (...n) => head.findIndex((h) => n.includes(h));
		const cs = col("surface"), cr = col("route", "path", "url"), ct = col("states"), cx = col("status", "expect");
		if (cs < 0 || cr < 0) die(`${p} needs a header row with surface and route columns`);
		surfaces = rows.map((r) => ({ surface: r[cs].trim(), route: r[cr].trim(), states: ct >= 0 ? (r[ct] || "").split(",").map((s) => s.trim()).filter((s) => s && s !== "-" && s !== "default") : [], expect: cx >= 0 && /^\d{3}$/.test((r[cx] || "").trim()) ? Number(r[cx].trim()) : 200 }));
	} else die("give --routes or --surfaces");
	for (const e of list("--expect-status") || []) {
		const m = /^(.+)=(\d{3})$/.exec(e); if (!m) die(`--expect-status takes surface=code, such as notfound=404, not ${e}`);
		const hit = surfaces.filter((s) => s.surface === m[1] || s.route === m[1]); if (!hit.length) die(`--expect-status: no surface or route ${m[1]}`);
		for (const s of hit) s.expect = Number(m[2]);
	}
	for (const s of surfaces) s.expect ??= 200;
	if (surfaces.some((s) => s.surface.includes("."))) die("a surface name may not contain a dot; the dot separates surface and state");
	const themes = val("--themes", "light").split(",");
	const name = (s, state, w, t) => `${s.surface}${state ? `.${state}` : ""}-${kind}-${w}${t === themes[0] ? "" : `-${t}`}`;
	// slug() drops the query and hash, so /items?id=1 and /items?id=2 would write the same files.
	if (!statusOnly) {
		const routesOf = new Map();
		for (const s of surfaces) for (const state of ["", ...s.states]) for (const w of widths) for (const t of themes) {
			const n = name(s, state, w, t);
			routesOf.set(n, [...(routesOf.get(n) || []), s.route]);
		}
		const clash = [...routesOf].filter(([, r]) => r.length > 1);
		if (clash.length) die(`${clash.length} planned capture name(s) would be written more than once, each capture overwriting the last: ${clash.map(([n, r]) => `${n} (${r.join(", ")})`).join("; ")}. Give each route its own surface name with surface=path, such as items-1=/items?id=1, or its own surface in --surfaces`);
	}

	// The guard's options, and the dry run that must come back clean before any browser opens.
	const host = new URL(base).hostname;
	const allowHosts = list("--allow-host") || [];
	// A non-local base once opened the guard to that host for every request. Only an explicit --allow-host does now.
	if (!isLocalHost(host) && !allowHosts.map((h) => h.toLowerCase()).includes(host.toLowerCase())) die(`--base ${host} is not a local host. Capture a local build, or name the host with --allow-host ${host} if every write to it is proven blocked`);
	const guardOpts = {
		procedureStyle: val("--procedure-style", "rpc-post"),
		readProcedures: (val("--read-procedures") || "").split(",").filter(Boolean),
		appOrigins: list("--app-origin") || [],
		allowHosts,
		graphqlPaths: list("--graphql") || [],
		fixtures: val("--guard-fixtures") ? JSON.parse(readFileSync(resolve(val("--guard-fixtures")), "utf8")) : undefined,
	};
	if (!["rpc-post", "rest"].includes(guardOpts.procedureStyle)) die("--procedure-style is rpc-post or rest");
	let proved = "--no-backend, so no dry run of the app's writes";
	if (val("--writes")) {
		const p = resolve(val("--writes")); if (!existsSync(p)) die(`no writes file at ${p}`);
		const lines = readFileSync(p, "utf8").split("\n");
		let leaks;
		try { leaks = prove(lines, guardOpts); } catch (e) { die(`${p} has lines prove cannot read, so nothing was judged or captured:\n${e.message}`); }
		const count = parseWrites(lines).writes.length;
		for (const l of leaks) console.log(`LEAK\t${l.method} ${l.url}\t${l.reason}`);
		if (leaks.length) die(`${leaks.length} of ${count} writes in ${p} would reach the backend. Fix the guard options; nothing was captured`);
		proved = `the guard blocks each of the ${count} requests in --writes (redirect hops are not judged)`;
	}

	// 1. Every route answers as expected. A type check passes a server/client break that only a request shows.
	const statuses = [];
	// Redirects are not followed, so a route that bounces to /login reads as the 3xx it is.
	for (const s of surfaces) {
		let code, where = "";
		try {
			const res = await fetch(new URL(s.route, base), { redirect: "manual" });
			code = res.status;
			if (code >= 300 && code < 400) where = ` -> ${res.headers.get("location") || "(no Location)"}`;
		} catch (e) { code = `no answer (${e.cause?.code || e.message})`; }
		statuses.push([s, code]);
		console.log(`${code === s.expect ? code : "FAIL"}\t${s.route}\t${code}${where}${s.expect !== 200 ? ` (expected ${s.expect})` : ""}`);
	}
	const off = statuses.filter(([s, c]) => c !== s.expect);
	if (statusOnly) { console.log(`${statuses.length} route(s), ${off.length} not as expected`); process.exit(off.length ? 1 : 0); }
	mkdirSync(out, { recursive: true });

	const FREEZE = `(() => { let s = 42; Math.random = () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; }; })();`;
	const HYDRATED = `new Promise((ok) => { const t0 = Date.now(); const tick = () => { const el = document.querySelector("button, a[href], input, select, textarea, [role=button]"); const ready = !el || Object.keys(el).some((k) => k.startsWith("__reactProps") || k.startsWith("__reactFiber")) || !document.querySelector("#__next, [data-reactroot], script[src*='_next']"); if (ready || Date.now() - t0 > 5000) ok(ready); else setTimeout(tick, 50); }; tick(); })`;
	const SETTLE = `(async () => { for (const i of document.querySelectorAll("img[loading=lazy]")) i.loading = "eager"; await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; setTimeout(r, 3000); }))); await document.fonts.ready; document.getAnimations().forEach((a) => { try { a.finish(); } catch {} }); return true; })()`;
	const themeClass = (t) => `document.documentElement.classList.toggle("dark", ${JSON.stringify(t)} === "dark"); document.documentElement.style.colorScheme = ${JSON.stringify(t)};`;
	if (via !== "media" && themes.length > 1) console.error(`capture: --theme-via ${via} sets the theme by hand. It proves the tokens, not that a dark OS reaches them`);
	const written = [], missed = [];
	let evals = 0, trees = 0, blocked = 0;

	const launched = await launchChromium({}, { root: repoRoot(val("--root"), out) });
	if (launched.error) die(launched.error);
	const browser = launched.browser;
	console.error(`capture: ${launched.from}, ${launched.how}`);
	let steps = {};
	if (val("--states")) { const m = await import(pathToFileURL(resolve(val("--states"))).href); steps = m.default || m; }
	const logFile = join(out, "guard.log");
	writeFileSync(logFile, "");
	for (const [s, code] of statuses) {
		if (code !== s.expect) { missed.push(`${s.surface}: HTTP ${code}`); continue; }
		for (const t of themes) for (const w of widths) for (const state of ["", ...s.states]) {
			const step = state ? steps[`${s.surface}.${state}`] || steps[state] : null;
			if (state && typeof step !== "function") { missed.push(`${s.surface}.${state}: no function for it in --states`); continue; }
			const ctx = await browser.newContext({ viewport: { width: w, height }, colorScheme: via === "media" ? (t === "dark" ? "dark" : "light") : "light", reducedMotion: "reduce", serviceWorkers: "block", ...(argv.includes("--mobile") ? { isMobile: true, hasTouch: true } : {}), ...(storageState ? { storageState } : {}) });
			const guard = installGuard(ctx, { ...guardOpts, logFile, logBodies: Boolean(bodiesFile) });
			await guard.ready;
			const page = await ctx.newPage();
			try {
				await page.clock.install({ time: new Date("2026-01-01T09:00:00Z") });
				await page.addInitScript(FREEZE);
				if (via.startsWith("storage:")) await page.addInitScript(([k, v]) => { try { localStorage.setItem(k, v); } catch {} }, [via.slice(8), t]);
				await page.goto(new URL(s.route, base).href, { waitUntil: "load" });
				if (via === "class") await page.evaluate(themeClass(t));
				await page.evaluate(HYDRATED);
				if (step) await step(page);
				await page.evaluate(SETTLE);
				const file = join(out, `${name(s, state, w, t)}.png`);
				await page.screenshot({ path: file, fullPage: argv.includes("--full"), animations: "disabled" });
				// A blank or failed render compresses to almost nothing. It is not a baseline.
				if (readFileSync(file).length < 700) { rmSync(file); throw new Error("blank render, a capture under 700 bytes was deleted"); }
				if (aria) {
					try { writeFileSync(file.replace(/\.png$/, ".aria.yml"), (await page.locator("body").ariaSnapshot()) + "\n"); trees++; }
					catch (e) { missed.push(`${name(s, state, w, t)}: aria tree failed (needs Playwright 1.49+): ${String(e.message).split("\n")[0]}`); }
				}
				for (const a of audits) {
					try { const r = await page.evaluate(a.src); if (r === undefined || r === null) throw new Error("returned nothing"); writeFileSync(file.replace(/\.png$/, `.${a.name}.json`), JSON.stringify(r, null, 1)); evals++; }
					catch (e) { missed.push(`${name(s, state, w, t)}: eval ${a.name} failed: ${String(e.message).split("\n")[0]}`); }
				}
				written.push(file);
			} catch (e) { missed.push(`${name(s, state, w, t)}: ${String(e.message).split("\n")[0]}`); }
			await guard.releaseAll();
			blocked += guard.log.filter((l) => l.action === "abort").length;
			await ctx.close();
		}
	}
	await browser.close();

	const log = readFileSync(logFile, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
	const writes = log.filter((l) => !["GET", "HEAD", "OPTIONS"].includes(String(l.method).toUpperCase()) && l.action !== "error");
	const unproven = writes.filter((w) => w.action === "abort" || w.action === "hold");
	if (argv.includes("--no-backend") && unproven.length) console.log(`WARN\tthe app sent ${unproven.length} write request(s) though --no-backend was given, each blocked. List them in --writes: ${[...new Set(unproven.map((w) => `${w.method} ${w.proc}`))].join(", ")}`);
	if (bodiesFile) {
		mkdirSync(dirname(bodiesFile), { recursive: true });
		writeFileSync(bodiesFile, JSON.stringify({ rows: writes.map((w) => ({ method: w.method, url: w.url, proc: w.proc, body: w.body ?? "", action: w.action })) }, null, 1) + "\n");
		console.log(`bodies: ${writes.length} write request(s) in ${bodiesFile}${writes.length ? "" : ". None was sent, so the changed path was not exercised"}`);
	}
	const planned = surfaces.reduce((n, s) => n + (1 + s.states.length) * widths.length * themes.length, 0);
	for (const m of missed) console.log(`not captured\t${m}`);
	console.log(`capture: ${written.length} of ${planned} planned file(s) in ${out}, ${missed.length} not captured, ${off.length} route(s) not as expected, ${blocked} request(s) blocked (guard.log)`);
	console.log(`Coverage: ${written.length} of ${planned} captures (${surfaces.length} surface(s), widths ${widths.join(",")}, themes ${themes.join(",")} via ${via}), ${aria ? `${trees} accessibility tree(s)` : "no accessibility trees (--no-aria)"}${audits.length ? `, ${evals} audit result(s)` : ""}, ${proved}. Not captured: hover, focus and pressed states, motion in flight, states the surfaces file does not list, routes not listed`);
	// Any capture short of the plan fails the run, so a missing state is never read as a baseline.
	process.exit(off.length || missed.length || written.length < planned ? 1 : 0);
}

await main(process.argv.slice(2));
