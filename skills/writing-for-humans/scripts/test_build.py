"""build.py 검사. 장르 기본값 해석은 항상 검사하고, 실제 변환은 pandoc이 있을 때만 검사한다."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import build

HERE = Path(__file__).resolve().parent
GENRES = HERE.parent / "genres"

SVG = """<svg viewBox="0 0 344 140" role="img" aria-labelledby="t-title t-desc" xmlns="http://www.w3.org/2000/svg"
     style="display:block;width:100%;max-width:344px;height:auto;margin:0 auto">
  <title id="t-title">제목</title><desc id="t-desc">설명</desc>
  <g class="node"><rect x="12" y="48" width="120" height="44"/><text x="72" y="70">노드</text></g>
</svg>
"""

DOC = """---
genre: guide
title: "테스트 문서"
date: 2026-09-09
author: 검사자
---

## 전제 조건

> [!WARNING]
> 되돌릴 수 없다.

## 절차

![그림 설명](fig.svg)

| a | b |
| --- | ---: |
| 1 | 2 |

## 참고

- [문서](https://example.com): 근거
"""


class ResolveTest(unittest.TestCase):
    def test_genre_defaults(self):
        for g, (theme, style) in build.GENRE_DEFAULTS.items():
            src = GENRES / f"{g}.md"
            self.assertTrue(src.exists(), src)
            t, s, meta = build.resolve(src, None, None)
            self.assertEqual((t, s), (theme, style))
            self.assertEqual(meta["genre"], g)

    def test_override(self):
        t, s, _ = build.resolve(GENRES / "report.md", "ink", "print")
        self.assertEqual((t, s), ("ink", "print"))

    def test_unknown_genre_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.md"
            p.write_text("---\ngenre: novel\ntitle: x\n---\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                build.resolve(p, None, None)


@unittest.skipUnless(shutil.which("pandoc"), "pandoc 없음")
class PandocTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "fig.svg").write_text(SVG, encoding="utf-8")
        self.src = self.root / "doc.md"
        self.src.write_text(DOC, encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def test_html_uses_shell_and_filters(self):
        self.assertEqual(build.main([str(self.src), "--to", "html"]), 0)
        html = (self.root / "doc.html").read_text(encoding="utf-8")
        self.assertIn('class="theme-moss style-compact"', html)
        self.assertIn('<figure class="diagram">', html)
        self.assertIn('<title id="t-title">', html)  # 인라인 SVG
        self.assertIn('class="table-wrap"', html)
        self.assertIn('class="note note-warning"', html)
        self.assertIn("<strong>주의</strong>", html)
        self.assertNotIn("[!WARNING]", html)
        self.assertNotIn("<script", html)
        self.assertNotIn('src="http', html)

    def test_html_theme_override(self):
        self.assertEqual(build.main([str(self.src), "--to", "html", "--theme", "ink", "--style", "print"]), 0)
        self.assertIn('class="theme-ink style-print"', (self.root / "doc.html").read_text(encoding="utf-8"))

    def test_docx_swaps_png_for_svg(self):
        (self.root / "fig.png").write_bytes(bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc0000003010100c9fe92ef0000000049454e44ae426082"))
        self.assertEqual(build.main([str(self.src), "--to", "docx"]), 0)
        self.assertTrue((self.root / "doc.docx").exists())


if __name__ == "__main__":
    unittest.main()
