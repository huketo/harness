# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "fonttools"]
# ///
"""Synthetic fixtures for the make-logo gate tests (test_*.py): marks drawn with Pillow, a font built with fontTools'
FontBuilder, and a throwaway workspace with its own XDG_CACHE_HOME. Nothing is downloaded."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import potrace_bin as P  # noqa: E402
import rights as R  # noqa: E402

# Found before any test points XDG_CACHE_HOME at a temporary folder, with the same resolver the scripts use.
POTRACE = P.find()
needs_potrace = unittest.skipUnless(POTRACE, "potrace_bin.find() found no potrace on PATH or in the make-logo cache")

QUESTION = "Do you hold the rights to this file, so make-logo may trace it into your mark?"
ANSWER = "synthetic test approval: not a real person's answer"


def canvas(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (w, h), "white")
    return im, ImageDraw.Draw(im)


def external(d: ImageDraw.ImageDraw, x: float, y: float, s: float) -> None:
    """Somebody else's mark: a ring with a wedge cut out and a bar through it."""
    d.ellipse([x, y, x + s, y + s], fill="black")
    d.ellipse([x + s * 0.22, y + s * 0.22, x + s * 0.78, y + s * 0.78], fill="white")
    d.pieslice([x - 2, y - 2, x + s + 2, y + s + 2], -80, -10, fill="white")
    d.rectangle([x + s * 0.05, y + s * 0.44, x + s * 0.62, y + s * 0.56], fill="black")


def own(d: ImageDraw.ImageDraw, x: float, y: float, s: float) -> None:
    """The person's own sketch: an L with a flag."""
    d.rectangle([x + s * 0.1, y, x + s * 0.35, y + s], fill="black")
    d.rectangle([x + s * 0.1, y + s * 0.75, x + s * 0.9, y + s], fill="black")
    d.polygon([(x + s * 0.5, y + s * 0.1), (x + s * 0.9, y + s * 0.1), (x + s * 0.9, y + s * 0.5)], fill="black")


def badge(d: ImageDraw.ImageDraw, x: float, y: float, s: float) -> None:
    """Another studio's mark, unlike `external`: a triangle with a round hole."""
    d.polygon([(x, y + s), (x + s / 2, y), (x + s, y + s)], fill="black")
    d.ellipse([x + s * 0.38, y + s * 0.5, x + s * 0.62, y + s * 0.74], fill="white")


def tee(d: ImageDraw.ImageDraw, x: float, y: float, s: float) -> None:
    """A plain T, used by no other fixture."""
    d.rectangle([x, y, x + s, y + s * 0.25], fill="black")
    d.rectangle([x + s * 0.38, y, x + s * 0.62, y + s], fill="black")


def tight(im: Image.Image) -> Image.Image:
    """The picture cropped to its ink, so the mark touches every edge: a logo cut close out of a screenshot, which
    logolib.usable() rejects for measuring ("ink fills the frame")."""
    return im.crop(ImageOps.invert(im.convert("L")).getbbox())


def padded(im: Image.Image, margin: int = 120) -> Image.Image:
    out = Image.new("RGB", (im.width + 2 * margin, im.height + 2 * margin), "white")
    out.paste(im, (margin, margin))
    return out


def halftone(d: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, dot: int = 7, pitch: int = 9) -> None:
    """A field of dots each under potrace's --turdsize 60, close enough to read as solid ink at the distance check's
    128 px."""
    for y in range(y0, y1, pitch):
        for x in range(x0, x1, pitch):
            d.rectangle([x, y, x + dot - 1, y + dot - 1], fill="black")


def mark_image(draw, side: int = 600) -> Image.Image:
    im, d = canvas(side, side)
    draw(d, side / 6, side / 6, side * 2 / 3)
    return im


def badge_svg(side: int = 600) -> bytes:
    """`badge` as an SVG file the way logo collections hold them: paths on a transparent ground."""
    x = y = side / 6
    s = side * 2 / 3
    return (f'<?xml version="1.0" encoding="iso-8859-1"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {side} {side}"><polygon points="{x},{y + s} {x + s / 2},{y} {x + s},{y + s}"/>'
            f'<circle cx="{x + s / 2}" cy="{y + s * 0.62}" r="{s * 0.12}" fill="#ffffff"/></svg>\n').encode()


def light_on_clear(im: Image.Image, grey: int = 226) -> Image.Image:
    """A dark-on-white mark repainted light grey on a transparent ground: a logo meant for dark backgrounds, which
    shows almost nothing once flattened onto white."""
    ink = im.convert("L").point(lambda v: 255 if v < 128 else 0)
    out = Image.new("RGBA", im.size, (grey, grey, grey, 0))
    out.putalpha(ink)
    return out


def dark_and_light_on_clear(dark: Image.Image, light: Image.Image) -> Image.Image:
    """Two marks side by side on one transparent ground, `dark` in black and `light` in light grey: a sheet with a
    logo for each ground. Flattened onto white only the dark one shows; onto black only the light one."""
    out = Image.new("RGBA", (dark.width + light.width, max(dark.height, light.height)), (0, 0, 0, 0))
    out.alpha_composite(light_on_clear(dark, grey=0), (0, 0))
    out.alpha_composite(light_on_clear(light), (dark.width, 0))
    return out


SMALL_MARK_BOX = (900, 300, 924, 324)  # where dark_mark_and_small_light_mark() puts its small mark, padded


def dark_mark_and_small_light_mark() -> Image.Image:
    """A 1200 x 600 transparent sheet: a large dark `tee` and, far from it, `badge` 16 px across in light grey.
    Flattened onto white only the tee shows; onto black only the badge, which logolib.segment() drops as a speck."""
    out = Image.new("RGBA", (1200, 600), (0, 0, 0, 0))
    out.alpha_composite(light_on_clear(mark_image(tee, 500), grey=0), (50, 50))
    x0, y0, x1, _ = SMALL_MARK_BOX
    out.alpha_composite(light_on_clear(mark_image(badge, x1 - x0)), (x0, y0))
    return out


def font_bytes(family: str) -> bytes:
    """A TrueType font whose letters are plain boxes: enough for HarfBuzz to shape and for outlines to exist."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    chars = [chr(c) for c in range(ord("A"), ord("Z") + 1)] + [chr(c) for c in range(ord("a"), ord("z") + 1)]
    order = [".notdef", "space"] + [f"g{ord(c):04X}" for c in chars]

    def box(h: int):
        pen = TTGlyphPen(None)
        pen.moveTo((50, 0)); pen.lineTo((50, h)); pen.lineTo((450, h)); pen.lineTo((450, 0)); pen.closePath()
        return pen.glyph()

    glyphs = {".notdef": box(700), "space": TTGlyphPen(None).glyph()}
    glyphs.update({f"g{ord(c):04X}": box(700 if c.isupper() else 500) for c in chars})
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({ord(" "): "space", **{ord(c): f"g{ord(c):04X}" for c in chars}})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (500, 0 if n == "space" else 50) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200, sCapHeight=700,
                sxHeight=500, usWeightClass=400)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def write(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


def install_font(cache: str, family: str, copyright_line: str | None = None) -> None:
    """Put a synthetic family where fonts.fetch() looks first, so it never goes to the network."""
    slug = "".join(ch for ch in family.lower() if ch.isalnum())
    d = os.path.join(cache, slug)
    os.makedirs(d, exist_ok=True)
    fname = family.replace(" ", "") + "-Regular.ttf"
    line = copyright_line or f"Copyright 2026 The {family} Project Authors"
    meta = f'name: "{family}"\nfonts {{\n  name: "{family}"\n  style: "normal"\n  weight: 400\n  filename: "{fname}"\n}}\n'
    write(os.path.join(d, fname), font_bytes(family))
    write(os.path.join(d, "METADATA.pb"), meta.encode())
    write(os.path.join(d, "OFL.txt"), (line + "\n" + OFL_BODY).encode())


class Workspace:
    """A temporary project folder with its own cache: collections, references, a brief, fonts. close() removes it."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="make-logo-test-")
        env = {"XDG_CACHE_HOME": os.path.join(self.root, "cache")}
        if POTRACE:
            env["PATH"] = os.path.dirname(POTRACE) + os.pathsep + os.environ.get("PATH", "")
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        self.fonts = os.path.join(self.root, "fonts")
        for family in ("Tessera Sans", "Inter Tight", "Noto Sans KR"):
            install_font(self.fonts, family)

    def close(self) -> None:
        self._env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def path(self, *parts: str) -> str:
        p = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def image(self, rel: str, im: Image.Image, fmt: str = "PNG", **save) -> str:
        p = self.path(rel)
        im.save(p, fmt, **save)
        return p

    def collection(self, name: str, files: dict[str, Image.Image | bytes]) -> str:
        """A collection as fetch_arena.mjs leaves it: files under the cache and a manifest with every sha256. A
        picture is saved as PNG; bytes are written as they are."""
        d = os.path.join(R.cache_root(), name)
        items = []
        for rel, im in files.items():
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if isinstance(im, bytes):
                write(p, im)
            else:
                im.save(p, "PNG")
            items.append({"id": rel, "file": rel, "sha256": R.sha256_file(p)})
        write(os.path.join(d, "manifest.json"), json.dumps({"fetched": "2026-11-20T00:00:00Z", "items": items}).encode())
        return d

    def entry(self, path: str, rights: str = "own-drawing") -> dict:
        return {"file": os.path.relpath(path, self.root), "sha256": R.sha256_file(path), "rights": rights,
                "question": QUESTION, "answer": ANSWER}

    def brief(self, entries: list[dict], **fields) -> str:
        p = self.path("brief.json")
        brief = {"name": "Tessera", "what": "a synthetic test product", **fields, "trace_sources": entries}
        write(p, json.dumps(brief, indent=1, ensure_ascii=False).encode())
        return p


OFL_BODY = """
This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.
"""
