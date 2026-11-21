# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "uharfbuzz", "numpy", "pillow"]
# ///
"""The collision guard (space_font.py) and the kerning gate (check_font.py) read a pair as HarfBuzz sets it, with the
glyphs a contextual alternate puts there, and the guard kerns those glyphs."""
import io
import os
import shutil
import tempfile
import unittest

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

import check_font
import fontlib as L
import space_font
import testfonts as T

MIN_GAP = 6


def ink_gap(font, pair):
    """The gap between the two glyphs HarfBuzz sets for `pair`, from their ink boxes (every glyph here is
    rectangles over the same rows), and the glyph names."""
    (ga, xa, adv), (gb, xb, _) = L.Face(font).shape(pair, {"kern": True, "liga": False})
    gs, box = font.getGlyphSet(), {}
    for name in (ga, gb):
        pen = BoundsPen(gs)
        gs[name].draw(pen)
        box[name] = pen.bounds
    return adv + xb + box[gb][0] - (xa + box[ga][2]), (ga, gb)


def kerning_gate(font):
    G = check_font.Gates()
    check_font.gate_kerning(G, L.Face(font), MIN_GAP)
    (row,) = [r for r in G.rows if r[1] == "collisions"]
    return row[2], row[3]


class GuardReadsThePairAsShaped(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mf-guard-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.font = TTFont(T.contextual_alternate(os.path.join(self.dir, "alt.ttf")))

    def test_the_guard_kerns_the_glyphs_a_contextual_alternate_sets(self):
        gap, glyphs = ink_gap(self.font, "no")
        self.assertEqual(glyphs, ("n", "o.alt"))
        self.assertEqual(gap, 110 - T.ALTERNATE_SHIFT)
        state, detail = kerning_gate(self.font)
        self.assertEqual(state, "FAIL", detail)
        self.assertIn("no", detail)
        log = {}
        space_font.guard(self.font, MIN_GAP, False, log)
        self.assertIn({"pair": "no", "open": MIN_GAP - gap, "gap_before": gap}, log["guard"])
        buf = io.BytesIO()
        self.font.save(buf)
        guarded = TTFont(io.BytesIO(buf.getvalue()))
        self.assertEqual(ink_gap(guarded, "no"), (MIN_GAP, ("n", "o.alt")))
        self.assertEqual(kerning_gate(guarded)[0], "PASS")


if __name__ == "__main__":
    unittest.main()
