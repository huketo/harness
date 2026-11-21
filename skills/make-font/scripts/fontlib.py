# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "uharfbuzz", "numpy", "pillow"]
# ///
"""Shared geometry, licence reading and character sets for the make-font scripts.

Every length a measurement returns is in cap-normalised units: the font is scaled so its cap height is 700.
That puts a screenshot (no em size) and a font file on the same scale. `cap_em` keeps the file's real cap
height per 1000 em, so a build can set the em size later.

Nothing here copies a reference's outline. A measurement is a font-wide number or a class mean. The one outline
operation, transform_hangul, moves the base's own Hangul, for fit_font.py and for check_font.py to check it.
"""
import copy
import io
import json
import re
import statistics as st
from collections import namedtuple

from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

CAP = 700  # every measurement is scaled to this cap height

# Width classes, by how the letter is built. One mean advance per class is a target, never a single glyph.
CLASSES = {
    "lc_straight": "hmnu",
    "lc_bowl": "abdgpq",
    "lc_round": "ceos",
    "lc_diagonal": "kvwxyz",
    "lc_narrow": "fijlrt",
    "uc_straight": "BDHNPRU",
    "uc_round": "CGOQS",
    "uc_diagonal": "AKVXYZ",
    "uc_wide": "MW",
    "uc_narrow": "EFIJLT",
    "figures": "0123456789",
}
# Which side of each letter is straight (S), round (R) or other (O), left then right. Used by spacing.
SIDES = {
    "a": "RS", "b": "SR", "c": "RO", "d": "RS", "e": "RO", "f": "OO", "g": "RO", "h": "SS", "i": "SS",
    "j": "OS", "k": "SO", "l": "SS", "m": "SS", "n": "SS", "o": "RR", "p": "SR", "q": "RS", "r": "SO",
    "s": "OO", "t": "OO", "u": "SS", "v": "OO", "w": "OO", "x": "OO", "y": "OO", "z": "OO",
    "A": "OO", "B": "SR", "C": "RO", "D": "SR", "E": "SO", "F": "SO", "G": "RO", "H": "SS", "I": "SS",
    "J": "OS", "K": "SO", "L": "SO", "M": "SS", "N": "SS", "O": "RR", "P": "SR", "Q": "RR", "R": "SO",
    "S": "OO", "T": "OO", "U": "SS", "V": "OO", "W": "OO", "X": "OO", "Y": "OO", "Z": "OO",
}
# Sides whose mean is a spacing target: the cleanest straight and round sides of each case.
SIDE_CLASSES = {
    "lc_straight": [("n", 0), ("n", 1), ("m", 0), ("m", 1), ("h", 0), ("h", 1), ("i", 0), ("i", 1),
                    ("l", 0), ("l", 1), ("u", 0), ("r", 0), ("p", 0), ("b", 0), ("k", 0), ("d", 1), ("q", 1)],
    "lc_round": [("o", 0), ("o", 1), ("c", 0), ("e", 0), ("d", 0), ("q", 0), ("b", 1), ("p", 1)],
    "uc_straight": [("H", 0), ("H", 1), ("I", 0), ("I", 1), ("N", 0), ("N", 1), ("E", 0), ("B", 0), ("D", 0),
                    ("P", 0), ("R", 0), ("L", 0), ("F", 0), ("K", 0), ("M", 0), ("M", 1), ("U", 0), ("U", 1)],
    "uc_round": [("O", 0), ("O", 1), ("C", 0), ("G", 0), ("Q", 0), ("D", 1)],
}
# A fixed paragraph for the shaped-width check. It has spaces, punctuation and figures the width fit never sees.
PARA = ("The quick brown fox jumps over the lazy dog, then reads 24 pages of notes and signs the forms. "
        "Every line is set with kerning and ligatures on, at one size.")
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
SOLVE_TEXT = LETTERS + "0123456789 "
MEASURE_TEXT = LETTERS + "0123456789" + PARA + " .,:;!?'\"()[]{}-&/@#%*"

# Lines to ask for when a person can type into the font they like (a type tester, a design tool).
# measure_image.py reads advances from the n-X-n and H-X-H contexts, so every letter gets a width.
SAMPLE_LINES = [
    "nnnnoooo HHHHOOOO xpdhb",
    "nanbncndnenfngnhninjnknlnmnonpnqnrnsntnunvnwnxnynzn",
    "HAHBHCHDHEHFHGHIHJHKHLHMHNHOHPHQHRHSHTHUHVHWHXHYHZH",
    "H0H1H2H3H4H5H6H7H8H9H",
]

# ------------------------------------------------------------------ Hangul classes
# A syllable is an initial, a medial vowel and an optional final: U+AC00 + 588 initial + 28 medial + final. Its
# class is set by those parts before anything is measured: where the vowel stands against the initial (beside it,
# under it, or both) and whether a final sits under them. One mean per class is a target, never a single syllable.
SYLLABLES = (0xAC00, 0xD7A3)
VOWELS_BESIDE = {0, 1, 2, 3, 4, 5, 6, 7, 20}  # ㅏ ㅐ ㅑ ㅒ ㅓ ㅔ ㅕ ㅖ ㅣ
VOWELS_UNDER = {8, 12, 13, 17, 18}  # ㅗ ㅛ ㅜ ㅠ ㅡ. The other seven (ㅘ ㅙ ㅚ ㅝ ㅞ ㅟ ㅢ) are both: mixed.
# The syllables each class is measured on, fixed for every font. HANGUL_HELD_OUT are other syllables of the same
# classes: measure_font.py reports how far their means land from the list's, which tests the classes on that font.
HANGUL_CLASSES = {"H1": "가나머서저이니미", "H2": "고노도무수그느오", "H3": "과귀뇌뭐쉬의와위",
                  "H4": "각난달맘선일진형", "H5": "공눈돌몸손울큰흥", "H6": "광권뒷원괜윙휠쾅"}
HANGUL_HELD_OUT = {"H1": "펴캬벼해", "H2": "뷰표쿠효", "H3": "쇠퇴뒤희", "H4": "핥밖넋졌", "H5": "몫볶흙숯",
                   "H6": "횝꿩뵘괌"}
HANGUL_ANCHOR = "으"  # no blank column inside it and close to symmetric, so a screenshot is cut at it
HANGUL_STEM = "이니미"  # the vertical stem: the last vertical run of ㅣ, at mid face height
HANGUL_HSTROKE = HANGUL_ANCHOR + "그느"  # the horizontal stroke: ㅡ, the lowest run at the face's centre
HANGUL_OVERSHOOT = ("오", "고")  # a round top against a flat one
HANGUL_TEXT = HANGUL_ANCHOR + "".join(HANGUL_CLASSES.values()) + "".join(HANGUL_HELD_OUT.values())
# One line per class, each syllable between two anchors, so a screenshot splits into syllables at the anchors.
SAMPLE_LINES_KO = [HANGUL_ANCHOR + "".join(c + HANGUL_ANCHOR for c in chars) for chars in HANGUL_CLASSES.values()]
# How far fit_font.py may move the Hangul: one scale for the whole Hangul within HANGUL_SCALE_LIMIT of the base's, and
# each class's final x and y scale within HANGUL_CLASS_LIMIT of that scale and of each other (references/fitting.md).
HANGUL_SCALE_LIMIT = 0.06
HANGUL_CLASS_LIMIT = 0.03
# The transform's numbers are five decimals (fit_font.TRANSFORM_STEP): past a limit by any of them is at least 1e-7.
# The margin absorbs float division alone.
_LIMIT_MARGIN = 1e-9


def hangul_transform_over(xf):
    """What in a Hangul transform (fit_font.hangul_transform) lies past the limits, [] when nothing does: the one
    scale within HANGUL_SCALE_LIMIT; per class the x and y scale each within HANGUL_CLASS_LIMIT of it, and the larger
    of the two over the smaller within it too, whichever axis is larger; the compatibility jamo at the one scale on
    both axes, unmoved and with no advance added. fit_font.py runs it on the transform it logs and check_font.py on
    the transform it reads."""
    s, out = xf["scale"], []
    if abs(s - 1) > HANGUL_SCALE_LIMIT + _LIMIT_MARGIN:
        out.append(f"scale {s} ({s - 1:+.4%})")
    for cls in HANGUL_CLASSES:
        t = xf["classes"].get(cls)
        if t is None:
            out.append(f"{cls} has no transform")
            continue
        for name, v in (("x", t["sx"] / s), ("y", t["sy"] / s),
                        ("larger axis over smaller", max(t["sx"], t["sy"]) / min(t["sx"], t["sy"]))):
            if abs(v - 1) > HANGUL_CLASS_LIMIT + _LIMIT_MARGIN:
                out.append(f"{cls} {name} {v - 1:+.4%}")
    j = xf["jamo"]
    if (j["sx"], j["sy"]) != (s, s):
        out.append(f"jamo x {j['sx']}, y {j['sy']}, not the one scale {s}")
    out += [f"jamo {k} {j.get(k)}" for k in ("dx", "dy", "adv_add") if j.get(k) != 0]
    return out
# The units a Hangul number carries: lengths at cap height 700 (a Latin H measured with it), lengths per 1000 em
# (a font file), and ratios, which need neither. make_targets.py merges values of one unit only.
UNITS = ("cap700", "em1000", "ratio")


def hangul_class(ch):
    """H1 to H6, from the syllable's medial vowel and final alone, or None when ch is not a precomposed syllable."""
    s = ord(ch) - SYLLABLES[0] if len(ch) == 1 else -1
    if not 0 <= s <= SYLLABLES[1] - SYLLABLES[0]:
        return None
    medial, final = s % 588 // 28, s % 28
    shape = 1 if medial in VOWELS_BESIDE else 2 if medial in VOWELS_UNDER else 3
    return f"H{shape + (3 if final else 0)}"


COMPAT_JAMO = (0x3131, 0x318E)  # the Hangul compatibility jamo: a fit scales them by the Hangul's one scale only
# The 2,350 syllables of KS X 1001 (EUC-KR rows 0xB0 to 0xC8), read from Python's own codec.
KS_X_1001 = "".join(bytes([r, c]).decode("euc_kr") for r in range(0xB0, 0xC9) for c in range(0xA1, 0xFF))
MODERN_SYLLABLES = "".join(map(chr, range(SYLLABLES[0], SYLLABLES[1] + 1)))


def hangul_glyphs(font):
    """glyph name -> its Hangul class (H1 to H6) for every precomposed syllable in the character map, and "jamo" for
    every compatibility jamo."""
    out = {}
    for cp, name in font.getBestCmap().items():
        if COMPAT_JAMO[0] <= cp <= COMPAT_JAMO[1]:
            out[name] = "jamo"
        elif cls := hangul_class(chr(cp)):
            out[name] = cls
    return out


def decomposed(glyf, name):
    """A copy of the glyph as a simple glyph: a composite's components drawn into its own points, so that moving it
    never moves a glyph another one shares."""
    from fontTools.ttLib.tables import ttProgram
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
    g = glyf[name]
    if not g.isComposite():
        return copy.deepcopy(g)
    coords, ends, flags = g.getCoordinates(glyf)
    out = Glyph()
    out.numberOfContours = len(ends)
    out.coordinates = GlyphCoordinates(coords)
    out.endPtsOfContours = list(ends)
    out.flags = bytearray(f & 1 for f in flags)  # on-curve bits only: the component flags do not apply to points
    out.program = ttProgram.Program()
    out.program.fromBytecode(b"")
    return out


def hangul_move(t, scale, coords, adv):
    """One Hangul glyph's new points and advance under its class transform t (hangul_transform): the advance times
    the Hangul's scale plus the class's addition, the ink scaled about its own box centre (of its points), then moved
    by half the advance change, so the change splits evenly between the two sides, and by the class's shift."""
    new_adv = round(adv * scale + t["adv_add"])
    if not coords:
        return [], new_adv
    xs, ys = [p[0] for p in coords], [p[1] for p in coords]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ox, oy = cx + (new_adv - adv) / 2 + t["dx"], cy + t["dy"]
    return [(round(t["sx"] * (x - cx) + ox), round(t["sy"] * (y - cy) + oy)) for x, y in coords], new_adv


def transform_hangul(f, src, xf):
    """Every Hangul glyph of f (each syllable by its class, the compatibility jamo) from src, the full instance at the
    Hangul location, decomposed, then moved by hangul_move. fit_font.py moves the Hangul with it, and check_font.py
    moves the base's again with it to know where every point belongs. Returns the glyphs moved (hangul_glyphs of
    src) and how many were composites in src."""
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    glyf, hm, sglyf, shm = f["glyf"], f["hmtx"].metrics, src["glyf"], src["hmtx"].metrics
    composites = 0
    members = hangul_glyphs(src)
    for name, cls in members.items():
        composites += sglyf[name].isComposite()
        g = decomposed(sglyf, name)
        t = xf["jamo"] if cls == "jamo" else xf["classes"][cls]
        coords, adv = hangul_move(t, xf["scale"], list(g.coordinates) if g.numberOfContours > 0 else [],
                                  shm[name][0])
        if coords:
            g.coordinates = GlyphCoordinates(coords)
            g.recalcBounds(glyf)
        glyf[name] = g
        hm[name] = (adv, g.xMin if g.numberOfContours > 0 else 0)
    return members, composites


# The characters each script needs. check_font.py gates coverage on them, and fit_font.py subsets the base to them.
COVERAGE = {
    "latin": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
             "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝßàáâãäåæçèéêëìíîïñòóôõöøùúûüýÿŒœŠšŽžŸ"
             ".,:;!?¡¿'\"()[]{}-–—‘’“”‚„‹›«»…•·/\\&@#*§¶©®™°%‰$€£¥¢+−×÷=<>",
    "latin-ext": "ĀāĂăĄąĆćČčĎďĐđĒēĖėĘęĚěĞğĢģĪīĮįİıĶķĹĺĻļĽľŁłŃńŅņŇňŌōŐőŔŕŘřŚśŞşȘșŤťŢţȚțŪūŮůŰűŲųŹźŻż",
    "vietnamese": "ĂăÂâĐđÊêÔôƠơƯưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ",
    "cyrillic": "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюяЄєІіЇїҐґЎў",
    "greek": "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρστυφχψωςάέήίόύώ",
    "korean": KS_X_1001,
}
COVERAGE_NAMES = {"korean": "KS X 1001"}  # what a COVERAGE list is, where it is a standard's
# Characters fit_font.py keeps in its subset beyond a script's COVERAGE list, which check_font.py counts and reports
# without gating: every modern syllable and the compatibility jamo.
COVERAGE_REPORTED = {
    "korean": {"modern syllables": MODERN_SYLLABLES,
               "compatibility jamo": "".join(map(chr, range(COMPAT_JAMO[0], COMPAT_JAMO[1] + 1)))},
}
# Kept for every script: printable ASCII, Latin-1, and the typographic marks the font book and plain text use
# (dashes, quotes, ellipsis, primes, fraction slash, minus).
COMMON_UNICODES = [(0x20, 0x7E), (0xA0, 0xFF), (0x2010, 0x2027), (0x2030, 0x203A), (0x2044, 0x2044),
                   (0x20AC, 0x20AC), (0x2122, 0x2122), (0x2212, 0x2212)]


def charset_unicodes(scripts):
    """The code points a build for these scripts keeps, as pyftsubset's --unicodes value: COVERAGE and
    COVERAGE_REPORTED. Raises on a script with no list in COVERAGE, since a subset would silently drop it."""
    cps = {c for lo, hi in COMMON_UNICODES for c in range(lo, hi + 1)}
    for s in scripts:
        if s not in COVERAGE:
            raise ValueError(f"no character list for script {s!r} (known: {', '.join(COVERAGE)})")
        cps |= {ord(c) for c in COVERAGE[s] + "".join(COVERAGE_REPORTED.get(s, {}).values())}
    runs, start, prev = [], None, None
    for c in sorted(cps):
        if start is None:
            start = prev = c
        elif c == prev + 1:
            prev = c
        else:
            runs.append((start, prev))
            start = prev = c
    if start is not None:
        runs.append((start, prev))
    return ",".join(f"U+{a:04X}" if a == b else f"U+{a:04X}-{b:04X}" for a, b in runs)


# ------------------------------------------------------------------ licences and names
# The SIL Open Font License 1.1 from its title to the end, as SIL publishes it. An OFL.txt is the copyright
# statement, a two-line preamble whose FAQ address varies between files, then exactly this text.
OFL_11_LICENCE = """\
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
_OFL_11_WORDS = " ".join(OFL_11_LICENCE.split())
_OFL_PREAMBLE = re.compile(r"This Font Software is licensed under the SIL Open Font License, Version 1\.1\.\s+"
                           r"This license is copied below, and is also available with a FAQ at:\s+"
                           r"(?:https?://)?(?:scripts\.sil\.org/OFL|openfontlicense\.org)/?\s+-{10,}\s+")
_QUOTES = {'"': '"', "'": "'", "\u201c": "\u201d", "\u2018": "\u2019"}
_COPYRIGHT_LINE = re.compile(r"\s*copyright\b", re.I)


# ------------------------------------------------------------------ the forms a copyright line and a notice take
# Code cannot read a term, so it reads forms. A copyright line and a name ID 13 notice are accepted only in the
# forms published OFL fonts use; any other clause on them is refused as an unsupported form, never interpreted.

# A name is words joined by spaces. Each word has a capital letter or a digit (Lumen, tyPoland, 3D) or is one of
# these connectors. A full stop may end a name's last word (Inc.) and an initial or short abbreviation (J., Co.).
_CONNECTORS = {"and", "&", "of", "the", "by", "de", "da", "das", "dos", "del", "der", "di", "du", "la", "le",
               "van", "von", "y", "et", "und"}
_WORD = re.compile(r"[\w&'’-]+(?:\.[\w&'’-]+)*\.?")


def _is_name(text, commas=True):
    """True when text is a name, or with commas=True several names joined by commas (Lumen Type, Inc.)."""
    for group in (re.split(r"\s*,\s+", text) if commas else [text]):
        words = group.split()
        if not words or all(w.lower() in _CONNECTORS for w in words):
            return False
        for i, w in enumerate(words):
            if not _WORD.fullmatch(w):
                return False
            if w.endswith(".") and i < len(words) - 1 and not (len(w) <= 4 and w[0].isupper()):
                return False
            if w.lower() not in _CONNECTORS and not any(c.isupper() or c.isdigit() for c in w):
                return False
    return True


_YEAR = r"(?:1[89]|20)\d\d"
_CR_HEAD = re.compile(rf"\s*copyright(?:\s*(?:\(c\)|©))?\s+{_YEAR}(?:\s*[-–,]\s*{_YEAR})*,?\s+", re.I)
_CR_RFN = re.compile(r"[,.]?\s+with\s+reserved\s+font\s+names?\s+", re.I)
_CR_ADDRESS = re.compile(r"\s*\(([^()\s]+)\)$")
_ADDRESS = re.compile(r"[a-z][a-z0-9+.-]*://[^\s()|]+|[^\s()|@]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+"
                      r"|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:/[^\s()|]*)?", re.I)
_QUOTED = "|".join(f"{re.escape(o)}[^{re.escape(c)}]+{re.escape(c)}" for o, c in _QUOTES.items())
_QUOTED_NAMES = re.compile(rf"(?:{_QUOTED})(?:\s*,\s*(?:{_QUOTED}))*(?:\s*,?\s+and\s+(?:{_QUOTED}))?")
COPYRIGHT_FORM = ("Copyright, an optional (c) or ©, the year or years, the holder's name, an optional address in "
                  "parentheses, an optional \"with Reserved Font Name(s) ...\" clause and an optional full stop")


def copyright_line_problem(line):
    """Why a copyright line is not in the supported form, or None when it is. The form is COPYRIGHT_FORM: the
    holder's name and the Reserved Font Names are names (_is_name), and the address is URLs or e-mail addresses
    joined by |. A clause after any of them, a sentence or a term, is not part of the form."""
    head = _CR_HEAD.match(line)
    if not head:
        return "it does not start with Copyright, an optional (c) or ©, and the year"
    rest = line[head.end():].rstrip()
    rfn = _CR_RFN.search(rest)
    holder, names = (rest[:rfn.start()], rest[rfn.end():]) if rfn else (rest, None)
    if names is None:
        holder = holder[:-1] if holder.endswith(".") else holder
    else:
        names = names[:-1] if names.endswith(".") else names
    address = _CR_ADDRESS.search(holder)
    if address:
        if not all(_ADDRESS.fullmatch(a) for a in address.group(1).split("|")):
            return f"{address.group(0).strip()} is not an address (URLs or e-mail addresses joined by |)"
        holder = holder[:address.start()]
    holder = holder.strip()
    if not _is_name(holder):
        return (f"{holder!r} is not a holder's name followed by nothing else (a name is words with a capital "
                "letter or a digit, joined by spaces, commas, and, of, the)")
    if names is not None:
        quoted = _QUOTED_NAMES.fullmatch(names)
        if not (all(_is_name(n[1:-1], commas=False) for n in re.findall(_QUOTED, names)) if quoted
                else _is_name(names)):
            return (f"the Reserved Font Name clause {names!r} is not names alone (quoted names, or unquoted names "
                    "joined by commas and \"and\")")
    return None


def ofl_11_text_problem(text):
    """Why a licence file is not the SIL Open Font License 1.1, or None when it is. An OFL.txt is the copyright
    statement (copyright lines in the supported form, COPYRIGHT_FORM, and blank lines), the two-line preamble whose
    FAQ address varies between files, then the licence word for word, white space aside. Any other line before the
    preamble, or a copyright line in another form, may add a condition the OFL does not have, so it is refused."""
    m = _OFL_PREAMBLE.search(text)
    if not m:
        return "it has no OFL 1.1 preamble (\"This Font Software is licensed under the SIL Open Font License, " \
               "Version 1.1. This license is copied below...\")"
    if " ".join(text[m.end():].split()) != _OFL_11_WORDS:
        return "the text after the preamble is not the SIL Open Font License 1.1 word for word"
    lines = [ln.strip() for ln in text[:m.start()].splitlines() if ln.strip()]
    for ln in lines:
        if not _COPYRIGHT_LINE.match(ln):
            return f"the line {ln!r} stands before the licence and is not a copyright line"
        why = copyright_line_problem(ln)
        if why:
            return (f"the line {ln!r} is not a supported copyright line: {why}. The supported form is "
                    f"{COPYRIGHT_FORM}")
    if not lines:
        return "it has no copyright line"
    return None


def is_ofl_11_text(text):
    return ofl_11_text_problem(text) is None


# name ID 13: the sentence that grants the OFL 1.1, then only sentences published OFL fonts follow it with (where
# the licence and its FAQ are, where a modifier's licence is, the "AS IS" disclaimer).
_END = r"\.?(?=\s|$)"
_URL = r"(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:/\S*?)?"
_NAME_RUN = r"[^\s,;:!?()\"']+(?:\s+[^\s,;:!?()\"']+)*?"
_NOTICE_GRANT = re.compile(r"This\s+Font\s+Software\s+is\s+licensed\s+under\s+the\s+SIL\s+Open\s+Font\s+License,?\s+"
                           r"Version\s+1\.1" + _END, re.I)
_NOTICE_SENTENCES = [
    re.compile(r"This\s+license\s+is\s+(?:copied\s+below,\s+and\s+is\s+also\s+)?available\s+with\s+an?\s+FAQ\s+"
               r"at:?\s+" + _URL + _END, re.I),
    re.compile(rf"The\s+license\s+for\s+(?P<modifier>{_NAME_RUN})['’]s\s+Modified\s+Version(?:,\s+covering\s+"
               rf"(?P<holder>{_NAME_RUN})['’]s\s+modifications\s+to\s+(?P<font>{_NAME_RUN}),)?\s+is\s+available\s+"
               r"at:?\s+" + _URL + _END, re.I),
    re.compile(r"This\s+Font\s+Software\s+is\s+distributed\s+on\s+an\s+\"AS\s+IS\"\s+BASIS,\s+"
               r"WITHOUT\s+WARRANTIES\s+OR\s+CONDITIONS\s+OF\s+ANY\s+KIND,\s+either\s+express\s+or\s+implied" + _END,
               re.I),
]
NOTICE_FORM = ("\"This Font Software is licensed under the SIL Open Font License, Version 1.1\", then only where "
               "the licence and its FAQ are available, where a Modified Version's licence is available, or the "
               "\"AS IS\" disclaimer")


def ofl_11_notice_problem(notice):
    """Why a name-table licence notice (name ID 13) does not grant the SIL Open Font License, Version 1.1 alone, or
    None when it does. The notice is NOTICE_FORM: the grant first, then only the known sentences. A label alone
    ("OFL-1.1"), another version, a denial, an exception or any other clause is not that form."""
    text = (notice or "").strip()
    m = _NOTICE_GRANT.match(text)
    if not m:
        return ("it does not begin with \"This Font Software is licensed under the SIL Open Font License, "
                "Version 1.1\"")
    pos = m.end()
    while True:
        pos = re.compile(r"\s*").match(text, pos).end()
        if pos == len(text):
            return None
        for rx in _NOTICE_SENTENCES:
            m = rx.match(text, pos)
            if m and all(_is_name(v, commas=False) for v in m.groupdict().values() if v is not None):
                pos = m.end()
                break
        else:
            return f"{text[pos:]!r} follows the grant and is not one of the sentences supported after it"


def is_ofl_11_notice(notice):
    return ofl_11_notice_problem(notice) is None


def _rfn_clause(rest):
    """Names from the text after `with Reserved Font Name(s)`, up to the end of that sentence."""
    rest = rest.lstrip(" :")
    if rest[:1] in _QUOTES:
        names, i = [], 0
        while i < len(rest):
            ch = rest[i]
            if ch in _QUOTES:
                end = rest.find(_QUOTES[ch], i + 1)
                if end < 0:
                    break
                names.append(rest[i + 1:end].strip())
                i = end + 1
            elif ch == "." or ch == ";":
                break
            else:
                i += 1
        return [n for n in names if n]
    m = re.match(r"(.*?)(?:\.(?:\s|$)|;|$)", rest)
    return [n.strip() for n in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", m.group(1)) if n.strip()]


def reserved_font_names(ofl_text):
    """Reserved Font Names declared in an OFL text, in order. Only copyright notice lines count (lines that start
    with Copyright), from `with Reserved Font Name(s)` to the end of that sentence. The OFL body's own definition
    of the term is not a declaration."""
    out = []
    for line in ofl_text.splitlines():
        if not re.match(r"\s*copyright\b", line, re.I):
            continue
        m = re.search(r"\bwith\s+Reserved\s+Font\s+Names?\b(.*)", line, re.I)
        if m:
            out += [n for n in _rfn_clause(m.group(1)) if n not in out]
    return out


def english_names(font):
    """name ID -> string, the English record first: Windows US English, other Windows English, Mac English,
    then anything else. A plain dict over the records would let a later language overwrite the English one."""
    def rank(r):
        if r.platformID == 3 and r.langID == 0x409:
            return 0
        if r.platformID == 3 and r.langID & 0x3FF == 0x09:
            return 1
        if r.platformID == 1 and r.langID == 0:
            return 2
        return 3
    best = {}
    for r in font["name"].names:
        try:
            s = r.toUnicode()
        except UnicodeDecodeError:
            continue
        k = rank(r)
        if r.nameID not in best or k < best[r.nameID][0]:
            best[r.nameID] = (k, s)
    return {nid: s for nid, (_, s) in best.items()}



# ------------------------------------------------------------------ outlines
class FlatPen(BasePen):
    """Flattens a glyph into closed polygons. Curves become 16 straight pieces."""

    def __init__(self, gs, steps=16):
        super().__init__(gs)
        self.polys, self.cur, self.steps = [], None, steps

    def _moveTo(self, p):
        self.cur = [p]
        self.polys.append(self.cur)

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, a, b, c):
        p0, n = self.cur[-1], self.steps
        for i in range(1, n + 1):
            t = i / n
            m = 1 - t
            self.cur.append((m ** 3 * p0[0] + 3 * m * m * t * a[0] + 3 * m * t * t * b[0] + t ** 3 * c[0],
                             m ** 3 * p0[1] + 3 * m * m * t * a[1] + 3 * m * t * t * b[1] + t ** 3 * c[1]))

    def _qCurveToOne(self, a, c):
        p0, n = self.cur[-1], self.steps
        for i in range(1, n + 1):
            t = i / n
            m = 1 - t
            self.cur.append((m * m * p0[0] + 2 * m * t * a[0] + t * t * c[0], m * m * p0[1] + 2 * m * t * a[1] + t * t * c[1]))

    def _closePath(self):
        pass

    _endPath = _closePath


def _spans(polys, v, axis):
    """Ink runs along a line (axis 1: horizontal line y=v, axis 0: vertical line x=v), nonzero winding.
    Works on overlapping contours, which variable-font instances often have."""
    hits = []
    o = 1 - axis
    for poly in polys:
        n = len(poly)
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]
            if (p[axis] <= v < q[axis]) or (q[axis] <= v < p[axis]):
                t = (v - p[axis]) / (q[axis] - p[axis])
                hits.append((p[o] + t * (q[o] - p[o]), 1 if q[axis] > p[axis] else -1))
    hits.sort()
    runs, wind, start = [], 0, None
    for x, d in hits:
        before = wind
        wind += d
        if before == 0 and wind != 0:
            start = x
        elif before != 0 and wind == 0 and start is not None:
            if runs and start - runs[-1][1] < 1e-6:
                runs[-1] = (runs[-1][0], x)  # two contours that touch make one run
            else:
                runs.append((start, x))
    return runs


PairGap = namedtuple("PairGap", "gap row left right offset")  # Face.pair_gap: the right glyph's origin at offset


class Face:
    """A font, or one location of a variable font, with the questions the scripts ask of it."""

    def __init__(self, src, loc=None, subset_text=None):
        f = src if isinstance(src, TTFont) else TTFont(src)
        if subset_text:
            f = subset_font(f, subset_text)
        if loc and "fvar" in f:
            from fontTools.varLib import instancer
            axes = {a.axisTag: (a.minValue, a.maxValue) for a in f["fvar"].axes}
            loc = {k: min(max(float(v), axes[k][0]), axes[k][1]) for k, v in loc.items() if k in axes}
            f = instancer.instantiateVariableFont(f, loc, updateFontNames=False)
        self.font = f
        self.loc = loc or {}
        self.upm = f["head"].unitsPerEm
        self.cmap = f.getBestCmap()
        self.gs = f.getGlyphSet()
        self.hmtx = f["hmtx"].metrics
        self._polys, self._profiles, self._hb = {}, {}, None

    def has(self, ch):
        return ord(ch) in self.cmap

    def gname(self, ch):
        return self.cmap[ord(ch)] if len(ch) == 1 else ch

    def polys(self, ch):
        return self.glyph_polys(self.gname(ch))

    def glyph_polys(self, name):
        """The glyph's outline as polygons, by glyph name."""
        if name not in self._polys:
            p = FlatPen(self.gs)
            self.gs[name].draw(p)
            self._polys[name] = p.polys
        return self._polys[name]

    def bounds(self, ch):
        p = BoundsPen(self.gs)
        self.gs[self.gname(ch)].draw(p)
        return p.bounds

    def adv(self, ch):
        return self.hmtx[self.gname(ch)][0]

    def hspans(self, ch, y):
        return _spans(self.polys(ch), y, 1)

    def vspans(self, ch, x):
        return _spans(self.polys(ch), x, 0)

    def svg_path(self, ch):
        p = SVGPathPen(self.gs)
        self.gs[self.gname(ch)].draw(p)
        return p.getCommands()

    def hb_font(self):
        if self._hb is None:
            import uharfbuzz as hb
            buf = io.BytesIO()
            self.font.save(buf)
            self._hb = hb.Font(hb.Face(buf.getvalue()))
        return self._hb

    def shape(self, text, features=None):
        """[(glyph name, x offset, x advance)] in font units, shaped by HarfBuzz."""
        import uharfbuzz as hb
        font = self.hb_font()
        b = hb.Buffer()
        b.add_str(text)
        b.guess_segment_properties()
        hb.shape(font, b, features if features is not None else {"kern": True, "liga": True})
        order = self.font.getGlyphOrder()
        return [(order[i.codepoint], p.x_offset, p.x_advance) for i, p in zip(b.glyph_infos, b.glyph_positions)]

    def text_width(self, text, features=None):
        return sum(a for _, _, a in self.shape(text, features))

    def kern(self, pair):
        """Kerning HarfBuzz applies between two characters (over the advance of the glyph it sets first), or None
        when they form a ligature."""
        on = self.shape(pair, {"kern": True, "liga": False})
        if len(on) != 2:
            return None
        return on[0][2] - self.hmtx[on[0][0]][0]

    def profile(self, ch, step=4, lo=-400, hi=1200):
        return self.glyph_profile(self.gname(ch), step, lo, hi)

    def glyph_profile(self, name, step=4, lo=-400, hi=1200):
        """Leftmost and rightmost ink per row, rows `step` units apart, by glyph name."""
        key = (name, step, lo, hi)
        if key not in self._profiles:
            rows = {}
            for y in range(lo, hi, step):
                s = _spans(self.glyph_polys(name), y + 0.5, 1)
                if s:
                    rows[y] = (s[0][0], s[-1][1])
            self._profiles[key] = rows
        return self._profiles[key]

    def pair_gap(self, pair, step=4):
        """Two characters as HarfBuzz sets them, kerning on and ligatures off, contextual alternates and all: the
        smallest horizontal ink gap between them, its row, the two glyphs shaping chose, and where the second glyph's
        origin sits from the first's. None when they shape to one glyph or share no row of ink. The collision guard
        (space_font.py) kerns these glyphs, and check_font.py and the font book read the same gap."""
        on = self.shape(pair, {"kern": True, "liga": False})
        if len(on) != 2:
            return None
        (left, x_left, advance), (right, x_right, _) = on
        a, b = self.glyph_profile(left, step), self.glyph_profile(right, step)
        off = advance + x_right - x_left
        gaps = [(b[y][0] + off - a[y][1], y) for y in a if y in b]
        if not gaps:
            return None
        gap, y = min(gaps)
        return PairGap(gap, y, left, right, off)


def subset_font(f, text, layout=True):
    """A small copy of the font that holds only the glyphs `text` needs. Instancing it is fast, and much
    faster with layout=False: the variable kerning is most of the cost of an instance."""
    import copy
    from fontTools import subset
    opts = subset.Options()
    opts.layout_features = ["kern", "liga", "mark", "mkmk", "calt", "locl"] if layout else []
    opts.notdef_outline = True
    opts.name_IDs = ["*"]
    opts.hinting = False
    t = copy.deepcopy(f)
    s = subset.Subsetter(opts)
    s.populate(text=text)
    s.subset(t)
    return t


def axes_of(f):
    return {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in f["fvar"].axes} if "fvar" in f else {}


# ------------------------------------------------------------------ measuring a font
def _w(r):
    return r[1] - r[0]


def _safe(fn):
    try:
        return fn()
    except (KeyError, IndexError, TypeError, ZeroDivisionError, ValueError):
        return None


def measure_face(face):
    """Every target the skill uses, from outlines, in cap-normalised units (cap = 700)."""
    F = face
    xh = F.bounds("x")[3]
    H = F.bounds("H")
    cap = H[3]
    k = CAP / cap
    m = {"source": "file", "cap_em": round(cap * 1000 / F.upm, 1), "cap": CAP}

    def r(v, nd=1):
        return None if v is None else round(v * k, nd)

    m["xh"] = r(xh)
    m["xh_cap"] = round(xh / cap, 3)
    m["asc"] = r(_safe(lambda: st.mean(F.bounds(c)[3] for c in "bdhkl" if F.has(c))))
    m["desc"] = r(_safe(lambda: st.mean(F.bounds(c)[1] for c in "pq" if F.has(c))))
    m["overshoot_lc"] = r(_safe(lambda: F.bounds("o")[3] - xh))
    m["overshoot_uc"] = r(_safe(lambda: F.bounds("O")[3] - cap))
    n_runs = F.hspans("n", xh * 0.5)
    m["n_stem"] = r(_w(n_runs[0]))
    m["n_counter"] = r(n_runs[1][0] - n_runs[0][1]) if len(n_runs) > 1 else None
    H_runs = F.hspans("H", cap * 0.3)
    m["H_stem"] = r(_w(H_runs[0]))
    bar = _safe(lambda: F.vspans("H", (H_runs[0][1] + H_runs[-1][0]) / 2)) if len(H_runs) > 1 else None
    m["H_bar"] = r(_w(bar[0])) if bar else None
    ob = F.bounds("o")
    m["o_side"] = r(_safe(lambda: _w(F.hspans("o", (ob[1] + ob[3]) / 2 + 0.37)[0])))
    m["o_thin"] = r(_safe(lambda: min(_w(x) for x in F.vspans("o", (ob[0] + ob[2]) / 2 + 0.37))))
    m["contrast"] = round(m["o_thin"] / m["o_side"], 3) if m["o_thin"] and m["o_side"] else None
    m["bar_stem"] = round(m["H_bar"] / m["H_stem"], 3) if m["H_bar"] and m["H_stem"] else None
    # Serifs: how far the foot of H reaches past its stem, and how thick it is near the tip.
    foot = _safe(lambda: F.hspans("H", cap * 0.01 + 1)[0])
    ext = 0.0
    tip = 0.0
    if foot:
        ext_l = H_runs[0][0] - foot[0]
        ext_r = foot[1] - H_runs[0][1]
        ext = (ext_l + ext_r) / 2
        if ext > 0.12 * _w(H_runs[0]):
            t = F.vspans("H", foot[0] + max(ext_l, 1) * 0.3)
            tip = _w(t[0]) if t else 0.0
        else:
            ext = 0.0
    m["serif"] = ext > 0
    m["serif_ext"] = r(ext)
    m["serif_tip"] = r(tip)
    m["widths"] = {}
    for cls, chars in CLASSES.items():
        have = [c for c in chars if F.has(c)]
        if have:
            m["widths"][cls] = r(st.mean(F.adv(c) for c in have))
    m["lc_avg"] = r(st.mean(F.adv(c) for c in LETTERS[:26] if F.has(c)))
    m["uc_avg"] = r(st.mean(F.adv(c) for c in LETTERS[26:] if F.has(c)))
    m["sides"] = {}
    for cls, members in SIDE_CLASSES.items():
        vals = []
        for c, s in members:
            if F.has(c):
                b = F.bounds(c)
                vals.append(b[0] if s == 0 else F.adv(c) - b[2])
        if vals:
            m["sides"][cls] = r(st.mean(vals))
    if m.get("n_counter") and m["sides"].get("lc_straight") is not None:
        m["rhythm"] = round(2 * m["sides"]["lc_straight"] / m["n_counter"], 3)
    m["space"] = r(F.adv(" ")) if F.has(" ") else None
    m["para"] = r(_safe(lambda: F.text_width(PARA)), 0)
    m["vmetrics"] = vmetrics(F.font)
    m["confidence"] = {key: "high" for key in m if key not in ("source", "confidence")}
    return m


def vmetrics(f):
    os2, hh = f["OS/2"], f["hhea"]
    return {"upm": f["head"].unitsPerEm, "hhea": [hh.ascent, hh.descent, hh.lineGap],
            "typo": [os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap],
            "win": [os2.usWinAscent, os2.usWinDescent], "use_typo": bool(os2.fsSelection & 128)}


# ------------------------------------------------------------------ measuring Hangul
# `ink` is a Face, or anything else with has(ch), bounds(ch) -> (x0, y0, x1, y1) and hspans / vspans(ch, at) ->
# [(start, end)] in order along the cut, y up: measure_image.py reads a screenshot through the same questions.
def _boxes(ink, chars):
    return [(c, b) for c in chars if ink.has(c) for b in [ink.bounds(c)] if b]


def _run_widths(ink, chars, cut):
    """{syllable: width of one run} for the syllables the ink has. cut(box) -> (axis, position, index): 1 cuts a
    row, 0 a column."""
    widths = {}
    for c, b in _boxes(ink, chars):
        axis, at, i = cut(b)
        runs = ink.hspans(c, at) if axis == 1 else ink.vspans(c, at)
        if runs:
            widths[c] = runs[i][1] - runs[i][0]
    return widths


def _stem_widths(ink):
    return _run_widths(ink, HANGUL_STEM, lambda b: (1, (b[1] + b[3]) / 2, -1))


def hangul_stem(ink):
    """The vertical stem: the last run across ㅣ in HANGUL_STEM at mid face height, median of the three, or None
    unless all three were read."""
    widths = _stem_widths(ink)
    return st.median(widths.values()) if len(widths) == len(HANGUL_STEM) else None


def hangul_stem_h1(ink):
    """The vertical stem over the H1 class's mean face height, both read from the same ink."""
    stem, h1 = hangul_stem(ink), _boxes(ink, HANGUL_CLASSES["H1"])
    return stem / st.mean(b[3] - b[1] for _, b in h1) if stem and h1 else None


def hangul_class_strokes(ink):
    """Per class, the median width of the vertical strokes of its measuring syllables: every run across the face at
    20, 35, 50, 65 and 80 % of its height that is narrower than a fifth of that height (a cut along a horizontal
    stroke is longer, so it is left out)."""
    out = {}
    for cls, chars in HANGUL_CLASSES.items():
        runs = []
        for c, b in _boxes(ink, chars):
            h = b[3] - b[1]
            for t in (0.2, 0.35, 0.5, 0.65, 0.8):
                runs += [r[1] - r[0] for r in ink.hspans(c, b[1] + h * t + 0.37) if r[1] - r[0] < h / 5]
        if runs:
            out[cls] = st.median(runs)
    return out


def _contrast(ink):
    """ㅇ in the anchor: its top and bottom thickness over its side thickness."""
    got = _boxes(ink, HANGUL_ANCHOR)
    if not got:
        return None, None
    b = got[0][1]
    v = ink.vspans(HANGUL_ANCHOR, (b[0] + b[2]) / 2)  # ㅡ, then the bottom and the top of ㅇ, bottom up
    if len(v) < 3:
        return None, None
    h = ink.hspans(HANGUL_ANCHOR, (v[-2][0] + v[-1][1]) / 2)  # the two sides of ㅇ at its middle
    if len(h) < 2:
        return None, None
    ends = [(v[-1][1] - v[-1][0]), (v[-2][1] - v[-2][0])]
    sides = [(h[0][1] - h[0][0]), (h[-1][1] - h[-1][0])]
    return st.mean(ends) / st.mean(sides), min(ends + sides)


CLASS_MIN = 2  # different syllables a class mean needs: one syllable read again and again is still one


def hangul_geometry(ink, font=True):
    """Hangul numbers in the ink's own units: per class the mean face (the ink box) width and height; the stem; and
    the report-only overshoot, ㅇ contrast and horizontal stroke. With font=True the boxes sit on the glyph origin
    and the baseline, so each class also gets its face centre, sides and advance, the font whether its Hangul is
    fixed-width, and held_out the held-out syllables' mean face over the list's. A class read on fewer than
    CLASS_MIN of its syllables, and the stem without all of HANGUL_STEM, are left out: left_out names the
    syllables they had."""
    out = {"classes": {}, "left_out": {}}
    for cls, chars in HANGUL_CLASSES.items():
        bs = _boxes(ink, chars)
        if len(bs) < CLASS_MIN:
            if bs:
                out["left_out"][cls] = "".join(c for c, _ in bs)
            continue
        g = {"syllables": "".join(c for c, _ in bs), "face_w": st.mean(b[2] - b[0] for _, b in bs),
             "face_h": st.mean(b[3] - b[1] for _, b in bs)}
        if font:
            adv = [ink.adv(c) for c, _ in bs]
            g["cx"] = st.mean((b[0] + b[2]) / 2 for _, b in bs)
            g["cy"] = st.mean((b[1] + b[3]) / 2 for _, b in bs)
            g["side"] = st.mean((b[0] + a - b[2]) / 2 for (_, b), a in zip(bs, adv))
            g["side_asym"] = st.mean(a - b[2] - b[0] for (_, b), a in zip(bs, adv))
            g["center_adv"] = st.mean((b[0] + b[2]) / 2 / a for (_, b), a in zip(bs, adv))
            g["adv"] = st.mean(adv)
            held = _boxes(ink, HANGUL_HELD_OUT[cls])
            if held:
                g["held_out"] = {"face_w": st.mean(b[2] - b[0] for _, b in held) / g["face_w"],
                                 "face_h": st.mean(b[3] - b[1] for _, b in held) / g["face_h"]}
        out["classes"][cls] = g
    if font and out["classes"]:
        advs = [ink.adv(c) for c in HANGUL_ANCHOR + "".join(HANGUL_CLASSES.values()) if ink.has(c)]
        out["fixed_width"] = max(advs) - min(advs) <= 0.005 * st.mean(advs)
        if out["fixed_width"]:
            out["adv"] = st.mean(advs)
            for g in out["classes"].values():
                del g["adv"]
    out["stem"] = hangul_stem(ink)
    if out["stem"] is None and (got := _stem_widths(ink)):
        out["left_out"]["stem"] = "".join(got)
    hstroke = _run_widths(ink, HANGUL_HSTROKE, lambda b: (0, (b[0] + b[2]) / 2, 0))
    out["hstroke"] = st.median(hstroke.values()) if hstroke else None
    out["contrast"], out["contrast_thinnest"] = _contrast(ink)
    tops = [_boxes(ink, c) for c in HANGUL_OVERSHOOT]
    out["overshoot"] = tops[0][0][1][3] - tops[1][0][1][3] if all(tops) else None
    return out


def hangul_measurement(geo, lengths, conf=None, n_stem=None):
    """The `hangul` object of a measurement file: hangul_geometry's numbers, each tagged with its unit. lengths maps
    each length unit the source can give to the factor from its own units: cap700 when a Latin H was measured with
    it, em1000 in a font file. A key holds lengths or one ratio, never both, and a ratio key's suffix names its
    denominator: _cap the Latin cap height, _h1 the H1 class's face, _n the Latin n stem (n_stem, at cap 700, read
    from the same source). conf(kind, raw) is the confidence of a value read from a raw size ("size", "stroke" or
    "edge"); a font file's values are all high."""
    def tag(v, unit, kind, raw):
        return {"value": round(v, 4 if unit == "ratio" else 1), "unit": unit,
                "confidence": conf(kind, raw) if conf else "high"}

    def length(v, kind):
        return [tag(v * k, u, kind, v) for u, k in lengths.items()]

    def ratio(v, kind, raw):
        return [tag(v, "ratio", kind, raw)]
    cap = lengths.get("cap700")
    h1 = geo["classes"].get("H1")
    classes = {}
    for cls, g in geo["classes"].items():
        c = {"syllables": g["syllables"]}
        for key in ("face_w", "face_h"):
            c[key] = length(g[key], "size")
            if cap:
                c[key + "_cap"] = ratio(g[key] * cap / CAP, "size", g[key])
            if h1:
                c[key + "_h1"] = ratio(g[key] / h1[key], "size", min(g[key], h1[key]))
        c["aspect"] = ratio(g["face_w"] / g["face_h"], "size", g["face_w"])
        for key in ("cx", "cy", "side", "side_asym", "adv"):
            if key in g:
                c[key] = length(g[key], "size")
        if "adv" in g and cap:
            c["adv_cap"] = ratio(g["adv"] * cap / CAP, "size", g["adv"])
        if "center_adv" in g:
            c["center_adv"] = ratio(g["center_adv"], "size", g["face_w"])
        classes[cls] = c
    out = {"units": [*lengths, "ratio"], "classes": classes}
    if geo["stem"]:
        out["stem"] = length(geo["stem"], "stroke")
        if h1:
            out["stem_h1"] = ratio(geo["stem"] / h1["face_h"], "stroke", geo["stem"])
        if cap and n_stem:
            out["stem_n"] = ratio(geo["stem"] * cap / n_stem, "stroke", geo["stem"])
    if "fixed_width" in geo:
        out["fixed_width"] = geo["fixed_width"]
        if geo["fixed_width"]:
            out["adv"] = length(geo["adv"], "size")
            if cap:
                out["adv_cap"] = ratio(geo["adv"] * cap / CAP, "size", geo["adv"])
    report = {}
    for key, kind in (("overshoot", "edge"), ("hstroke", "stroke")):
        if geo[key] is not None:
            report[key] = length(geo[key], kind)
            if h1:
                report[key + "_h1"] = ratio(geo[key] / h1["face_h"], kind, abs(geo[key]))
    if geo["contrast"]:
        report["contrast"] = ratio(geo["contrast"], "stroke", geo["contrast_thinnest"])
    if geo.get("pitch"):
        report["pitch"] = {cls: length(v, "size") for cls, v in geo["pitch"].items()}
        if h1:
            report["pitch_h1"] = {cls: ratio(v / h1["face_h"], "size", v) for cls, v in geo["pitch"].items()}
    out["report"] = report
    out["held_out"] = {cls: {k: ratio(v, "size", g["face_h"]) for k, v in g["held_out"].items()}
                       for cls, g in geo["classes"].items() if "held_out" in g}
    out["left_out"] = geo["left_out"]
    return _pruned(out)


def _pruned(tree):
    """The tree without its empty lists (a length where the source has no length unit) and empty dicts."""
    out = {}
    for k, v in tree.items():
        v = _pruned(v) if isinstance(v, dict) else v
        if v != [] and v != {}:
            out[k] = v
    return out


def stem_cap700(face, ch="n"):
    """n stem (or H stem) scaled to cap 700. Used to solve the weight that matches a target."""
    xh = face.bounds("x")[3]
    cap = face.bounds("H")[3]
    y = xh * 0.5 if ch == "n" else cap * 0.3
    return _w(face.hspans(ch, y)[0]) * CAP / cap


def solve_axis(make_face, measure, target, lo, hi, iters=12, rising=True):
    """Bisect one axis value so measure(make_face(v)) meets target. `rising`: measure grows with v."""
    best = None
    for _ in range(iters):
        mid = (lo + hi) / 2
        v = measure(make_face(mid))
        best = (mid, v)
        if (v < target) == rising:
            lo = mid
        else:
            hi = mid
    return best


# ------------------------------------------------------------------ comparing
# How far apart two measurements may be before they count as one unit of distance, and how much each counts.
DISTANCE = {
    "xh_cap": (0.015, 3.0), "asc": (15, 1.0), "desc": (15, 1.0), "contrast": (0.06, 2.0), "bar_stem": (0.08, 1.0),
    "serif_ext": (12, 1.5), "serif_tip": (10, 1.0), "overshoot_lc": (6, 0.3), "rhythm": (0.08, 1.0),
    "n_stem": (6, 1.0),
}
WIDTH_SCALE = 0.025  # 2.5 % of a class mean advance is one unit
# The Hangul ratios find_foundation.py compares, per class where the key is a class's: a relative gap of `scale`
# (candidate over target, minus 1) is one unit of distance, times the weight.
HANGUL_DISTANCE = {"aspect": (0.02, 1.0), "face_h_h1": (0.02, 1.0), "face_h_cap": (0.03, 1.0), "stem_h1": (0.05, 1.0)}


def hangul_distance(target, cand, skip=()):
    """Weighted distance and per-key relative deltas between two hangul objects (targets.json's, and a candidate's
    hangul_measurement), on the ratio keys of HANGUL_DISTANCE that both have. Keys in skip are left out."""
    total, deltas = 0.0, {}

    def add(path, want, got, scale, w):
        nonlocal total
        a, b = tagged_value(want, "ratio"), tagged_value(got, "ratio")
        if a and b:
            d = b / a - 1
            deltas[path] = round(d, 4)
            total += w * (d / scale) ** 2
    for key, (scale, w) in HANGUL_DISTANCE.items():
        if key in skip:
            continue
        if key in target:
            add(key, target[key], cand.get(key), scale, w)
        for cls, c in (target.get("classes") or {}).items():
            if key in c:
                add(f"{cls}.{key}", c[key], ((cand.get("classes") or {}).get(cls) or {}).get(key), scale, w)
    return round(total ** 0.5, 3), deltas


def distance(target, cand, width_weight=1.0, skip=()):
    """Weighted distance and per-key deltas (candidate minus target). Missing keys are left out.
    width_weight is a number, or a function (class, relative delta) -> number."""
    total, deltas = 0.0, {}
    for key, (scale, w) in DISTANCE.items():
        if key in skip:
            continue
        a, b = target.get(key), cand.get(key)
        if a is None or b is None:
            continue
        d = b - a
        deltas[key] = round(d, 3)
        total += w * (d / scale) ** 2
    if target.get("serif") is not None and cand.get("serif") is not None and target["serif"] != cand["serif"]:
        total += 50
        deltas["serif"] = "mismatch"
    for cls, tv in (target.get("widths") or {}).items():
        cv = (cand.get("widths") or {}).get(cls)
        if tv and cv:
            d = cv / tv - 1
            deltas["w_" + cls] = round(d, 4)
            w = width_weight(cls, d) if callable(width_weight) else width_weight
            total += w * 0.5 * (d / WIDTH_SCALE) ** 2
    return round(total ** 0.5, 3), deltas


def tagged_value(entries, unit):
    """The value of one unit in a list of tagged values, or None."""
    return next((e["value"] for e in entries or [] if e["unit"] == unit), None)


def hangul_summary(h):
    """Lines that show a hangul object's main numbers, lengths in the first unit it has them in."""
    have = {e["unit"] for c in h["classes"].values() for e in c.get("face_h", [])}
    unit = next((u for u in UNITS if u in have), "ratio")
    out = [f"  hangul, lengths in {unit}" + (f"; fixed width {h['fixed_width']}" if "fixed_width" in h else "")]
    keys = (("aspect", "ratio"), ("face_h_h1", "ratio"))
    if unit != "ratio":
        keys = (("face_w", unit), ("face_h", unit)) + keys
    for cls, c in h["classes"].items():
        row = ", ".join(f"{k} {tagged_value(c.get(k), u)}" for k, u in keys)
        out.append(f"    {cls} {c.get('syllables', '')}: {row}")
    out.append((f"    stem {tagged_value(h.get('stem'), unit)}, " if unit != "ratio" else "    ")
               + f"stem / H1 face height {tagged_value(h.get('stem_h1'), 'ratio')}")
    for k, v in h.get("report", {}).items():
        if isinstance(v, list):
            out.append(f"    report {k}: {v[0]['value']} {v[0]['unit']} ({v[0]['confidence']})")
    for cls, v in h.get("held_out", {}).items():
        out.append(f"    held-out {cls}: face width x{v['face_w'][0]['value']}, height x{v['face_h'][0]['value']}")
    for key, chars in h.get("left_out", {}).items():
        need = f"all of {HANGUL_STEM}" if key == "stem" else f"{CLASS_MIN} different syllables of its list"
        out.append(f"    left out: {key}, read on {chars} only; it needs {need}")
    return out


def load_json(p):
    with open(p) as fh:
        return json.load(fh)


def save_json(obj, p):
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ rendering
def rasterize(face, text, px, pad=None, features=None, ss=4):
    """Coverage image (numpy, 0 white to 1 ink) of one shaped line, drawn from outlines with nonzero fill.
    No hinting. Rows run top to bottom. Returns (image, baseline row, px per unit)."""
    import numpy as np
    s = px / face.upm
    pad = int(px * 0.4) if pad is None else pad
    asc = max(face.font["hhea"].ascent, face.upm * 0.95)
    desc = min(face.font["hhea"].descent, -face.upm * 0.3)
    glyphs = face.shape(text, features)
    W = int(sum(a for _, _, a in glyphs) * s) + 2 * pad + 2
    H = int((asc - desc) * s) + 2 * pad
    base = pad + asc * s
    edges = []
    x = pad
    for name, dx, a in glyphs:
        p = FlatPen(face.gs)
        face.gs[name].draw(p)
        for poly in p.polys:
            pts = [((x + (dx + q[0]) * s) * ss, (base - q[1] * s) * ss) for q in poly]
            for i in range(len(pts)):
                edges.append(pts[i] + pts[(i + 1) % len(pts)])
        x += a * s
    img = np.zeros((H * ss, W * ss), dtype=np.uint8)
    if edges:
        E = np.array(edges)
        x0, y0, x1, y1 = E.T
        for row in range(H * ss):
            yc = row + 0.5
            sel = ((y0 <= yc) & (y1 > yc)) | ((y1 <= yc) & (y0 > yc))
            if not sel.any():
                continue
            t = (yc - y0[sel]) / (y1[sel] - y0[sel])
            xs = x0[sel] + t * (x1[sel] - x0[sel])
            d = np.where(y1[sel] > y0[sel], 1, -1)
            o = np.argsort(xs)
            xs, d = xs[o], d[o]
            wind = np.cumsum(d)
            for i in range(len(xs) - 1):
                if wind[i] != 0:
                    a0, a1 = int(round(xs[i])), int(round(xs[i + 1]))
                    img[row, max(a0, 0):max(a1, 0)] = 1
    cov = img.reshape(H, ss, W, ss).mean(axis=(1, 3))
    return cov, base, s


def save_png(cov, path):
    import numpy as np
    from PIL import Image
    Image.fromarray((255 - cov * 255).clip(0, 255).astype(np.uint8)).save(path)
