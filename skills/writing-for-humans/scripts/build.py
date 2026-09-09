#!/usr/bin/env python3
"""Markdown 원본 하나를 HTML(single-file) 또는 Word로 패키징한다.

    python3 build.py 문서.md --to html [--theme slate] [--style reading] [--out 경로]
    python3 build.py 문서.md --to docx [--out 경로]

원본의 YAML front matter `genre:`가 테마·스타일 기본값을 정한다. 옵션이 그 값을 덮어쓴다.
Markdown 산출물은 원본 그대로이므로 이 스크립트를 거치지 않는다.
pandoc 3 이상이 필요하다. 없으면 FORMATS.md의 수동 절차를 따른다.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHELL = HERE.parent / "html" / "shell.html"
FILTER = HERE.parent / "html" / "filters.lua"

THEMES = ("slate", "ember", "moss", "ink", "editorial")
STYLES = ("reading", "compact", "print")
GENRE_DEFAULTS = {
    "report": ("slate", "reading"),
    "postmortem": ("ember", "reading"),
    "design": ("slate", "reading"),
    "guide": ("moss", "compact"),
    "brief": ("ink", "reading"),
    "minutes": ("slate", "compact"),
    "post": ("editorial", "reading"),
}
TOC_MIN_SECTIONS = 6
FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def front_matter(text: str) -> dict[str, str]:
    m = FRONT_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def resolve(source: Path, theme: str | None, style: str | None) -> tuple[str, str, dict[str, str]]:
    text = source.read_text(encoding="utf-8")
    meta = front_matter(text)
    genre = meta.get("genre", "report")
    if genre not in GENRE_DEFAULTS:
        raise SystemExit(f"알 수 없는 genre: {genre} (가능: {', '.join(GENRE_DEFAULTS)})")
    d_theme, d_style = GENRE_DEFAULTS[genre]
    theme = theme or d_theme
    style = style or d_style
    if theme not in THEMES:
        raise SystemExit(f"알 수 없는 theme: {theme} (가능: {', '.join(THEMES)})")
    if style not in STYLES:
        raise SystemExit(f"알 수 없는 style: {style} (가능: {', '.join(STYLES)})")
    meta["_sections"] = str(len(re.findall(r"^## ", text, re.M)))
    return theme, style, meta


def pandoc_cmd(source: Path, to: str, out: Path, theme: str, style: str, meta: dict[str, str]) -> list[str]:
    cmd = ["pandoc", str(source.name), "--from", "markdown", "--standalone", "--lua-filter", str(FILTER), "-o", str(out)]
    if to == "html":
        cmd += ["--to", "html5", "--template", str(SHELL), "--no-highlight", "-V", f"theme={theme}", "-V", f"style={style}"]
        if int(meta["_sections"]) >= TOC_MIN_SECTIONS:
            cmd += ["--toc", "--toc-depth=2"]
    elif to == "docx":
        cmd += ["--to", "docx"]
    return cmd


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("--to", choices=("html", "docx"), required=True)
    ap.add_argument("--theme", choices=THEMES)
    ap.add_argument("--style", choices=STYLES)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if shutil.which("pandoc") is None:
        print("pandoc이 없다. FORMATS.md의 수동 절차를 따른다.", file=sys.stderr)
        return 2
    source = a.source.resolve()
    theme, style, meta = resolve(source, a.theme, a.style)
    out = (a.out or source.with_suffix("." + a.to)).resolve()
    cmd = pandoc_cmd(source, a.to, out, theme, style, meta)
    r = subprocess.run(cmd, cwd=source.parent, capture_output=True, text=True)
    if r.stderr:
        print(r.stderr, file=sys.stderr, end="")
    if r.returncode:
        return r.returncode
    if a.to == "html":
        html = out.read_text(encoding="utf-8")
        left = re.findall(r"\{\{[^}]*\}\}", html)
        if left:
            print(f"자리표시자 {len(left)}개 남음: {', '.join(dict.fromkeys(left))}", file=sys.stderr)
    print(f"{out} (genre={meta.get('genre', 'report')}, theme={theme}, style={style})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
