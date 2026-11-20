# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools"]
# ///
"""Synthetic fixtures for the make-font gate tests: fonts drawn with FontBuilder and the OFL-1.1 text.

No downloaded font is used. Every font here is made of rectangles, so its numbers are known: cap height 700,
x-height 500, an n with two stems, an o and an O with a hole, a b that rises to 740 and a p that falls to -220
(the font book reads its ascender and descender from them), and a weight axis that thickens the stems.
"""
import os
import re
import subprocess
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables.TupleVariation import TupleVariation

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_FAMILY = "Lumen Ledger"
NEW_FAMILY = "Tessera Sans"
OFL_NOTICE = ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
              "This license is available with a FAQ at: https://openfontlicense.org")
APACHE_NOTICE = "Licensed under the Apache License, Version 2.0"
OFL_10_NOTICE = "This Font Software is licensed under the SIL Open Font License, Version 1.0."
APACHE_TEXT = ("\n                                 Apache License\n                           Version 2.0, January 2004\n"
               "                        http://www.apache.org/licenses/\n\n"
               "   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n")
SYNTHETIC_QUESTION = "Synthetic test approval: build on the Lumen Ledger fixture under the OFL-1.1?"
SYNTHETIC_ANSWER = "synthetic e2e approval: yes, use it"

# The SIL Open Font License 1.1, preamble and body, unmodified, as it follows the copyright line in an OFL.txt.
OFL_BODY = "\n".join([
    "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
    "This license is copied below, and is also available with a FAQ at:",
    "https://scripts.sil.org/OFL",
    "",
    "",
    "-----------------------------------------------------------",
    "SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007",
    "-----------------------------------------------------------",
    "",
    "PREAMBLE",
    "The goals of the Open Font License (OFL) are to stimulate worldwide",
    "development of collaborative font projects, to support the font creation",
    "efforts of academic and linguistic communities, and to provide a free and",
    "open framework in which fonts may be shared and improved in partnership",
    "with others.",
    "",
    "The OFL allows the licensed fonts to be used, studied, modified and",
    "redistributed freely as long as they are not sold by themselves. The",
    "fonts, including any derivative works, can be bundled, embedded, ",
    "redistributed and/or sold with any software provided that any reserved",
    "names are not used by derivative works. The fonts and derivatives,",
    "however, cannot be released under any other type of license. The",
    "requirement for fonts to remain under this license does not apply",
    "to any document created using the fonts or their derivatives.",
    "",
    "DEFINITIONS",
    '"Font Software" refers to the set of files released by the Copyright',
    "Holder(s) under this license and clearly marked as such. This may",
    "include source files, build scripts and documentation.",
    "",
    '"Reserved Font Name" refers to any names specified as such after the',
    "copyright statement(s).",
    "",
    '"Original Version" refers to the collection of Font Software components as',
    "distributed by the Copyright Holder(s).",
    "",
    '"Modified Version" refers to any derivative made by adding to, deleting,',
    "or substituting -- in part or in whole -- any of the components of the",
    "Original Version, by changing formats or by porting the Font Software to a",
    "new environment.",
    "",
    '"Author" refers to any designer, engineer, programmer, technical',
    "writer or other person who contributed to the Font Software.",
    "",
    "PERMISSION & CONDITIONS",
    "Permission is hereby granted, free of charge, to any person obtaining",
    "a copy of the Font Software, to use, study, copy, merge, embed, modify,",
    "redistribute, and sell modified and unmodified copies of the Font",
    "Software, subject to the following conditions:",
    "",
    "1) Neither the Font Software nor any of its individual components,",
    "in Original or Modified Versions, may be sold by itself.",
    "",
    "2) Original or Modified Versions of the Font Software may be bundled,",
    "redistributed and/or sold with any software, provided that each copy",
    "contains the above copyright notice and this license. These can be",
    "included either as stand-alone text files, human-readable headers or",
    "in the appropriate machine-readable metadata fields within text or",
    "binary files as long as those fields can be easily viewed by the user.",
    "",
    "3) No Modified Version of the Font Software may use the Reserved Font",
    "Name(s) unless explicit written permission is granted by the corresponding",
    "Copyright Holder. This restriction only applies to the primary font name as",
    "presented to the users.",
    "",
    "4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font",
    "Software shall not be used to promote, endorse or advertise any",
    "Modified Version, except to acknowledge the contribution(s) of the",
    "Copyright Holder(s) and the Author(s) or with their explicit written",
    "permission.",
    "",
    "5) The Font Software, modified or unmodified, in part or in whole,",
    "must be distributed entirely under this license, and must not be",
    "distributed under any other license. The requirement for fonts to",
    "remain under this license does not apply to any document created",
    "using the Font Software.",
    "",
    "TERMINATION",
    "This license becomes null and void if any of the above conditions are",
    "not met.",
    "",
    "DISCLAIMER",
    'THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,',
    "EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF",
    "MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT",
    "OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE",
    "COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,",
    "INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL",
    "DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING",
    "FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM",
    "OTHER DEALINGS IN THE FONT SOFTWARE.",
    "",
])


# An OFL.txt with the licence's title and headings but none of its words: a label, not the licence.
TITLE_ONLY_TEXT = ("Copyright 2026 The Lumen Ledger Project Authors\n\nSIL OPEN FONT LICENSE Version 1.1\n\n"
                   "PERMISSION & CONDITIONS\n\nTERMINATION\n")


def ofl_text(copyright_line="Copyright 2026 The Lumen Ledger Project Authors (https://example.org/lumen-ledger)"):
    """An OFL.txt: the copyright line, then the unmodified licence."""
    return copyright_line + "\n\n" + OFL_BODY


# ------------------------------------------------------------------ outlines
def _rect(pen, x0, y0, x1, y1, hole=False):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)] if hole else [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()


def _shapes(stem):
    """Rectangles per glyph at one stem thickness: (advance, [(x0, y0, x1, y1, hole)])."""
    s, t = stem, round(stem * 0.8)
    S = round(stem * 1.05)
    return {
        ".notdef": (500, [(50, 0, 450, 700, False), (100, 50, 400, 650, True)]),
        "space": (250, []),
        "n": (520, [(60, 0, 60 + s, 500, False), (460 - s, 0, 460, 500, False), (60, 500 - t, 460, 500, False)]),
        "o": (520, [(50, -10, 470, 510, False), (50 + s, -10 + t, 470 - s, 510 - t, True)]),
        "x": (500, [(40, 0, 460, 500, False)]),
        "b": (540, [(60, 0, 60 + s, 740, False), (60, 0, 480, t, False), (480 - s, 0, 480, 500, False),
                    (60, 500 - t, 480, 500, False)]),
        "p": (540, [(60, -220, 60 + s, 500, False), (60, 0, 480, t, False), (480 - s, 0, 480, 500, False),
                    (60, 500 - t, 480, 500, False)]),
        "H": (720, [(70, 0, 70 + S, 700, False), (650 - S, 0, 650, 700, False), (70, 330, 650, 330 + t, False)]),
        "O": (740, [(50, -10, 690, 710, False), (50 + S, -10 + t, 690 - S, 710 - t, True)]),
    }


CMAP = {0x20: "space", ord("n"): "n", ord("o"): "o", ord("x"): "x", ord("H"): "H", ord("O"): "O", ord("b"): "b",
        ord("p"): "p"}
ORDER = [".notdef", "space", "n", "o", "x", "H", "O", "b", "p"]


def _ttglyphs(stem):
    out, adv = {}, {}
    for name, (a, rects) in _shapes(stem).items():
        pen = TTGlyphPen(None)
        for r in rects:
            _rect(pen, *r)
        out[name] = pen.glyph()
        adv[name] = a
    return out, adv


def _names(family, copyright_line, notice, extra=None):
    names = {"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": f"{family} Regular",
             "fullName": f"{family} Regular", "psName": family.replace(" ", "") + "-Regular", "version": "Version 1.000",
             "copyright": copyright_line, "designer": "Fixture Designer", "trademark": f"{family} is a fixture mark",
             "licenseDescription": notice, "licenseInfoURL": "https://openfontlicense.org"}
    names.update(extra or {})
    return names


def _finish(fb, family, copyright_line, notice, extra_names):
    fb.setupHorizontalHeader(ascent=900, descent=-250)
    fb.setupNameTable(_names(family, copyright_line, notice, extra_names), mac=False)
    fb.setupOS2(version=4, sTypoAscender=900, sTypoDescender=-250, usWinAscent=950, usWinDescent=260, sxHeight=500,
                sCapHeight=700, usWeightClass=400)
    fb.setupPost()


def glyf_vf(path, family=BASE_FAMILY, copyright_line="Copyright 2026 The Lumen Ledger Project Authors",
            notice=OFL_NOTICE, extra_names=None):
    """A TrueType variable font with a weight axis 100-900: the stems are 40 units at 100, 80 at 400, 160 at 900."""
    glyphs, adv = _ttglyphs(80)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(ORDER)
    fb.setupCharacterMap(CMAP)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (adv[n], glyphs[n].xMin if glyphs[n].numberOfContours else 0) for n in ORDER})
    _finish(fb, family, copyright_line, notice, extra_names)
    fb.setupFvar(axes=[("wght", 100, 400, 900, "Weight")], instances=[])
    heavy, _ = _ttglyphs(160)
    light, _ = _ttglyphs(40)
    variations = {}
    for n in ORDER:
        if not glyphs[n].numberOfContours:
            continue
        base = list(glyphs[n].coordinates)
        tv = []
        for other, region in ((heavy[n], {"wght": (0, 1.0, 1.0)}), (light[n], {"wght": (-1.0, -1.0, 0)})):
            d = [(q[0] - p[0], q[1] - p[1]) for p, q in zip(base, other.coordinates)] + [(0, 0)] * 4
            tv.append(TupleVariation(region, d))
        variations[n] = tv
    fb.setupGvar(variations)
    fb.save(path)
    return path


def glyf_static(path, family=BASE_FAMILY, notice=OFL_NOTICE):
    glyphs, adv = _ttglyphs(80)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(ORDER)
    fb.setupCharacterMap(CMAP)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (adv[n], glyphs[n].xMin if glyphs[n].numberOfContours else 0) for n in ORDER})
    _finish(fb, family, "Copyright 2026 The Lumen Ledger Project Authors", notice, None)
    fb.save(path)
    return path


def cff_static(path, family=BASE_FAMILY, notice=OFL_NOTICE):
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(ORDER)
    fb.setupCharacterMap(CMAP)
    charstrings, adv = {}, {}
    for name, (a, rects) in _shapes(80).items():
        pen = T2CharStringPen(a, None)
        for r in rects:
            _rect(pen, *r)
        charstrings[name] = pen.getCharString()
        adv[name] = a
    fb.setupCFF(family.replace(" ", "") + "-Regular", {"FullName": family}, charstrings, {})
    fb.setupHorizontalMetrics({n: (adv[n], 0) for n in ORDER})
    _finish(fb, family, "Copyright 2026 The Lumen Ledger Project Authors", notice, None)
    fb.save(path)
    return path


def flavoured(src, dst, flavor):
    """The same font in a WOFF ("woff") or WOFF2 ("woff2") container."""
    from fontTools.ttLib import TTFont
    f = TTFont(src)
    f.flavor = flavor
    f.save(dst)
    return dst


# ------------------------------------------------------------------ running the scripts
def run(script, *args, cwd=None):
    """Run one skill script with this interpreter. Returns the CompletedProcess (never raises on exit code)."""
    return subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd)


def approve(font, licence, out, *source, answer=SYNTHETIC_ANSWER):
    """The approval step as an agent runs it, with a synthetic answer: print the question, then record it with the
    two sha256 values it names and the decision. Returns the CompletedProcess of the step that ended it (the first
    refusal, or the run that wrote base.json), with the question asked as .question."""
    src = source or ("--source", "local")
    ask = run("record_base.py", "--font", font, "--licence", licence, *src, "--question-only", "--out", out)
    if ask.returncode:
        return ask
    question = ask.stdout.strip()
    font_sha, licence_sha = re.findall(r"\b[0-9a-f]{64}\b", question)[:2]
    r = run("record_base.py", "--font", font, "--licence", licence, *src, "--question", question, "--answer", answer,
            "--decision", "approved", "--font-sha256", font_sha, "--license-sha256", licence_sha, "--out", out)
    r.question = question
    return r


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path
