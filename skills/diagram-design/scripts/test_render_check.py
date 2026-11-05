"""render_check.py against small fixtures. Needs Playwright with Chromium; skipped without it.

  uv run --with playwright python3 -m unittest discover -s scripts -p 'test_render_check.py' -v
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "render_check.py"
TEMPLATE_DUAL = SCRIPT.parent.parent / "assets" / "template-dual.html"
HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">{head}
<style>body{{margin:0;padding:2rem}} svg{{width:800px;display:block}}</style></head>
<body>{body}</body></html>"""


def diagram(inner: str, cls: str = "", style: str = "") -> str:
    return (f'<svg {cls} viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-labelledby="t-title t-desc"><title id="t-title">T</title><desc id="t-desc">D</desc>'
            f'{style}<rect width="100%" height="100%" fill="#f5f5f5"/>{inner}</svg>')


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright is not installed")
class RenderCheck(unittest.TestCase):
    def run_check(self, body: str, head: str = "", *extra: str, env: dict | None = None):
        tmp = pathlib.Path(tempfile.mkdtemp())
        page = tmp / "fixture.html"
        page.write_text(PAGE.format(head=head, body=body), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), str(page), "--out", str(tmp / "png"), "--scale", "1", *extra],
                              capture_output=True, text=True, timeout=180, env=env)
        self.png_dir = tmp / "png"
        return proc.returncode, proc.stdout + proc.stderr, sorted(p.name for p in (tmp / "png").glob("*.png"))

    def test_clean_diagram_passes_and_writes_a_png(self):
        code, out, pngs = self.run_check(diagram('<text x="40" y="40" font-size="12">Alpha</text>'
                                                 '<text x="40" y="120" font-size="12">Beta</text>'))
        self.assertEqual(code, 0, out)
        self.assertEqual(pngs, ["fixture.png"])

    def test_overlap_clip_and_broken_image_are_reported(self):
        code, out, _ = self.run_check(diagram(
            '<text x="40" y="40" font-size="12">Overlapping label</text>'
            '<text x="60" y="42" font-size="12">Second label</text>'
            '<text x="380" y="100" font-size="12">Clipped text</text>'
            '<image href="data:image/png;base64,AAAA" x="10" y="150" width="20" height="20"/>'))
        self.assertEqual(code, 1, out)
        self.assertIn('"Overlapping label" overlaps text "Second label"', out)
        self.assertIn('"Clipped text" is clipped', out)
        self.assertIn("<image> does not decode", out)

    def test_hidden_theme_pair_is_not_an_overlap(self):
        style = "<style>svg.dd .dk{display:none} :root[data-theme=dark] svg.dd .lt{display:none} :root[data-theme=dark] svg.dd .dk{display:inline}</style>"
        code, out, pngs = self.run_check(diagram(
            '<text class="lt" x="40" y="40" font-size="12">Light</text>'
            '<text class="dk" x="40" y="40" font-size="12">Dark</text>', cls='class="dd"', style=style))
        self.assertEqual(code, 0, out)
        self.assertEqual(pngs, ["fixture-dark.png", "fixture-light.png"])

    def test_missing_chromium_is_a_setup_problem(self):
        env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": tempfile.mkdtemp()}
        code, out, _ = self.run_check(diagram('<text x="40" y="40">A</text>'), env=env)
        self.assertEqual(code, 2, out)
        self.assertIn("Chromium did not start", out)
        self.assertNotIn("Traceback", out)

    def test_pinned_diagram_renders_as_authored_unless_both_is_forced(self):
        style = "<style>svg.dd{--paper:#f5f5f5} svg.dd[data-theme=dark]{--paper:#2d3142} .bg{fill:var(--paper)}</style>"
        body = diagram('<rect class="bg" width="100%" height="100%"/>', cls='class="dd" data-theme="dark"', style=style)
        code, out, pngs = self.run_check(body)
        self.assertEqual((code, pngs), (0, ["fixture.png"]), out)
        code, out, pngs = self.run_check(body, "", "--theme", "both")
        self.assertEqual((code, pngs), (0, ["fixture-dark.png", "fixture-light.png"]), out)
        light, dark = (self.png_dir / "fixture-light.png").read_bytes(), (self.png_dir / "fixture-dark.png").read_bytes()
        self.assertNotEqual(light, dark, "--theme both rendered the pinned theme twice")

    def test_hangul_without_noto_sans_kr_is_reported(self):
        code, out, _ = self.run_check(diagram('<text x="40" y="40" font-size="12">결제 서비스</text>'))
        self.assertEqual(code, 1, out)
        self.assertIn("Noto Sans KR did not load", out)


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright is not installed")
class DualThemePrecedence(unittest.TestCase):
    """assets/template-dual.html: a diagram's own data-theme beats the page's and the OS's."""

    def test_theme_matrix(self):
        from playwright.sync_api import sync_playwright
        light, dark = "#f5f5f5", "#2d3142"
        cases = [  # (color scheme, <html> data-theme, <svg> data-theme) -> --paper
            ("light", None, None, light), ("dark", None, None, dark),
            ("dark", "light", None, light), ("light", "dark", None, dark),
            ("light", "dark", "light", light), ("dark", None, "light", light),
            ("light", "light", "dark", dark), ("dark", "dark", "light", light),
        ]
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for scheme, page_theme, svg_theme, want in cases:
                with self.subTest(scheme=scheme, page=page_theme, svg=svg_theme):
                    page = browser.new_page(color_scheme=scheme)
                    page.route("**/fonts.googleapis.com/**", lambda r: r.abort())
                    page.goto(TEMPLATE_DUAL.as_uri())
                    got = page.evaluate("""([pt, st]) => {
                        const svg = document.querySelector('svg.dd');
                        if (pt) document.documentElement.setAttribute('data-theme', pt);
                        if (st) svg.setAttribute('data-theme', st);
                        return getComputedStyle(svg).getPropertyValue('--paper').trim();
                    }""", [page_theme, svg_theme])
                    self.assertEqual(got, want)
                    page.close()
            browser.close()


if __name__ == "__main__":
    unittest.main()
