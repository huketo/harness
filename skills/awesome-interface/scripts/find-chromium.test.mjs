// Tests for find-chromium.mjs. repoRoot needs only git; the launch case skips when no browser is found.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, before, test } from "node:test";
import { launchChromium, repoRoot } from "./find-chromium.mjs";

let dir;
before(() => (dir = realpathSync(mkdtempSync(join(tmpdir(), "find-chromium-")))));
after(() => rmSync(dir, { recursive: true, force: true }));

test("repoRoot: --root wins, then the git root of the first path, even one that does not exist yet", () => {
	const app = join(dir, "app");
	mkdirSync(join(app, "src"), { recursive: true });
	execFileSync("git", ["init", "-q", app], { env: { ...process.env, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1" } });
	writeFileSync(join(app, "src", "page.png"), "");
	assert.equal(repoRoot(join(dir, "elsewhere"), join(app, "src")), join(dir, "elsewhere"));
	assert.equal(repoRoot(null, join(app, "src", "page.png")), app);
	assert.equal(repoRoot(null, join(app, "captures", "not-yet", "x.png")), app);
});

// The installer links the skill folder into place, so every script must still run when started through a link.
test("every script answers --help when started through a linked skill folder", () => {
	const link = join(dir, "linked-skill");
	symlinkSync(dirname(import.meta.dirname), link, "dir");
	for (const script of ["find-chromium.mjs", "capture-guard.mjs", "capture.mjs", "pixdiff.mjs"]) {
		const r = spawnSync(process.execPath, [join(link, "scripts", script), "--help"], { encoding: "utf8" });
		assert.equal(r.status, 0, `${script}: ${r.stderr}`);
		assert.match(r.stdout, /usage|Usage/, `${script} printed nothing through the link`);
	}
});

test("launchChromium returns a browser that runs, or an error that names where it looked", async (t) => {
	const r = await launchChromium();
	if (r.error) {
		assert.match(r.error, /Playwright not found|no Chromium would launch/);
		return t.skip(`no Playwright and Chromium: ${r.error.split("\n")[0]}`);
	}
	try {
		assert.ok(r.from && r.how, JSON.stringify({ from: r.from, how: r.how }));
		assert.match(r.browser.version(), /^\d+\./);
	} finally {
		await r.browser.close();
	}
});
