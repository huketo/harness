# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools", "uharfbuzz"]
# ///
"""OFL fonts for wordmarks (references/building.md): fetched from the Google Fonts repository with their licence, set
with HarfBuzz, outlined. A wordmark is the font's outlines, so the font's OFL.txt ships in the package's LICENSES.
"""
from __future__ import annotations

import io
import os
import re
import urllib.request

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RAW = "https://raw.githubusercontent.com/google/fonts/main"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "make-logo/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _save(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


def _text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def fetch(family: str, cache: str) -> dict:
    """The family's upright file and OFL.txt, cached. Raises if it isn't an OFL family on Google Fonts."""
    slug = re.sub(r"[^a-z0-9]", "", family.lower())
    d = os.path.join(cache, slug)
    os.makedirs(d, exist_ok=True)
    meta_path = os.path.join(d, "METADATA.pb")
    if not os.path.exists(meta_path):
        try:
            _save(meta_path, _get(f"{RAW}/ofl/{slug}/METADATA.pb"))
        except Exception as e:
            raise SystemExit(f'"{family}" is not an OFL family on Google Fonts ({e})')
    meta = _text(meta_path)
    files = re.findall(r'style: "normal"\s+weight: \d+\s+filename: "([^"]+)"', meta)
    if not files:
        raise SystemExit(f'"{family}" has no upright file')
    out = {"family": family, "slug": slug, "files": [], "licence": os.path.join(d, "OFL.txt")}
    for f in dict.fromkeys(files):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            _save(p, _get(f"{RAW}/ofl/{slug}/{urllib.request.quote(f)}"))
        out["files"].append(p)
    if not os.path.exists(out["licence"]):
        _save(out["licence"], _get(f"{RAW}/ofl/{slug}/OFL.txt"))
    lic = _text(out["licence"])
    out["reserved_names"] = reserved_font_names(lic)
    return out


def reserved_font_names(ofl_text: str) -> list[str]:
    """The Reserved Font Names an OFL declares, in order. Only copyright notice lines count (a line starting with
    "Copyright", any case, after optional whitespace), from "with Reserved Font Name(s)" to the end of that sentence;
    the licence body's own definition of the term names nothing."""
    names: list[str] = []
    for line in ofl_text.splitlines():
        if not re.match(r"\s*copyright\b", line, re.I):
            continue
        m = re.search(r"\bwith\s+Reserved\s+Font\s+Names?\b(.*)", line, re.I)
        if not m:
            continue
        rest = m.group(1)
        # The sentence ends at the first full stop outside quotes that ends the line or comes before a space.
        quote, end = None, len(rest)
        for i, ch in enumerate(rest):
            if quote:
                quote = None if ch == quote or (quote == "\u201c" and ch == "\u201d") else quote
            elif ch in "\"\u201c":
                quote = ch
            elif ch == "." and (i + 1 == len(rest) or rest[i + 1].isspace()):
                end = i
                break
        sentence = rest[:end]
        quoted = re.findall(r'"([^"]+)"|\u201c([^\u201d]+)\u201d', sentence)
        if quoted:
            names += [a or b for a, b in quoted]
        else:
            parts = re.split(r",|\band\b", sentence)
            names += [p.strip().strip("'\u2018\u2019").strip() for p in parts if p.strip().strip("'\u2018\u2019").strip()]
    return names


def load(info: dict, weight: int) -> TTFont:
    """The family at a weight: a variable file instanced, or the static file nearest the weight."""
    for p in info["files"]:
        f = TTFont(p)
        if "fvar" in f:
            axes = {a.axisTag: a for a in f["fvar"].axes}
            loc = {}
            if "wght" in axes:
                loc["wght"] = max(axes["wght"].minValue, min(axes["wght"].maxValue, weight))
            for tag, a in axes.items():
                loc.setdefault(tag, a.defaultValue)
            return instancer.instantiateVariableFont(f, loc)
    best = min(info["files"], key=lambda p: abs(TTFont(p)["OS/2"].usWeightClass - weight))
    return TTFont(best)


def set_text(font: TTFont, text: str, tracking: float = 0.0) -> dict:
    """Shape `text` and return its outlines as a recording in font units (y up), with metrics. `tracking` is in
    thousandths of the em, added after every glyph but the last."""
    import uharfbuzz as hb

    buf = io.BytesIO()
    font.save(buf)
    blob = hb.Blob(buf.getvalue())
    hfont = hb.Font(hb.Face(blob))
    upem = font["head"].unitsPerEm
    hfont.scale = (upem, upem)
    b = hb.Buffer()
    b.add_str(text)
    b.guess_segment_properties()
    hb.shape(hfont, b, {"kern": True, "liga": True})
    gs = font.getGlyphSet()
    order = font.getGlyphOrder()
    rec = DecomposingRecordingPen(gs)
    x = 0.0
    track = tracking * upem / 1000
    for k, (info, pos) in enumerate(zip(b.glyph_infos, b.glyph_positions)):
        name = order[info.codepoint]
        gs[name].draw(TransformPen(rec, (1, 0, 0, 1, x + pos.x_offset, pos.y_offset)))
        x += pos.x_advance + (track if k < len(b.glyph_infos) - 1 else 0)
    os2 = font["OS/2"]
    return {"pen": rec, "advance": x, "upem": upem, "cap": getattr(os2, "sCapHeight", 0) or upem * 0.7,
            "xheight": getattr(os2, "sxHeight", 0) or upem * 0.5}
