# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow"]
# ///
"""Hangul structural classes: set from the initial, the medial vowel and the final alone, and right on syllables
outside the measuring lists. The fit's subset keeps the Hangul, and check_font.py does not gate it yet."""
import os
import tempfile
import unittest

from fontTools.ttLib import TTFont

import check_font
import fontlib as L
import testfonts as T

# Labelled by hand from where the vowel stands (beside the initial, under it, or both) and whether a final sits
# under them. None is in a measuring list; they include double initials, compound vowels and compound finals.
HAND_LABELLED = {
    "H1": "펴캬얘예해띠",
    "H2": "뷰표쿠효뜨꾜",
    "H3": "쇠퇴뒤희꽈",
    "H4": "핥밖넋졌힣",
    "H5": "몫볶흙숯읗",
    "H6": "횝꿩뵘괌쀍읭",
}
# ㄱ and ㅏ as compatibility jamo, then as conjoining jamo, a Latin letter, the code points either side of the
# syllable block, two syllables, nothing.
NOT_SYLLABLES = ["\u3131", "\u314f", "\u1100", "\u1161", "A", "\uabff", "\ud7a4", "\uac00\ub098", ""]


class Classes(unittest.TestCase):
    def test_syllables_outside_the_lists_get_their_structural_class(self):
        listed = set("".join(L.HANGUL_CLASSES.values()))
        for cls, chars in HAND_LABELLED.items():
            for c in chars:
                with self.subTest(syllable=c):
                    self.assertNotIn(c, listed)
                    self.assertEqual(L.hangul_class(c), cls)

    def test_both_ends_of_the_syllable_block(self):
        self.assertEqual(L.hangul_class("\uac00"), "H1")  # 가: ㄱ ㅏ
        self.assertEqual(L.hangul_class("\ud7a3"), "H4")  # 힣: ㅎ ㅣ ㅎ

    def test_other_characters_have_no_class(self):
        for c in NOT_SYLLABLES:
            with self.subTest(character=repr(c)):
                self.assertIsNone(L.hangul_class(c))

    def test_each_list_holds_its_class_only_and_no_syllable_twice(self):
        listed = "".join(L.HANGUL_CLASSES.values())
        self.assertEqual(len(listed), len(set(listed)))
        for cls, chars in L.HANGUL_CLASSES.items():
            for c in chars:
                with self.subTest(cls=cls, syllable=c):
                    self.assertEqual(L.hangul_class(c), cls)

    def test_the_held_out_syllables_are_outside_the_lists_and_in_their_class(self):
        listed = set("".join(L.HANGUL_CLASSES.values()))
        for cls, chars in L.HANGUL_HELD_OUT.items():
            for c in chars:
                with self.subTest(cls=cls, syllable=c):
                    self.assertNotIn(c, listed)
                    self.assertEqual(L.hangul_class(c), cls)

    def test_the_stem_and_stroke_syllables_are_measured_in_their_classes(self):
        self.assertTrue(set(L.HANGUL_STEM) <= set(L.HANGUL_CLASSES["H1"]))
        self.assertTrue(set(L.HANGUL_HSTROKE) - {L.HANGUL_ANCHOR} <= set(L.HANGUL_CLASSES["H2"]))
        self.assertTrue(set(L.HANGUL_OVERSHOOT) <= set(L.HANGUL_CLASSES["H2"]))
        self.assertNotIn(L.HANGUL_ANCHOR, "".join(L.HANGUL_CLASSES.values()))

    def test_the_korean_sample_lines_set_every_listed_syllable_between_two_anchors(self):
        a = L.HANGUL_ANCHOR
        for line, chars in zip(L.SAMPLE_LINES_KO, L.HANGUL_CLASSES.values()):
            self.assertEqual(line[0::2], a * (len(chars) + 1))
            self.assertEqual(line[1::2], chars)


class Coverage(unittest.TestCase):
    def test_the_fit_subset_keeps_every_modern_syllable(self):
        self.assertIn("U+AC00-D7A3", L.charset_unicodes(["korean"]))

    def test_check_font_does_not_gate_korean_coverage(self):
        # Which Hangul a build must cover is a later step's gate: until then check_font.py has no list for it.
        with tempfile.TemporaryDirectory() as d:
            font = TTFont(T.hangul_vf(os.path.join(d, "hangul.ttf")), lazy=False)
        G = check_font.Gates()
        check_font.gate_coverage(G, font, ["korean"])
        self.assertEqual([row[:3] for row in G.rows], [("coverage", "korean", "INFO")])


if __name__ == "__main__":
    unittest.main()
