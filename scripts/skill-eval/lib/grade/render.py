#!/usr/bin/env python3
"""Render one workspace HTML entry for the skill-eval grader and print the result as JSON.

For every width x color scheme: a 900px-high viewport with prefers-color-scheme
emulated, the entry opened over file://, a full-page PNG written to
OUT/<stem>-<width>-<scheme>.png, horizontal overflow measured as
max(0, scrollWidth - innerWidth), and console errors plus uncaught page errors
collected. Every request of the browser context (popups included) is routed:
data:, blob:, and about: pass, file: passes only inside the workspace (after
resolving symlinks), and everything else is aborted. The console errors those
aborts cause are dropped (they are counted instead).

Usage:
  uv run --with playwright python3 render.py --workspace DIR --entry REL \
      --widths 390,1280 --schemes light,dark --out DIR

Stdout is one JSON object:
  {"ok": true, "screens": [{"width", "scheme", "file", "overflowPx", "consoleErrors"}],
   "blockedRequests": [...]}
  {"ok": false, "error": "..."}            (setup problem; exit status 2)
Exit status 0 means every screen rendered; the grader applies the assertions.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.parse
import urllib.request

INLINE_SCHEMES = ("data:", "blob:", "about:")
SETTLE_MS = 300


def inside(url: str, root: pathlib.Path) -> bool:
    """True when a file: URL names a path inside root once symlinks are resolved."""
    path = pathlib.Path(urllib.request.url2pathname(urllib.parse.urlparse(url).path)).resolve()
    return path == root or root in path.parents


def make_route(blocked: set[str], root: pathlib.Path):
    def route(r, _request=None):
        url = r.request.url
        if url.startswith(INLINE_SCHEMES) or (url.startswith("file:") and inside(url, root)):
            r.continue_()
        else:
            blocked.add(url)
            r.abort()

    return route


def make_console(errors: list[str], blocked: set[str]):
    def on_console(msg):
        if msg.type != "error":
            return
        url = (msg.location or {}).get("url", "")
        if url in blocked and msg.text.startswith("Failed to load resource"):
            return
        errors.append(msg.text)

    return on_console


def emit(obj: dict, code: int) -> int:
    print(json.dumps(obj))
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=pathlib.Path, required=True)
    ap.add_argument("--entry", required=True)
    ap.add_argument("--widths", required=True)
    ap.add_argument("--schemes", required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return emit({"ok": False, "error": "playwright is not installed"}, 2)

    root = args.workspace.resolve()
    entry = (args.workspace / args.entry).resolve()
    if not entry.is_file() or root not in entry.parents:
        return emit({"ok": False, "error": f"entry not found: {args.entry}"}, 2)
    widths = [int(w) for w in args.widths.split(",") if w]
    schemes = [s for s in args.schemes.split(",") if s]
    stem = entry.stem
    args.out.mkdir(parents=True, exist_ok=True)

    screens = []
    blocked: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # Playwright raises its own Error when Chromium is missing
            first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
            return emit({"ok": False, "error": f"chromium did not start: {first}"}, 2)
        try:
            for scheme in schemes:
                for width in widths:
                    context = browser.new_context(
                        viewport={"width": width, "height": 900}, color_scheme=scheme
                    )
                    blocked_here: set[str] = set()
                    context.route("**/*", make_route(blocked_here, root))
                    page = context.new_page()
                    errors: list[str] = []
                    page.on("console", make_console(errors, blocked_here))
                    page.on("pageerror", lambda err, errors=errors: errors.append(f"pageerror: {err}"))
                    page.goto(entry.as_uri(), wait_until="load")
                    page.wait_for_timeout(SETTLE_MS)
                    overflow = page.evaluate(
                        "Math.max(0, document.documentElement.scrollWidth - window.innerWidth)"
                    )
                    shot = args.out / f"{stem}-{width}-{scheme}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    screens.append(
                        {
                            "width": width,
                            "scheme": scheme,
                            "file": shot.name,
                            "overflowPx": int(overflow),
                            "consoleErrors": errors,
                        }
                    )
                    blocked.extend(sorted(blocked_here))
                    context.close()
        finally:
            browser.close()
    return emit({"ok": True, "screens": screens, "blockedRequests": sorted(set(blocked))}, 0)


if __name__ == "__main__":
    sys.exit(main())
