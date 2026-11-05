#!/usr/bin/env python3
"""Render a diagram HTML with headless Chromium and report what a reader would see broken.

This is a verification render, not an export: PNGs go to a temporary directory unless
--out is given, and you must still open and look at them. Export stays manual
(references/export.md).

Usage:
  python3 render_check.py IN.html [--out DIR] [--scale 2] [--theme auto|as-authored|both]

Checks, per rendered diagram (<svg role="img">) and theme:
  - two <text> elements whose boxes overlap
  - a <text> that sticks out of its <svg> canvas (clipped)
  - an <image> whose data cannot be decoded (a broken logo)
  - Hangul present but the Noto Sans KR web font not loaded (offline or blocked), with
    the locally installed Korean families that will be used instead
It does not check connectors against labels or nodes; that is what looking at the PNG is for.

--theme auto (default) renders light and dark when the diagram uses the dual-theme
contract (<svg class="dd">, assets/template-dual.html) and no diagram pins a theme with its
own data-theme; a pinned diagram renders as authored. --theme both forces light and dark on
the page and on every svg.dd, pins included.

Exit status: 0 clean, 1 findings, 2 setup problem.

Requires Playwright with Chromium. Without changing the system Python:
  uv run --with playwright python3 render_check.py IN.html
Otherwise: pip install playwright && python3 -m playwright install chromium
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile

PROBE = r"""
async () => {
  const out = [];
  const svgs = [...document.querySelectorAll('svg[role="img"]')];
  for (const [i, svg] of svgs.entries()) {
    const box = svg.getBoundingClientRect();
    const texts = [...svg.querySelectorAll('text')]
      .filter(t => t.textContent.trim() && getComputedStyle(t).display !== 'none'
                   && t.closest('[display="none"]') === null)
      .map(t => ({t, r: t.getBoundingClientRect(), s: t.textContent.trim().slice(0, 40)}))
      .filter(x => x.r.width > 0 && x.r.height > 0);
    for (let a = 0; a < texts.length; a++) {
      const A = texts[a].r;
      if (A.left < box.left - 0.5 || A.top < box.top - 0.5 || A.right > box.right + 0.5 || A.bottom > box.bottom + 0.5)
        out.push(`svg#${i}: text "${texts[a].s}" is clipped by the canvas edge`);
      for (let b = a + 1; b < texts.length; b++) {
        const B = texts[b].r;
        const w = Math.min(A.right, B.right) - Math.max(A.left, B.left);
        const h = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
        if (w > 1 && h > 1)
          out.push(`svg#${i}: text "${texts[a].s}" overlaps text "${texts[b].s}"`);
      }
    }
    for (const img of svg.querySelectorAll('image')) {
      if (getComputedStyle(img).display === 'none') continue;
      const href = img.getAttribute('href') || img.getAttribute('xlink:href') || '';
      const probe = new Image();
      probe.src = href;
      try { await probe.decode(); }
      catch (e) { out.push(`svg#${i}: <image> does not decode (${href.slice(0, 40)}...)`); }
    }
  }
  const hangul = /[ᄀ-ᇿ㄰-㆏가-힯]/.test(document.body.innerText + [...document.querySelectorAll('svg text')].map(t => t.textContent).join(''));
  return {findings: out, count: svgs.length, hangul,
          // fonts.check() is true for a family with no web face at all, so look for a loaded face.
          notoKr: [...document.fonts].some(f => f.family.replace(/["']/g, '') === 'Noto Sans KR' && f.status === 'loaded')};
}
"""


def korean_families() -> str:
    try:
        out = subprocess.run(["fc-list", ":lang=ko", "family"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return "unknown (fc-list not available)"
    families = sorted({line.split(",")[0].strip() for line in out.splitlines() if line.strip()})
    return ", ".join(families[:6]) or "none"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--scale", type=float, default=2)
    ap.add_argument("--theme", choices=["auto", "as-authored", "both"], default="auto")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run without changing the system Python:\n"
              f"  uv run --with playwright python3 {sys.argv[0]} {args.html}\n"
              "or install it: pip install playwright && python3 -m playwright install chromium",
              file=sys.stderr)
        return 2
    if not args.html.is_file():
        print(f"no such file: {args.html}", file=sys.stderr)
        return 2

    src = args.html.resolve()
    html = src.read_text(encoding="utf-8", errors="ignore")
    url = src.as_uri() + ("?motion=static" if "data-motion-root" in html else "")
    out_dir = args.out or pathlib.Path(tempfile.mkdtemp(prefix="dd-render-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    findings: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--font-render-hinting=none"])
        except Exception as e:  # Playwright raises its own Error when Chromium is missing
            first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
            print(f"Chromium did not start: {first}\n"
                  "Install the browser: python3 -m playwright install chromium "
                  "(or uv run --with playwright python3 -m playwright install chromium)",
                  file=sys.stderr)
            return 2
        page = browser.new_page(viewport={"width": 1400, "height": 1000}, device_scale_factor=args.scale)
        page.goto(url)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            findings.append("page did not reach network idle in 15s (web fonts may be missing)")
        page.evaluate("document.fonts.ready.then(() => true)")
        dual = page.evaluate("document.querySelector('svg.dd:not([data-theme])') !== null")
        themes = ["light", "dark"] if args.theme == "both" or (args.theme == "auto" and dual) else [None]
        for theme in themes:
            if theme:
                # auto switches the page only, so a pinned diagram keeps its pin; both overrides pins.
                targets = "document.querySelectorAll('svg.dd')" if args.theme == "both" else "[]"
                page.evaluate(f"""for (const el of [document.documentElement, ...{targets}])
                                    el.setAttribute('data-theme', '{theme}')""")
                page.wait_for_timeout(150)
            result = page.evaluate(PROBE)
            label = theme or "as-authored"
            if result["count"] == 0:
                findings.append('no <svg role="img"> found; nothing to check')
            findings += [f"[{label}] {f}" for f in result["findings"]]
            if result["hangul"] and not result["notoKr"]:
                findings.append(f"[{label}] Hangul present but Noto Sans KR did not load; local Korean "
                                f"fonts in use: {korean_families()}. Check the font link or install "
                                f"fonts-noto-cjk before trusting Korean widths.")
            for i, el in enumerate(page.query_selector_all('svg[role="img"]')):
                suffix = f"-{theme}" if theme else ""
                shot = out_dir / f"{src.stem}{'-' + str(i) if i else ''}{suffix}.png"
                el.screenshot(path=str(shot))
                print(f"rendered {shot}")
        browser.close()

    for f in dict.fromkeys(findings):
        print(f"FINDING {f}")
    if findings:
        return 1
    print("no automatic findings. Open every PNG above and check connectors, labels, and logos by eye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
