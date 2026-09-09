"""check.py의 적대적 fixture. 규칙을 지킨 SVG는 통과하고, 각 규칙을 하나씩 깬 SVG는 그 항목으로 잡혀야 한다."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import check

LEGAL = """<svg viewBox="0 0 344 140" role="img" aria-labelledby="gw-title gw-desc"
     xmlns="http://www.w3.org/2000/svg"
     style="display:block;width:100%;max-width:344px;height:auto;margin:0 auto">
  <title id="gw-title">요청 경로</title>
  <desc id="gw-desc">클라이언트 요청이 Gateway를 지나 인증 서비스로 전달되는 경로</desc>
  <style>
    text { font-family: sans-serif; font-size: 14px; fill: #16191d; }
    .edge-label { font-size: 12px; }
  </style>
  <defs>
    <marker id="gw-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#16191d" />
    </marker>
  </defs>
  <line x1="138" y1="70" x2="206" y2="70" marker-end="url(#gw-arrow)" />
  <text class="edge-label" x="172" y="58" text-anchor="middle">HTTPS</text>
  <g class="node">
    <rect x="12" y="48" width="120" height="44" rx="4" />
    <text x="72" y="70" text-anchor="middle" dominant-baseline="central">클라이언트</text>
  </g>
  <g class="node strong">
    <rect x="212" y="48" width="120" height="44" rx="4" />
    <text x="272" y="70" text-anchor="middle" dominant-baseline="central">Gateway</text>
  </g>
</svg>
"""


def run(svg: str) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.svg"
        p.write_text(svg, encoding="utf-8")
        return check.check(p)


class LegalTest(unittest.TestCase):
    def test_legal_passes(self):
        self.assertEqual(run(LEGAL), [])


class BrokenTest(unittest.TestCase):
    def assert_finding(self, svg: str, needle: str):
        findings = run(svg)
        self.assertTrue(any(needle in f for f in findings), f"{needle!r} not in {findings}")

    def test_title_not_first(self):
        svg = LEGAL.replace('  <title id="gw-title">요청 경로</title>\n', "")
        svg = svg.replace("</style>", '</style>\n  <title id="gw-title">요청 경로</title>')
        self.assert_finding(svg, "<title>이 첫 자식")

    def test_missing_desc(self):
        self.assert_finding(LEGAL.replace("gw-title gw-desc", "gw-title").replace(
            '  <desc id="gw-desc">클라이언트 요청이 Gateway를 지나 인증 서비스로 전달되는 경로</desc>\n', ""), "<desc>")

    def test_dangling_labelledby(self):
        self.assert_finding(LEGAL.replace('aria-labelledby="gw-title gw-desc"', 'aria-labelledby="title desc"'), "없는 id")

    def test_dangling_marker(self):
        self.assert_finding(LEGAL.replace("url(#gw-arrow)", "url(#arrow)"), "url(#arrow)")

    def test_too_wide_for_phone(self):
        svg = LEGAL.replace('viewBox="0 0 344 140"', 'viewBox="0 0 720 140"').replace("max-width:344px", "max-width:720px")
        self.assert_finding(svg, "모바일 글자")

    def test_off_grid(self):
        self.assert_finding(LEGAL.replace('x="12" y="48"', 'x="13" y="48"'), "4의 배수")

    def test_node_too_narrow_for_hangul(self):
        svg = LEGAL.replace('<rect x="12" y="48" width="120"', '<rect x="12" y="48" width="80"')
        self.assert_finding(svg, "노드 폭 80")

    def test_mixed_script_width_counts_every_char(self):
        # '주문 v2.1' = 2×1em + 5×0.6em = 5em → 70px + 24 = 94 > 80
        svg = LEGAL.replace(">클라이언트<", ">주문 v2.1<").replace('<rect x="12" y="48" width="120"', '<rect x="12" y="48" width="80"')
        self.assert_finding(svg, "주문 v2.1")

    def test_edge_label_over_node(self):
        self.assert_finding(LEGAL.replace('x="172" y="58"', 'x="72" y="70"'), "선 라벨")

    def test_rgba_rejected(self):
        self.assert_finding(LEGAL.replace('fill="#16191d"', 'fill="rgba(22,25,29,1)"'), "rgba")

    def test_width_attr_rejected(self):
        self.assert_finding(LEGAL.replace('<svg viewBox', '<svg width="344" viewBox'), "width 속성")

    def test_script_rejected(self):
        self.assert_finding(LEGAL.replace("</svg>", "<script>1</script></svg>"), "<script>")

    def test_strong_budget(self):
        extra = "".join(
            f'<g class="node strong"><rect x="12" y="{y}" width="120" height="44"/><text x="72" y="{y+22}">n</text></g>'
            for y in (100, 148)
        )
        self.assert_finding(LEGAL.replace("</svg>", extra + "</svg>"), "강조 노드 3")

    def test_node_budget(self):
        extra = "".join(
            f'<g class="node"><rect x="12" y="{y}" width="120" height="44"/><text x="72" y="{y+22}">n</text></g>'
            for y in range(100, 100 + 48 * 8, 48)
        )
        self.assert_finding(LEGAL.replace("</svg>", extra + "</svg>"), "노드 10")


if __name__ == "__main__":
    unittest.main()
