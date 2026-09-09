#!/usr/bin/env python3
"""svg-diagram 규칙을 SVG 파일에서 정적으로 검사한다. 표준 라이브러리만 쓴다.

    python3 check.py diagram.svg [more.svg ...]

렌더 없이 마크업만으로 판정할 수 있는 규칙을 검사한다: 접근성 계약, self-contained,
모바일 폭 상한, 4px 격자, 글자 폭 대비 노드 폭, 선 라벨과 노드의 겹침, 예산.
렌더된 결과(실제 글리프 폭, 화살촉 위치)는 SKILL.md의 브라우저 audit이 담당한다.
발견이 없으면 종료 코드 0, 있으면 1이며 한 줄에 하나씩 `파일: 문제`를 출력한다.
"""

from __future__ import annotations

import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
FONT_PX_DEFAULT = 14.0
MIN_RENDERED_PX = 11.0
PHONE_CONTENT_WIDTH = 300.0
NODE_PADDING = 12.0
MAX_NODES = 9
MAX_EDGES = 12
MAX_STRONG = 2
FONT_SIZE_RE = re.compile(r"\btext\s*\{[^}]*?font-size\s*:\s*([\d.]+)px", re.S)
URL_REF_RE = re.compile(r"url\(#([^)]+)\)")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_width_em(s: str) -> float:
    """글자 단위 폭. 전각·넓은 문자 1em, 결합 문자 0, 그 외 0.6em."""
    total = 0.0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        total += 1.0 if unicodedata.east_asian_width(ch) in ("W", "F") else 0.6
    return total


def num(el: ET.Element, attr: str, default: float = 0.0) -> float:
    try:
        return float(el.get(attr, default))
    except ValueError:
        return default


def check(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    findings: list[str] = []
    try:
        root = ET.fromstring(source)
    except ET.ParseError as e:
        return [f"XML 파싱 실패: {e}"]
    if local(root.tag) != "svg":
        return ["루트가 <svg>가 아님"]
    if root.tag != f"{{{SVG_NS}}}svg":
        findings.append("xmlns=\"http://www.w3.org/2000/svg\" 없음")

    children = list(root)
    if not children or local(children[0].tag) != "title" or not (children[0].text or "").strip():
        findings.append("<title>이 첫 자식이 아니거나 비어 있음")
    desc = next((c for c in children if local(c.tag) == "desc"), None)
    if desc is None or not (desc.text or "").strip():
        findings.append("<desc> 없음 또는 비어 있음")
    if root.get("role") != "img":
        findings.append("role=\"img\" 없음")
    ids = {el.get("id") for el in root.iter() if el.get("id")}
    labelledby = root.get("aria-labelledby", "").split()
    if not labelledby:
        findings.append("aria-labelledby 없음")
    for ref in labelledby:
        if ref not in ids:
            findings.append(f"aria-labelledby가 없는 id를 가리킴: {ref}")
    for ref in URL_REF_RE.findall(source):
        if ref not in ids:
            findings.append(f"url(#{ref})가 없는 id를 가리킴")
    for el in root.iter():
        if local(el.tag) == "script":
            findings.append("<script> 포함")
        for k, v in el.attrib.items():
            if k.lower().startswith("on"):
                findings.append(f"실행 속성 {k}")
            if local(k) in ("href", "src") and re.match(r"^(https?:)?//", v):
                findings.append(f"외부 참조 {v}")
        if local(el.tag) == "style" and "@import" in (el.text or ""):
            findings.append("<style> 안에 @import")
    for k, v in root.attrib.items():
        if k in ("width", "height"):
            findings.append(f"루트에 {k} 속성 (viewBox와 style만 쓴다)")

    for attr in ("fill", "stroke"):
        for m in re.finditer(rf"{attr}\s*[:=]\s*\"?(rgba?\([^)]*\)|transparent)", source):
            findings.append(f"{attr}에 {m.group(1)} (hex와 -opacity를 쓴다)")

    vb = root.get("viewBox", "").split()
    if len(vb) != 4:
        findings.append("viewBox 없음")
        width = None
    else:
        width = float(vb[2])
        if width % 4 or float(vb[3]) % 4:
            findings.append(f"viewBox 크기가 4의 배수가 아님: {vb[2]}x{vb[3]}")
    style_text = "".join((el.text or "") for el in root.iter() if local(el.tag) == "style")
    m = FONT_SIZE_RE.search(style_text)
    font_px = float(m.group(1)) if m else FONT_PX_DEFAULT
    if width is not None:
        rendered = font_px * PHONE_CONTENT_WIDTH / width
        if rendered < MIN_RENDERED_PX:
            findings.append(
                f"모바일 글자 {rendered:.1f}px < {MIN_RENDERED_PX:g}px (폰트 {font_px:g}px이면 W ≤ {font_px * PHONE_CONTENT_WIDTH / MIN_RENDERED_PX:.0f})"
            )
        if f"max-width:{width:g}px" not in root.get("style", "").replace(" ", ""):
            findings.append(f"style에 max-width:{width:g}px 없음")

    node_rects: list[tuple[float, float, float, float]] = []
    nodes = strong = 0
    for g in root.iter(f"{{{SVG_NS}}}g"):
        classes = g.get("class", "").split()
        if "node" not in classes:
            continue
        nodes += 1
        if "strong" in classes:
            strong += 1
        rect = g.find(f"{{{SVG_NS}}}rect")
        texts = [t for t in g.iter(f"{{{SVG_NS}}}text")]
        if rect is None:
            continue
        x, y, w, h = (num(rect, a) for a in ("x", "y", "width", "height"))
        node_rects.append((x, y, w, h))
        for a, v in (("x", x), ("y", y), ("width", w), ("height", h)):
            if v % 4:
                findings.append(f"노드 rect {a}={v:g}가 4의 배수가 아님")
        order = [local(c.tag) for c in g]
        if "text" in order and order.index("text") < order.index("rect"):
            findings.append("노드 안에서 텍스트가 도형보다 먼저 옴")
        for t in texts:
            lines = [t.text or ""] + [(s.text or "") for s in t.iter(f"{{{SVG_NS}}}tspan")]
            size = font_px
            if "sub" in t.get("class", "").split():
                size = 12.0
            for line in lines:
                if not line.strip():
                    continue
                need = text_width_em(line) * size + 2 * NODE_PADDING
                if need > w + 0.5:
                    findings.append(f"노드 폭 {w:g} < 필요 폭 {need:.0f} ({line!r})")

    edges = 0
    for el in root.iter():
        tag = local(el.tag)
        if tag == "line" or (tag == "path" and "edge" in el.get("class", "").split()):
            if el.get("marker-end") or el.get("marker-start"):
                edges += 1
    for t in root.iter(f"{{{SVG_NS}}}text"):
        if "edge-label" not in t.get("class", "").split():
            continue
        label = t.text or ""
        lw = text_width_em(label) * 12.0
        cx, cy = num(t, "x"), num(t, "y")
        anchor = t.get("text-anchor", "start")
        lx = cx - lw / 2 if anchor == "middle" else (cx - lw if anchor == "end" else cx)
        ly = cy - 12.0
        for x, y, w, h in node_rects:
            if lx < x + w and x < lx + lw and ly < y + h and y < ly + 12.0:
                findings.append(f"선 라벨 {label!r}가 노드 ({x:g},{y:g})와 겹침")

    if nodes > MAX_NODES:
        findings.append(f"노드 {nodes} > {MAX_NODES}")
    if edges > MAX_EDGES:
        findings.append(f"화살표 {edges} > {MAX_EDGES}")
    if strong > MAX_STRONG:
        findings.append(f"강조 노드 {strong} > {MAX_STRONG}")
    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    total = 0
    for arg in argv:
        for f in check(Path(arg)):
            print(f"{arg}: {f}")
            total += 1
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
