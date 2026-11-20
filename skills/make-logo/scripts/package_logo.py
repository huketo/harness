# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "resvg-py"]
# ///
"""Package a chosen direction (references/building.md, "Package").

    uv run package_logo.py <build dir> --out <new dir> --refs <ref folder> [...] [--calibration calibration.json]
        [--brief brief.json] [--lang en|ko] [--classes "9, 42"]

svg/ (mark, wordmark, lockup, stacked; ink, reversed, accent, black), png/ (the mark at 16 to 1024 and the lockup),
favicon.ico, LICENSES/ (each font's OFL.txt), trademark-search.md, brand.json.

It goes on only while the build's check still holds: check.json exists and passed, and build.json, every file it
lists, the --refs images and the calibration still have the sha256 check.json recorded. It reads only the files
build.json lists, and writes into a new folder. The trademark sheet is in the brief's language (Korean for a Korean
brief) and says where a traced mark came from, in the person's own words.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

import resvg_py
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rights as R  # noqa: E402

PARTS = ("mark", "wordmark", "lockup", "lockup-stacked")
PNG = (16, 32, 48, 180, 512, 1024)

# The one sentence the sheet says about the distance check, chosen by whether the mark was traced.
CHECKED = {
    "en": {
        "drawn": "The mark was built from grid shapes and fonts and compared with every reference used to make it, "
                 "and it was not a near copy of any of them (`check.json`), which covers those references only, not "
                 "every mark in use.",
        "traced": "The mark was compared with every reference used to make it except the traced source above, and it "
                  "was not a near copy of any of them (`check.json`), which covers those references only, not every "
                  "mark in use.",
    },
    "ko": {
        "drawn": "이 마크는 격자 도형과 글꼴로 만들었고, 만드는 데 쓴 참고 로고 전부와 비교했을 때 어느 것과도 지나치게 "
                 "가깝지 않았지만(`check.json`), 이 결과는 그 참고 로고들에만 해당하며 사용 중인 모든 상표를 확인한 "
                 "것은 아닙니다.",
        "traced": "이 마크는 위의 트레이싱 원본을 뺀 나머지 참고 로고 전부와 비교했을 때 어느 것과도 지나치게 가깝지 "
                  "않았지만(`check.json`), 이 결과는 그 참고 로고들에만 해당하며 사용 중인 모든 상표를 확인한 것은 "
                  "아닙니다.",
    },
}

RIGHTS = {
    "en": {"own-drawing": "the person's own drawing", "own-brand": "the person's own brand", "licensed": "licensed to the person"},
    "ko": {"own-drawing": "사용자가 직접 그린 그림", "own-brand": "사용자 자신의 브랜드", "licensed": "사용자가 이용 허락을 받은 자료"},
}


def recolour(svg: str, fill: str) -> str:
    return re.sub(r'fill="#[0-9a-fA-F]{6}"', f'fill="{fill}"', svg)


def png(svg: str, width: int) -> Image.Image:
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width)))).convert("RGBA")


def square(im: Image.Image, side: int, pad: float = 0.1) -> Image.Image:
    """The mark centred on a transparent square with `pad` of clear space each side."""
    inner = round(side * (1 - 2 * pad))
    im = im.copy()
    im.thumbnail((inner, inner), Image.LANCZOS)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    return out


def quote(text: str) -> str:
    """The person's words as a Markdown quote, every line kept."""
    return "\n".join("> " + line if line else ">" for line in text.splitlines() or [""])


def provenance(lang: str, traces: list[dict], scores: dict[str, float]) -> str:
    out = []
    for t in traces:
        ts, sha = t["provenance"]["trace_source"], t["trace"]["source_sha256"]
        score = f"{scores[sha]:.3f}" if sha in scores else "-"
        if lang == "ko":
            out.append(f"""## 마크의 출처

이 마크는 사용자가 권리를 가지고 있다고 답한 파일을 트레이싱한 뒤 격자 도형으로 고친 것입니다.

- 원본 파일: `{ts['file']}` (sha256 `{sha}`)
- 권리 유형: {RIGHTS['ko'][ts['rights']]} (`{ts['rights']}`)
- 원본과의 점수: {score} (표시만 하며, 통과 여부를 정하지 않습니다)

사용자에게 보인 질문(원문):

{quote(ts['question'])}

사용자의 답(원문):

{quote(ts['answer'])}

make-logo는 이 진술을 기록하고 원본 파일의 해시에 묶었을 뿐이며, 진술이 사실인지는 확인하지 않았습니다.
""")
        else:
            out.append(f"""## Where the mark came from

The mark was traced from a file the person said they hold the rights to, then changed with grid shapes.

- Source file: `{ts['file']}` (sha256 `{sha}`)
- Rights: {RIGHTS['en'][ts['rights']]} (`{ts['rights']}`)
- Score against the source: {score} (shown, not a pass or a fail)

The question they were shown, verbatim:

{quote(ts['question'])}

Their answer, verbatim:

{quote(ts['answer'])}

make-logo recorded this statement and bound it to the source file's hash; it did not verify it.
""")
    return "\n".join(out)


def sheet(lang: str, name: str, classes: str, shapes: str, traces: list[dict], scores: dict[str, float]) -> str:
    said = CHECKED[lang]["traced" if traces else "drawn"]
    came = provenance(lang, traces, scores)
    if lang == "ko":
        return f"""# 상표 검색 안내: {name}

이 문서는 상표 등록이나 사용이 가능하다고 확인해 주는 문서가 아닙니다. 이름과 마크를 사업에 쓰기 전에 찾아볼 곳을
정리한 것이므로, 출원하거나 브랜드에 비용을 쓰기 전에 변리사에게 선행 상표 조사를 받으세요.

{came}
## 한국 특허청(KIPRIS)

- KIPRIS 상표 검색: https://www.kipris.or.kr/ 에서 "상표"를 고른 뒤 "{name}"을 한글, 영문, 비슷한 발음으로 검색합니다.
- 도형이 들어간 상표는 KIPRIS의 도형 분류(비엔나 분류) 코드로도 검색합니다. 이 마크를 이루는 도형: {shapes}.
- 지정상품 분류(니스 분류): {classes or "판매하는 상품과 서비스의 분류(소프트웨어는 보통 제9류와 제42류)"}

## 해외

- WIPO Global Brand Database: https://branddb.wipo.int/ (판매하는 모든 나라)
- USPTO 상표 검색: https://tmsearch.uspto.gov/
- EUIPO eSearch: https://euipo.europa.eu/eSearch/

같은 분류에서 한눈에 같아 보이는 마크가 있는지 살펴봅니다.

## make-logo가 확인한 것

{said}
"""
    return f"""# Trademark search sheet: {name}

This is not a clearance. It lists where to look before you use the name and mark in commerce. Get a clearance search
from a trademark lawyer before you file or spend money on the brand.

{came}
## The name

- USPTO trademark search: https://tmsearch.uspto.gov/ (search "{name}" and close spellings)
- WIPO Global Brand Database: https://branddb.wipo.int/ (all countries you sell in)
- EUIPO eSearch: https://euipo.europa.eu/eSearch/
- KIPRIS, the Korean Intellectual Property Office's search: https://www.kipris.or.kr/ (Korea; search the name in Hangul too)
- Classes to search: {classes or "the Nice classes for what you sell (software is usually 9 and 42)"}

## The mark

Search the design codes (the Vienna Classification in WIPO's database and KIPRIS, the USPTO's design search codes) for
the shapes the mark is built from: {shapes}. Look for marks in the same classes that would read as the same at a glance.

## What make-logo checked

{said}
"""


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("build")
    ap.add_argument("--out", required=True, help="a new or empty folder")
    ap.add_argument("--refs", nargs="+", required=True, help="the reference folders check_logo.py was given")
    ap.add_argument("--calibration", help="the calibration check_logo.py was given; default the one shipped here")
    ap.add_argument("--brief", help="brief.json: the sheet is written in its language")
    ap.add_argument("--lang", choices=("en", "ko"), help="the sheet's language; default from --brief, else en")
    ap.add_argument("--classes", default="", help="Nice classes for the trademark search sheet, e.g. \"9, 42\"")
    a = ap.parse_args(argv)
    info, chk = R.sealed(a.build, a.refs, a.calibration)
    if os.path.isdir(a.out) and os.listdir(a.out):
        raise SystemExit(f"{a.out} already holds files; package into a new folder so nothing from before is mixed in")
    lang = a.lang or R.language(R.load_brief(a.brief)["data"] if a.brief else None)
    files = info["files"]
    listed = lambda rel: R.inside(a.build, rel) if rel in files else None  # noqa: E731
    read = lambda rel: R.read_bytes(listed(rel)).decode()  # noqa: E731

    pal = info.get("palette", {})
    colours = {"ink": pal.get("ink", "#151515"), "reversed": pal.get("paper", "#ffffff"), "accent": pal.get("accent", pal.get("ink", "#151515")), "black": "#000000"}
    os.makedirs(os.path.join(a.out, "svg"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "png"), exist_ok=True)
    for part in PARTS:
        if not listed(f"{part}.svg"):
            continue
        s = read(f"{part}.svg")
        for name, fill in colours.items():
            R.write_bytes(os.path.join(a.out, "svg", f"{part}-{name}.svg"), recolour(s, fill).encode())
    big = png(recolour(read("mark.svg"), colours["ink"]), 2048)
    for side in PNG:
        square(big, side).save(os.path.join(a.out, "png", f"mark-{side}.png"))
    if listed("lockup.svg"):
        png(recolour(read("lockup.svg"), colours["ink"]), 1600).save(os.path.join(a.out, "png", "lockup-1600.png"))
    square(big, 256).save(os.path.join(a.out, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    os.makedirs(os.path.join(a.out, "LICENSES"), exist_ok=True)
    for family, rel in info.get("fonts", {}).items():
        R.write_bytes(os.path.join(a.out, "LICENSES", os.path.basename(rel)), R.read_bytes(listed(rel)))

    traces = R.traces(a.build, info)
    scores = {s["source_sha256"]: s["score"] for s in chk.get("source_scores", [])}
    shapes = ", ".join(sorted({s for s in ("circles" if '"circle"' in json.dumps(info) else "", "squares and rectangles") if s}))
    if lang == "ko":
        shapes = shapes.replace("circles", "원").replace("squares and rectangles", "정사각형과 직사각형")
    name = info["name"]
    R.write_bytes(os.path.join(a.out, "trademark-search.md"), sheet(lang, name, a.classes, shapes, traces, scores).encode())
    brand = {"name": name, "direction": info.get("title"), "palette": pal, "fonts": list(info.get("fonts", {})),
             "traces": [{"file": t["provenance"]["trace_source"]["file"], "sha256": t["trace"]["source_sha256"],
                              "rights": t["trace"]["rights"], "answer": t["trace"]["answer"]} for t in traces]}
    R.write_bytes(os.path.join(a.out, "brand.json"), json.dumps(brand, indent=1, ensure_ascii=False).encode())
    print(f"packaged {name} ({info.get('title')}) into {a.out}")


if __name__ == "__main__":
    main()
