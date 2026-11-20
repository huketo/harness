# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "fonttools", "uharfbuzz"]
# ///
"""Write the logo book: every direction presented the way a studio presents logo directions (references/logo-book.md).

    uv run logo_book.py <build dir> [...] --out <book dir> --refs <ref folder> [...] --name "Fieldnote"
        --line "Inspections and permits from the job site" [--tagline "From site to sign-off"]
        [--note "a notification the app would send"] [--photos <folder>] [--brief brief.json] [--lang en|ko]
        [--calibration calibration.json] [--include-failed] [--fonts <cache>]

Then print it: `node render_book.mjs <book dir>` writes pages/*.png and logobook.pdf.

Pages: a cover; the directions side by side; for each direction a spread of the mark in use (a dark lockup, a browser
tab, a poster), a spread of its construction (a light lockup, the grid, a phone), where a traced mark came from, its
colour, and its small sizes; then one page comparing them with their checks. No reference logos; photos only from
--photos, credited at the end.

Each build must still match its check.json (build.json, every file it lists, the --refs images, the calibration and,
for a traced build, its sources and the collections), all verified before the book writes anything, and the book reads
only the verified bytes of the files build.json lists: a build with no lockup shows its mark in the
lockup's place. A direction that failed check_logo.py is left out unless --include-failed, which shows it marked as
failed. The book is written in the brief's language, Korean for a Korean brief, set in an OFL face from Google Fonts
that has the script. A photo is used only when its manifest entry says who made it, under what licence and where it
came from, so the credits page can name it.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fonts as F  # noqa: E402
import rights as R  # noqa: E402

W, H = 1600, 900
BOOK_FONT = {"en": "Inter Tight", "ko": "Noto Sans KR"}

TEXT = {
    "en": {
        "title": "{name} logo directions", "logo_directions": "Logo directions", "directions": "{n} directions",
        "direction": "1 direction", "colour": "Colour", "sizes": "Sizes and versions", "side": "Side by side",
        "photos": "Photos", "photo": "Photo", "small": "Small sizes", "reversed": "Reversed", "on_colour": "On colour",
        "stroke": "Stroke at 16 px: {v}", "not_checked": "not checked", "checks": "Checks", "not_run": "not run",
        "failed": "Failed a check, shown on request",
        "tracing": "Where it came from", "traced": "Traced from {file}", "source": "Source file", "sha": "SHA-256",
        "kind": "Rights", "asked": "Question shown", "answer": "Their answer, verbatim",
        "score": "Score against the source", "score_line": "{s} against the source, shown and not checked",
        "unverified": "make-logo recorded this statement and bound it to the file's hash. It did not verify it.",
        "rights": {"own-drawing": "The person's own drawing", "own-brand": "The person's own brand",
                   "licensed": "Licensed to the person"},
        "check_names": {},
    },
    "ko": {
        "title": "{name} 로고 방향", "logo_directions": "로고 방향", "directions": "방향 {n}가지", "direction": "방향 1가지",
        "colour": "색", "sizes": "크기와 변형", "side": "나란히 비교", "photos": "사진", "photo": "사진",
        "small": "작은 크기", "reversed": "반전", "on_colour": "색 바탕", "stroke": "16 px에서 획 굵기: {v}",
        "not_checked": "검사하지 않음", "checks": "검사", "not_run": "실행하지 않음",
        "failed": "검사에 실패했지만 요청에 따라 넣은 방향입니다",
        "tracing": "마크의 출처", "traced": "트레이싱 원본: {file}", "source": "원본 파일", "sha": "SHA-256",
        "kind": "권리 유형", "asked": "사용자에게 보인 질문", "answer": "사용자의 답(원문)",
        "score": "원본과의 점수", "score_line": "원본과의 점수 {s}(표시만 하며 검사하지 않습니다)",
        "unverified": "make-logo는 이 진술을 기록하고 파일의 해시에 묶었을 뿐이며, 진술이 사실인지는 확인하지 않았습니다.",
        "rights": {"own-drawing": "사용자가 직접 그린 그림", "own-brand": "사용자 자신의 브랜드",
                   "licensed": "사용자가 이용 허락을 받은 자료"},
        "check_names": {"stroke at 16 px": "16 px 획 굵기", "counters at 16 px": "16 px 속공간",
                        "ink on paper": "바탕 위 잉크 대비", "accent against paper or ink": "포인트 색 대비",
                        "nearest reference": "가장 가까운 참고 로고"},
    },
}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def read_svg(svg: str) -> tuple[str, str]:
    """(viewBox, path d) of a single-path SVG written by build_logo.py."""
    return re.search(r'viewBox="([^"]+)"', svg).group(1), re.search(r' d="([^"]+)"', svg).group(1)


def logo(svg: str, fill: str, height: float | None = None, width: float | None = None, cls: str = "") -> str:
    vb, d = read_svg(svg)
    _, _, w, h = (float(v) for v in vb.split())
    if height is not None:
        width = height * w / h
    elif width is not None:
        height = width * h / w
    return (f'<svg class="logo {cls}" viewBox="{vb}" width="{width:.1f}" height="{height:.1f}" aria-hidden="true">'
            f'<path fill="{fill}" d="{d}"/></svg>')


def rgb(h: str) -> list[int]:
    h = h.lstrip("#")
    if len(h) == 3:  # #999 is #999999
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a: str, b: str, t: float) -> str:
    pa, pb = rgb(a), rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def field(p: dict, angle: int = 135) -> str:
    """A soft colour field in the direction's palette, standing in for a photograph."""
    return (f"background: radial-gradient(120% 90% at 0% 100%, {p['accent']} 0%, {mix(p['accent'], p['tint'], .55)} 38%, transparent 70%),"
            f" radial-gradient(80% 70% at 70% 10%, {mix(p['tint'], '#ffffff', .5)} 0%, transparent 60%), {p['tint']};")


def thin(vals, lo, hi, g, gap_share=0.12, most=5):
    """A few clean guides, as a studio would draw them: the mark's two edges, then the recipe's own lines that sit
    well apart from those already kept (at least `gap_share` of the grid), at most `most` per axis."""
    keep = [lo, hi]
    for v in sorted(vals, key=lambda v: -min(abs(v - k) for k in keep)):
        if len(keep) >= most:
            break
        if all(abs(v - k) >= gap_share * g for k in keep):
            keep.append(v)
    return sorted(keep)


def construction(build: dict, files: dict[str, str], p: dict, w: int, h: int) -> str:
    """The mark on its grid with dashed guides run edge to edge, as the construction tile."""
    g = build["grid"]
    _, d = read_svg(files["mark-grid.svg"])
    s = h * 0.34 / g
    ox, oy = (w - g * s) / 2, (h - g * s) / 2
    lines = []
    for x in thin(build["guides"]["x"], build["mark_box"][0], build["mark_box"][2], g):
        X = ox + x * s
        lines.append(f'<line x1="{X:.1f}" y1="0" x2="{X:.1f}" y2="{h}"/>')
    for y in thin(build["guides"]["y"], build["mark_box"][1], build["mark_box"][3], g):
        Y = oy + y * s
        lines.append(f'<line x1="0" y1="{Y:.1f}" x2="{w}" y2="{Y:.1f}"/>')
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="grid">'
            f'<g stroke="{mix(p["paper"], p["ink"], .35)}" stroke-width="1.2" stroke-dasharray="7 6">{"".join(lines)}</g>'
            f'<path transform="translate({ox:.1f} {oy:.1f}) scale({s:.4f})" fill="{mix(p["paper"], p["neutral"], .25)}" d="{d}"/></svg>')


def browser(name: str, mark: str, p: dict) -> str:
    domain = re.sub(r"[^a-z0-9]", "", name.lower()) + ".com"
    icon = f'<span class="fav" style="background:{p["accent"]}">{logo(mark, p["ink"] if lum(p["accent"]) > .45 else "#ffffff", height=26)}</span>'
    return f"""<div class="browser">
      <div class="tabs"><i></i><i></i><i></i><div class="tab">{icon}<b>{esc(name)}</b><span class="x">×</span></div></div>
      <div class="bar"><span class="nav">←</span><span class="nav">→</span><span class="nav">↻</span>
        <span class="url" style="background:{p['tint']}"><svg width="14" height="16" viewBox="0 0 14 16"><rect x="1" y="7" width="12" height="9" rx="2" fill="{p['ink']}"/><path d="M4 7V5a3 3 0 0 1 6 0v2" stroke="{p['ink']}" stroke-width="2" fill="none"/></svg>{domain}</span></div>
    </div>"""


def phone(name: str, mark: str, p: dict, note: str) -> str:
    on = p["ink"] if lum(p["accent"]) > .45 else "#ffffff"
    apps = []
    for i in range(16):
        if i == 5:
            apps.append(f'<div class="app"><span class="ic" style="background:{p["accent"]}">{logo(mark, on, height=40)}</span><em>{esc(name)}</em></div>')
        else:
            apps.append(f'<div class="app"><span class="ic" style="background:{mix(p["tint"], p["neutral"], (i % 5) / 8)}"></span><em></em></div>')
    return f"""<div class="phone" style="background:{mix(p['tint'], '#ffffff', .4)}">
      <div class="notch"></div><div class="time">9:41</div>
      <div class="note"><span class="ic sm" style="background:{p['accent']}">{logo(mark, on, height=20)}</span>
        <div><b>{esc(name)}</b><span>{esc(note)}</span></div></div>
      <div class="apps">{''.join(apps)}</div>
    </div>"""


def lum(hex_: str) -> float:
    h = hex_.lstrip("#")
    h = "".join(ch * 2 for ch in h) if len(h) == 3 else h  # #999 is #999999
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


CSS = """
@font-face { font-family: "Book"; src: url("fonts/book.ttf"); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; padding: 0; }
@page { size: 1600px 900px; margin: 0; }
body { background: #e9e9e9; font-family: "Book"; color: #161616; -webkit-font-smoothing: antialiased; }
section.page { position: relative; width: 1600px; height: 900px; overflow: hidden; background: #fff; break-after: page; margin: 0 auto 24px; }
@media print { body { background: none; } section.page { margin: 0; } }
.tile { position: absolute; border-radius: 22px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.foot { position: absolute; left: 64px; bottom: 40px; font-size: 13px; letter-spacing: -0.01em; opacity: .55; }
.num { position: absolute; right: 64px; bottom: 40px; font-size: 13px; opacity: .55; }
h1 { font-weight: 400; letter-spacing: -0.035em; line-height: .98; }
h2 { font-weight: 400; font-size: 64px; letter-spacing: -0.03em; line-height: 1; }
p.lede { font-size: 22px; line-height: 1.4; letter-spacing: -0.01em; }
section.page.cover { background: #161616; color: #fff; }
.cover .left { position: absolute; left: 0; top: 0; width: 50%; height: 100%; padding: 96px 104px; }
.cover .right { position: absolute; right: 0; top: 0; width: 50%; height: 100%; }
.cover h1 { position: absolute; left: 104px; bottom: 310px; font-size: 104px; }
.cover .sub { position: absolute; left: 104px; bottom: 250px; font-size: 52px; letter-spacing: -0.03em; color: #6f6f6f; }
.cover .kicker { font-size: 16px; color: #8a8a8a; letter-spacing: 0.02em; }
.three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px; position: absolute; left: 64px; right: 64px; top: 210px; }
.three .t { height: 360px; border-radius: 22px; display: flex; align-items: center; justify-content: center; }
.three h3 { font-weight: 500; font-size: 22px; letter-spacing: -0.02em; margin-top: 24px; }
.three p { font-size: 16px; line-height: 1.45; opacity: .7; margin-top: 8px; max-width: 420px; }
.label { position: absolute; left: 64px; top: 64px; }
.label .k { font-size: 15px; opacity: .55; margin-bottom: 10px; }
.browser { width: 560px; background: transparent; }
.browser .tabs { display: flex; align-items: flex-end; gap: 10px; padding-left: 26px; }
.browser .tabs i { width: 15px; height: 15px; border-radius: 50%; background: #fff; margin-bottom: 22px; }
.browser .tab { margin-left: 18px; display: flex; align-items: center; gap: 14px; background: #fff; border-radius: 16px 16px 0 0; padding: 12px 22px 12px 14px; font-size: 22px; letter-spacing: -0.01em; }
.browser .tab b { font-weight: 400; width: 190px; }
.browser .x { opacity: .55; font-size: 22px; }
.fav { width: 40px; height: 40px; border-radius: 9px; display: flex; align-items: center; justify-content: center; }
.browser .bar { background: #fff; border-radius: 16px; padding: 16px 22px; display: flex; align-items: center; gap: 26px; }
.browser .nav { font-size: 22px; opacity: .6; }
.browser .url { flex: 1; display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 6px; font-size: 19px; }
.poster { position: absolute; inset: 0; padding: 72px 68px; display: flex; flex-direction: column; justify-content: space-between; }
.poster h4 { font-weight: 500; font-size: 58px; letter-spacing: -0.03em; line-height: 1.04; }
.poster .lk { align-self: flex-end; }
.phone { width: 330px; height: 660px; border-radius: 48px; border: 10px solid #121212; position: relative; padding: 76px 24px 0; }
.phone .notch { position: absolute; left: 50%; top: 12px; width: 96px; height: 28px; border-radius: 14px; background: #121212; transform: translateX(-50%); }
.phone .time { position: absolute; left: 30px; top: 16px; font-size: 15px; font-weight: 600; }
.phone .note { display: flex; gap: 12px; align-items: center; background: rgba(255,255,255,.85); border-radius: 18px; padding: 12px 14px; margin-bottom: 28px; }
.phone .note b { display: block; font-size: 13px; font-weight: 600; }
.phone .note span { font-size: 12px; opacity: .75; line-height: 1.3; }
.phone .apps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px 12px; }
.phone .app { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.phone .ic { width: 60px; height: 60px; border-radius: 15px; display: flex; align-items: center; justify-content: center; }
.phone .ic.sm { width: 38px; height: 38px; border-radius: 10px; flex: none; }
.phone em { font-style: normal; font-size: 11px; height: 13px; }
.swatches { position: absolute; left: 450px; top: 76px; width: 1086px; height: 748px; background: #f1f1f1; border-radius: 22px; }
.sw { position: absolute; display: flex; align-items: flex-end; padding: 22px 26px; font-size: 20px; letter-spacing: -0.01em; box-shadow: 0 1px 0 rgba(0,0,0,.06); }
.sizes { position: absolute; left: 64px; right: 64px; top: 220px; display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 28px; }
.sizes .t { position: relative; height: 300px; border-radius: 22px; display: flex; align-items: flex-end; justify-content: center; gap: 44px; padding-bottom: 70px; }
.sizes .t small { position: absolute; left: 26px; top: 22px; font-size: 14px; opacity: .6; }
.sizes .t .cap { position: absolute; bottom: 26px; font-size: 13px; opacity: .55; }
.cmp { position: absolute; left: 64px; right: 64px; top: 200px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px; }
.cmp .t { height: 250px; border-radius: 22px; display: flex; align-items: center; justify-content: center; gap: 40px; }
.cmp table { width: 100%; border-collapse: collapse; margin-top: 22px; font-size: 15px; }
.cmp td { padding: 9px 0; border-bottom: 1px solid #e5e5e5; }
.cmp td:last-child { text-align: right; }
.grid { position: absolute; inset: 0; }
.credits { position: absolute; left: 64px; right: 64px; top: 200px; border-collapse: collapse; font-size: 15px; }
.credits td { padding: 12px 16px 12px 0; border-bottom: 1px solid #e5e5e5; word-break: break-all; }
.three p.prov { font-size: 13px; line-height: 1.4; opacity: .8; margin-top: 12px; white-space: pre-wrap; }
.three p.fail, .cmp p.fail { font-size: 14px; color: #b42318; opacity: 1; margin-top: 10px; }
.provtable { position: absolute; left: 610px; right: 64px; top: 190px; border-collapse: collapse; font-size: 16px; line-height: 1.4; }
.provtable td { padding: 12px 16px 12px 0; border-bottom: 1px solid #e5e5e5; vertical-align: top; }
.provtable td:first-child { width: 230px; opacity: .6; }
.provtable td.v { white-space: pre-wrap; word-break: break-word; }
.provtable td.sha { word-break: break-all; font-size: 14px; }
.unverified { position: absolute; left: 610px; right: 64px; bottom: 64px; font-size: 14px; opacity: .6; }
"""


def lockup(files: dict[str, str], fill: str, height: float, stacked: bool = False) -> str:
    """The lockup this build wrote, or its mark, larger, when it wrote none (a mark-only build)."""
    name = "lockup-stacked.svg" if stacked else "lockup.svg"
    if name in files:
        return logo(files[name], fill, height=height)
    return logo(files["mark.svg"], fill, height=height if stacked else height * 2.2)


def poster(p: dict, files: dict[str, str], tagline: str, img: str | None) -> str:
    """The tall poster tile: a photo with the tagline and lockup in paper over a dark foot, or, with no photos, the
    direction's colour field with ink type."""
    box = "left:1014px;top:30px;width:556px;height:840px;"
    if img:
        return (f'<div class="tile" style="{box}background:#000 url({img}) center/cover">'
                f'<div class="poster" style="background:linear-gradient(to top, rgba(0,0,0,.72) 0%, rgba(0,0,0,.25) 45%, rgba(0,0,0,0) 70%);justify-content:flex-end;gap:36px">'
                f'<h4 style="color:{p["paper"]}">{esc(tagline)}</h4><div class="lk">{lockup(files, p["paper"], 40)}</div></div></div>')
    return (f'<div class="tile" style="{box}{field(p)}"><div class="poster"><h4 style="color:{p["ink"]}">{esc(tagline)}</h4>'
            f'<div class="lk">{lockup(files, p["ink"], 40)}</div></div></div>')


def trace_lines(t: dict, traces: list[dict], scores: dict[str, float]) -> str:
    """The overview card's note on a traced direction: source, rights, score against the source, the answer."""
    out = []
    for tr in traces:
        ts, sha = tr["provenance"]["trace_source"], tr["trace"]["source_sha256"]
        score = t["score_line"].format(s=f"{scores[sha]:.3f}") if sha in scores else ""
        out.append(f'<p class="prov">{esc(t["traced"].format(file=ts["file"]))}\n{esc(t["rights"][ts["rights"]])}'
                   f'\n{esc(score)}\n\u201c{esc(ts["answer"])}\u201d</p>')
    return "".join(out)


def trace_page(t: dict, mark: str, p: dict, traces: list[dict], scores: dict[str, float], num: str) -> str:
    """A traced direction's page: its mark beside the person's statement about the source, verbatim."""
    rows = []
    for tr in traces:
        ts, sha = tr["provenance"]["trace_source"], tr["trace"]["source_sha256"]
        rows += [(t["source"], ts["file"], "v"), (t["sha"], sha, "sha"), (t["kind"], t["rights"][ts["rights"]], "v"),
                 (t["asked"], ts["question"], "v"), (t["answer"], ts["answer"], "v"),
                 (t["score"], f"{scores[sha]:.3f}" if sha in scores else "-", "v")]
    trs = "".join(f'<tr><td>{esc(k)}</td><td class="{c}">{esc(v)}</td></tr>' for k, v, c in rows)
    return (f'<div class="label"><h2>{esc(t["tracing"])}</h2></div>'
            f'<div class="tile" style="left:64px;top:190px;width:500px;height:646px;background:{p["paper"]}">'
            f'{logo(mark, p["ink"], height=230)}</div>'
            f'<table class="provtable">{trs}</table><p class="unverified">{esc(t["unverified"])}</p><div class="num">{num}</div>')


def page(num: str, body: str, cls: str = "", style: str = "") -> str:
    return f'<section class="page {cls}" id="p{num}" style="{style}">{body}</section>'


def credited(item: dict) -> bool:
    """A photo the credits page can name: its manifest entry has a creator, a licence and a source."""
    return all(isinstance(item.get(k), str) and item[k].strip() for k in ("creator", "license", "source"))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("builds", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--refs", nargs="+", required=True, help="the reference folders check_logo.py was given")
    ap.add_argument("--calibration", help="the calibration check_logo.py was given; default the one shipped here")
    ap.add_argument("--name", required=True)
    ap.add_argument("--line", required=True, help="what the product does, one line")
    ap.add_argument("--tagline", default=None)
    ap.add_argument("--note", default=None, help="the phone mockup's notification text; default: the tagline")
    ap.add_argument("--photos", default=None, help="a folder from fetch_photos.mjs: photos for the cover and posters, credited at the end")
    ap.add_argument("--brief", help="brief.json: the book is written in its language")
    ap.add_argument("--lang", choices=("en", "ko"), help="the book's language; default from --brief, else en")
    ap.add_argument("--include-failed", action="store_true", help="show directions that failed check_logo.py, marked as failed")
    ap.add_argument("--fonts", default=None, help="font cache; default ${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/fonts")
    a = ap.parse_args(argv)
    lang = a.lang or R.language(R.load_brief(a.brief)["data"] if a.brief else None)
    t = TEXT[lang]
    dirs = []
    for b in a.builds:
        build, chk, verified, traces = R.sealed(b, a.refs, a.calibration, require_ok=False)
        if not chk["ok"] and not a.include_failed:
            print(f"left out {b}: it failed check_logo.py (--include-failed shows it, marked)")
            continue
        scores = {sc["source_sha256"]: sc["score"] for sc in chk.get("source_scores", [])}
        files = {rel: data.decode() for rel, data in verified.items() if rel.endswith(".svg")}
        dirs.append((build, chk, traces, scores, files))
    if not dirs:
        raise SystemExit("no direction passed check_logo.py; fix the recipes, or pass --include-failed to show them marked")
    os.makedirs(os.path.join(a.out, "fonts"), exist_ok=True)
    info = F.fetch(BOOK_FONT[lang], a.fonts or os.path.join(R.cache_root(), "fonts"))
    shutil.copy(info["files"][0], os.path.join(a.out, "fonts", "book.ttf"))
    shutil.copy(info["licence"], os.path.join(a.out, "fonts", "OFL.txt"))
    tagline = a.tagline or a.line
    # Photos, copied in beside the book, used in turn: the cover, then each direction's poster.
    photos = []
    if a.photos:
        man = R.read_json(os.path.join(a.photos, "manifest.json"))
        os.makedirs(os.path.join(a.out, "photos"), exist_ok=True)
        for it in man["items"]:
            if not os.path.exists(os.path.join(a.photos, it["file"])):
                continue  # deleted as not fitting the brand (SKILL.md step 9): drop it, credit and all
            if not credited(it):
                print(f"left out photo {it['file']}: its manifest entry names no creator, licence and source to credit")
                continue
            shutil.copy(os.path.join(a.photos, it["file"]), os.path.join(a.out, "photos", it["file"]))
            photos.append(it)
    photo = lambda k: f"photos/{photos[k % len(photos)]['file']}" if photos else None  # noqa: E731
    pages, order = [], []

    def add(slug: str, make) -> None:
        """One more page; `make` takes the page's number, two digits, for its id and its corner. The number goes
        only where a template puts it, never into the person's words."""
        n = len(order) + 1
        order.append([n, slug])
        pages.append(make(f"{n:02d}"))

    p0, files0 = dirs[0][0]["palette"], dirs[0][4]
    add("cover", lambda N: page(N, f"""
      <div class="left"><div class="kicker">{esc(a.line)}</div></div>
      <h1>{esc(a.name)}</h1><div class="sub">{esc(t["logo_directions"])}</div>
      {f'<div class="right" style="background:#000 url({photo(0)}) center/cover"></div>' if photos else
       f'<div class="right" style="{field(p0)}display:flex;align-items:center;justify-content:center">{logo(files0["mark.svg"], p0["ink"], height=300)}</div>'}
    """, "cover"))

    count = t["direction"] if len(dirs) == 1 else t["directions"].format(n=len(dirs))
    cards = []
    for build, chk, traces, scores, files in dirs:
        p = build["palette"]
        fail = "" if chk["ok"] else f'<p class="fail">{esc(t["failed"])}</p>'
        cards.append(f"""<div><div class="t" style="background:{p['paper']}">{logo(files['mark.svg'], p['ink'], height=150)}</div>
          <h3>{esc(build.get('title', ''))}</h3><p>{esc(build.get('idea', ''))}</p>{trace_lines(t, traces, scores)}{fail}</div>""")
    # Three to a page, like side by side: six cards on one page leave no room around the marks.
    for k in range(0, len(cards), 3):
        add(f"directions-{k // 3 + 1}", lambda N: page(N, f"""<div class="label"><h2>{esc(count)}</h2></div>
      <div class="three">{''.join(cards[k:k + 3])}</div><div class="foot">{esc(a.line)}</div><div class="num">{N}</div>"""))

    for i, (build, chk, traces, scores, files) in enumerate(dirs, 1):
        p = build["palette"]
        dark = p["ink"]
        m = files["mark.svg"]
        # Spread A: in use. A dark lockup, a browser tab, a poster.
        add(f"d{i}-use", lambda N: page(N, f"""
          <div class="tile" style="left:30px;top:30px;width:954px;height:400px;background:{dark}">{lockup(files, p['paper'], 64)}</div>
          <div class="tile" style="left:30px;top:460px;width:954px;height:410px;background:{p['tint']}">{browser(a.name, m, p)}</div>
          {poster(p, files, tagline, photo(i))}"""))
        # Spread B: construction. A light lockup, the grid, a phone.
        add(f"d{i}-build", lambda N: page(N, f"""
          <div class="tile" style="left:30px;top:30px;width:954px;height:400px;background:{p['paper']}">{lockup(files, dark, 64)}</div>
          <div class="tile" style="left:30px;top:460px;width:954px;height:410px;background:{dark}">{construction(build, files, p, 954, 410)}</div>
          <div class="tile" style="left:1014px;top:30px;width:556px;height:840px;background:{p['neutral']}">{phone(a.name, m, p, a.note or tagline)}</div>"""))
        if traces:
            add(f"d{i}-trace", lambda N: page(N, trace_page(t, m, p, traces, scores, N)))
        # Colour.
        sw = [("paper", 36, 32, 336, 684), ("accent", 400, 32, 336, 296), ("tint", 764, 32, 286, 136), ("neutral", 764, 196, 286, 132), ("ink", 400, 356, 650, 360)]
        cells = "".join(
            f'<div class="sw" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{p[k]};color:{"#161616" if lum(p[k]) > .3 else "#ffffff"}">{p[k].upper()}</div>'
            for k, x, y, w, h in sw)
        add(f"d{i}-colour", lambda N: page(N, f"""<div class="label"><h2>{esc(t["colour"])}</h2></div>
          <div class="swatches">{cells}</div><div class="num">{N}</div>"""))
        # Small sizes and versions.
        sizes = "".join(f'<div style="display:flex;flex-direction:column;align-items:center;gap:10px">{logo(m, dark, height=s)}<span style="font-size:12px;opacity:.55">{s}px</span></div>' for s in (16, 24, 32, 64))
        stroke = next((c["value"] for c in chk.get("checks", []) if c["check"] == "stroke at 16 px"), t["not_checked"])
        add(f"d{i}-sizes", lambda N: page(N, f"""<div class="label"><h2>{esc(t["sizes"])}</h2></div>
          <div class="sizes">
            <div class="t" style="background:{p['paper']}"><small>{esc(t["small"])}</small>{sizes}<span class="cap">{esc(t["stroke"].format(v=stroke))}</span></div>
            <div class="t" style="background:{dark};align-items:center;padding:0">{logo(m, p['paper'], height=120)}<small style="color:{p['paper']}">{esc(t["reversed"])}</small></div>
            <div class="t" style="background:{p['accent']};align-items:center;padding:0">{logo(m, dark if lum(p['accent']) > .45 else '#ffffff', height=120)}<small>{esc(t["on_colour"])}</small></div>
          </div>
          <div class="tile" style="left:64px;right:64px;top:550px;height:290px;background:{p['tint']}">{lockup(files, dark, 170, stacked=True)}</div>
          <div class="num">{N}</div>"""))

    rows = []
    for build, chk, traces, scores, files in dirs:
        p = build["palette"]
        checks = [(t["check_names"].get(c["check"], c["check"]), f"{c['value']} {'✓' if c['ok'] else '✗'}") for c in chk.get("checks", [])]
        checks += [(t["score"], f"{s:.3f}") for s in scores.values()]
        trs = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in checks) or f"<tr><td>{esc(t['checks'])}</td><td>{esc(t['not_run'])}</td></tr>"
        fail = "" if chk["ok"] else f'<p class="fail">{esc(t["failed"])}</p>'
        rows.append(f"""<div><div class="t" style="background:{p['paper']}">{logo(files['mark.svg'], p['ink'], height=110)}{logo(files['mark.svg'], p['ink'], height=16)}</div>
          <h3 style="font-weight:500;font-size:20px;margin-top:22px">{esc(build.get('title', ''))}</h3>{fail}<table>{trs}</table></div>""")
    # Three to a page: six on one page left the tiles cramped and the checks cut down.
    for k in range(0, len(rows), 3):
        add(f"compare-{k // 3 + 1}", lambda N: page(N, f"""<div class="label"><h2>{esc(t["side"])}</h2></div>
      <div class="cmp">{''.join(rows[k:k + 3])}</div><div class="num">{N}</div>"""))
    if photos:
        lines = "".join(f'<tr><td>{esc(it.get("title") or t["photo"])}</td><td>{esc(it["creator"])}</td><td>{esc(it["license"])}</td><td>{esc(it["source"])}</td></tr>' for it in photos)
        add("credits", lambda N: page(N, f"""<div class="label"><h2>{esc(t["photos"])}</h2></div>
      <table class="credits">{lines}</table>"""))

    doc = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{esc(t["title"].format(name=a.name))}</title>'
           f'<style>{CSS}</style></head><body>{"".join(pages)}</body></html>')
    R.write_bytes(os.path.join(a.out, "index.html"), doc.encode())
    R.write_bytes(os.path.join(a.out, "pages.json"), json.dumps({"family": "Book", "name": a.name, "lang": lang, "pages": order}, indent=1, ensure_ascii=False).encode())
    print(f"wrote {len(order)} pages to {a.out}")


if __name__ == "__main__":
    main()
