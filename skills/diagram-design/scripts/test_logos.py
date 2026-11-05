"""Offline tests for logos.py: safety verdicts, inlining, credits. No network."""
from __future__ import annotations

import base64
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import logos  # noqa: E402

CLEAN = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#533afd" d="M0 0h24v24z"/></svg>'
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def svg(body: str, attrs: str = "") -> bytes:
    return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"{attrs}>{body}</svg>'.encode()


class Classify(unittest.TestCase):
    def test_clean_svg_and_illustrator_doctype_pass(self):
        self.assertEqual(logos.classify(CLEAN), ("svg", None))
        doctype = (b'<?xml version="1.0"?>\n<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                   b'"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n' + CLEAN)
        self.assertEqual(logos.classify(doctype), ("svg", None))

    def test_internal_fragment_and_gradient_references_pass(self):
        ok = svg('<defs><linearGradient id="g"/></defs><use href="#g"/><path fill="url(#g)" d="M0 0h1v1z"/>')
        self.assertEqual(logos.classify(ok), ("svg", None))

    def test_plain_css_strings_pass(self):
        ok = svg('<style>.st0{fill:#533afd;font-family:"Helvetica Neue", \'Arial\'}</style>'
                 '<text class="st0" style="font-family:\'Geist\'">a</text>')
        self.assertEqual(logos.classify(ok), ("svg", None))

    def test_metadata_urls_outside_css_pass(self):
        ok = svg('<metadata><r:RDF xmlns:r="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                 '<r:Description r:about="https://example.org/logo"/></r:RDF></metadata><rect width="1" height="1"/>')
        self.assertEqual(logos.classify(ok), ("svg", None))

    def test_unsafe_svgs_are_rejected_with_a_reason(self):
        cases = {
            "<script>": svg("<script>alert(1)</script>"),
            "event-handler": svg('<rect width="1" height="1"/>', ' onload="alert(1)"'),
            "foreignObject": svg("<foreignObject><div/></foreignObject>"),
            "external href": svg('<image href="https://evil.example/x.png" width="1" height="1"/>'),
            "external href ": svg('<use xlink:href="http://evil.example/s.svg#a"/>'),
            "javascript": svg('<a href="javascript:alert(1)"><rect width="1" height="1"/></a>'),
            "remote CSS": svg("<style>rect{fill:url(https://evil.example/p)}</style>"),
            "@import": svg("<style>@import 'x.css';</style>"),
            "ENTITY": b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]>' + CLEAN,
            # Bypasses of a raw-byte scan: a dotted namespace prefix, character references,
            # CSS escapes and comments, a namespaced href, and a stylesheet PI.
            "dotted prefix": svg('<x.y:script xmlns:x.y="http://www.w3.org/2000/svg">x()</x.y:script>'),
            "char ref url": svg('<path fill="url(&#104;ttps://evil.example/x.svg#p)" d="M0 0h1v1z"/>'),
            "char ref javascript": svg('<a href="&#106;avascript:x()"><rect width="1" height="1"/></a>'),
            "css escape url": svg("<style>rect{fill:u\\72l(https://evil.example/p)}</style>"),
            "css comment import": svg("<style>@im/**/port 'x.css';</style>"),
            "style attr url": svg('<rect style="fill:url(//evil.example/p)" width="1" height="1"/>'),
            "unterminated url": svg('<rect style="fill:url(https://evil.example/p" width="1" height="1"/>'),
            "unterminated quoted url": svg("<style>rect{fill:url('https://evil.example/p</style>"),
            "newline-broken string": svg("<style>rect{fill:url('#safe\n);stroke:url(https://evil.example/p)}</style>"),
            "image() string": svg('<rect style="mask-image:image(\'https://evil.example/p\')" width="1" height="1"/>'),
            "protocol-relative string": svg("<style>rect{mask-image:cross-fade('//evil.example/p', 50%)}</style>"),
            "one-slash image-set": svg('<rect style="mask-image:image-set(\'https:/evil.example/p\' 1x)" width="1" height="1"/>'),
            "no-slash string": svg("<style>rect{mask-image:image-set(\"https:evil.example/p\" 1x)}</style>"),
            "path string": svg("<style>@font-face{font-family:x;src:local('x'),'/evil/p'}</style>"),
            "image-set": svg('<rect style="mask-image:image-set(\'https://evil.example/p\' 1x)" width="1" height="1"/>'),
            "xhtml element": svg('<h:div xmlns:h="http://www.w3.org/1999/xhtml"/>'),
            "xml-stylesheet": b'<?xml-stylesheet href="https://evil.example/s.css"?>' + CLEAN,
        }
        for name, data in cases.items():
            with self.subTest(name):
                ext, problem = logos.classify(data + b" " * 50)
                self.assertIsNone(ext)
                self.assertTrue(problem, f"{name} was not rejected")

    def test_html_error_page_is_a_miss_not_a_rejection(self):
        page = b"<!DOCTYPE html><html><head><script>x()</script></head><body>404</body></html>"
        self.assertEqual(logos.classify(page), (None, None))

    def test_rasters_by_magic_bytes_only(self):
        self.assertEqual(logos.classify(PNG), ("png", None))
        self.assertEqual(logos.classify(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 60), ("webp", None))
        self.assertEqual(logos.classify(b"GIF89a" + b"\x00" * 60), (None, None))

    def test_white_fill_only_when_the_whole_mark_is_white(self):
        self.assertTrue(logos.white_fill(svg('<path fill="#fff" d="M0 0h1v1z"/>')))
        self.assertFalse(logos.white_fill(svg('<path fill="#fff" d="M0 0h1v1z"/><path fill="#f00" d="M0 0h1v1z"/>')))


class Inline(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.logodir = self.tmp / "logos"
        self.logodir.mkdir()
        (self.logodir / "hono.svg").write_bytes(CLEAN)
        (self.logodir / "manifest.json").write_text(json.dumps({
            "hono": {"source": "svgl"}, "s3": {"source": "aws"}}))

    def run_inline(self, html: str):
        draft, out = self.tmp / "draft.html", self.tmp / "out.html"
        draft.write_text(html)
        err, std = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(std):
            code = logos.inline(draft, self.logodir, out)
        return code, out, err.getvalue()

    def test_tokens_become_data_uris_and_credits_fill(self):
        code, out, _ = self.run_inline('<image href="%%LOGO_hono%%"/><footer>%%LOGO_CREDITS%%</footer>')
        self.assertEqual(code, 0)
        html = out.read_text()
        self.assertIn("data:image/svg+xml;base64," + base64.b64encode(CLEAN).decode(), html)
        self.assertIn("logos: svgl / AWS Architecture Icons.", html)
        self.assertNotIn("%%", html)

    def test_unresolved_token_fails_without_writing(self):
        code, out, err = self.run_inline('<image href="%%LOGO_missing%%"/>')
        self.assertEqual(code, 1)
        self.assertIn("%%LOGO_missing%%", err)
        self.assertFalse(out.exists())

    def test_unsafe_file_on_disk_is_not_embedded(self):
        (self.logodir / "evil.svg").write_bytes(svg("<script>x()</script>") + b" " * 50)
        code, out, err = self.run_inline('<image href="%%LOGO_evil%%"/>')
        self.assertEqual(code, 1)
        self.assertIn("evil.svg", err)
        self.assertFalse(out.exists())


class Fetch(unittest.TestCase):
    def test_bad_names_are_refused_before_any_network(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = logos.fetch(tmp, ["bad name", "x_dark", "../up"])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue().count("SKIP"), 3)
        self.assertEqual(json.loads((tmp / "manifest.json").read_text()), {})


if __name__ == "__main__":
    unittest.main()
