# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow"]
# ///
"""Hangul measurement from a font file and from a screenshot: every value tagged with its unit, ratios that agree
between the two, and a screenshot split into syllables at the anchors or refused."""
import json
import os
import shutil
import tempfile
import unittest

import fontlib as L
import measure_image
import testfonts as T

PX = 100  # pixels per em of the rendered sheets


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def tagged(tree):
    """Every tagged value in a hangul object, with its path. Lists of names ("units", "cut_at") are not values."""
    if isinstance(tree, list):
        yield from (("", v) for v in tree if isinstance(v, dict))
    elif isinstance(tree, dict):
        for k, v in tree.items():
            yield from ((f"{k}.{p}" if p else k, t) for p, t in tagged(v))


def value(entries, unit):
    got = [e["value"] for e in entries if e["unit"] == unit]
    return got[0] if got else None


def sheet(font, lines, path, wght=400):
    static = T.instance(font, path + ".ttf", wght)
    measure_image.render_sheet(L.Face(static, subset_text=L.MEASURE_TEXT + L.HANGUL_TEXT), lines, PX, path)
    return path


class Scratch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="mf-hangul-")
        cls.p = staticmethod(lambda *n: os.path.join(cls.dir, *n))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)


class FontFile(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        for name, latin in (("both", True), ("hangul", False), ("cap", "H")):
            T.hangul_vf(p(f"{name}.ttf"), latin=latin)
            r = T.run("measure_font.py", p(f"{name}.ttf"), "--out", p(f"{name}.json"))
            assert r.returncode == 0, r.stderr
        cls.both, cls.hangul, cls.cap = load(p("both.json")), load(p("hangul.json")), load(p("cap.json"))

    def test_every_hangul_value_carries_one_of_the_three_units(self):
        for m in (self.both, self.hangul):
            values = list(tagged(m["hangul"]))
            self.assertGreater(len(values), 50)
            for path, v in values:
                with self.subTest(path=path):
                    self.assertIn(v["unit"], L.UNITS)

    def test_a_font_with_a_latin_H_gives_lengths_at_cap_700_and_per_1000_em(self):
        h = self.both["hangul"]
        self.assertEqual(h["units"], ["cap700", "em1000", "ratio"])
        H1 = h["classes"]["H1"]
        # cap height 700 in a 1250 em: cap700 lengths are font units, em1000 lengths are 0.8 of them
        self.assertEqual(value(H1["face_h"], "cap700"), 860)
        self.assertEqual(value(H1["face_h"], "em1000"), 688)
        self.assertAlmostEqual(value(H1["face_h_cap"], "ratio"), 860 / 700, places=3)
        self.assertEqual(value(h["stem"], "cap700"), 80)
        self.assertEqual(value(h["adv"], "em1000"), 800)
        self.assertAlmostEqual(value(h["adv_cap"], "ratio"), 1000 / 700, places=3)
        self.assertTrue(h["fixed_width"])

    def test_a_font_without_latin_gives_lengths_per_1000_em_and_ratios(self):
        m = self.hangul
        self.assertNotIn("widths", m)
        self.assertIsNone(m["cap_em"])
        self.assertEqual(m["hangul"]["units"], ["em1000", "ratio"])
        self.assertEqual({v["unit"] for _, v in tagged(m["hangul"])}, {"em1000", "ratio"})
        self.assertEqual(value(m["hangul"]["classes"]["H1"]["face_h"], "em1000"), 688)

    def test_a_latin_H_alone_gives_lengths_at_cap_700(self):
        m = self.cap
        self.assertNotIn("widths", m)  # no x, n or o: the Latin is not measured, the H still sets the cap
        h = m["hangul"]
        self.assertEqual(h["units"], ["cap700", "em1000", "ratio"])
        H1 = h["classes"]["H1"]
        self.assertEqual(value(H1["face_h"], "cap700"), 860)
        self.assertAlmostEqual(value(H1["face_h_cap"], "ratio"), 860 / 700, places=3)
        self.assertEqual(value(h["stem"], "cap700"), 80)
        self.assertAlmostEqual(value(h["adv_cap"], "ratio"), 1000 / 700, places=3)

    def test_ratios_and_the_report(self):
        h = self.both["hangul"]
        self.assertAlmostEqual(value(h["stem_h1"], "ratio"), 80 / 860, places=4)
        self.assertAlmostEqual(value(h["classes"]["H1"]["aspect"], "ratio"), 640 / 860, places=4)
        self.assertAlmostEqual(value(h["classes"]["H2"]["face_w_h1"], "ratio"), 700 / 640, places=3)
        self.assertEqual(value(h["report"]["hstroke"], "cap700"), 64)  # ㅡ is the thin stroke, 0.8 of the stem
        self.assertEqual(value(h["report"]["overshoot"], "cap700"), 12)
        self.assertAlmostEqual(value(h["report"]["contrast"], "ratio"), 0.8, places=3)

    def test_sides_and_the_centre_in_the_advance(self):
        H1 = self.both["hangul"]["classes"]["H1"]
        self.assertEqual(value(H1["side"], "cap700"), (80 + 1000 - 720) / 2)
        self.assertEqual(value(H1["side_asym"], "cap700"), 1000 - 720 - 80)
        self.assertAlmostEqual(value(H1["center_adv"], "ratio"), 400 / 1000, places=4)

    def test_a_stem_to_solve_needs_the_latin_n(self):
        r = T.run("measure_font.py", self.p("hangul.ttf"), "--stem", "80")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("--stem", r.stderr)

    def test_the_held_out_syllables_are_measured_against_the_list(self):
        held = self.both["hangul"]["held_out"]
        self.assertEqual(set(held), set(L.HANGUL_CLASSES))
        for cls, v in held.items():  # same drawing per class, but the H2 list holds 오, 12 units taller
            with self.subTest(cls=cls):
                self.assertAlmostEqual(value(v["face_h"], "ratio"), 680 / 681.5 if cls == "H2" else 1.0, places=3)


class Screenshot(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        T.hangul_vf(p("both.ttf"), latin=True)
        r = T.run("measure_font.py", p("both.ttf"), "--out", p("file.json"))
        assert r.returncode == 0, r.stderr
        cls.file = load(p("file.json"))["hangul"]
        sheet(p("both.ttf"), L.SAMPLE_LINES_KO, p("ko.png"))
        cls.ko = T.run("measure_image.py", p("ko.png"), "--text", "|".join(L.SAMPLE_LINES_KO), "--out", p("ko.json"))
        sheet(p("both.ttf"), ["HOH", *L.SAMPLE_LINES_KO], p("mixed.png"))
        cls.mixed = T.run("measure_image.py", p("mixed.png"), "--text", "|".join(["HOH", *L.SAMPLE_LINES_KO]),
                          "--out", p("mixed.json"))

    def test_a_hangul_only_screenshot_gives_ratios_only(self):
        self.assertEqual(self.ko.returncode, 0, self.ko.stderr)
        h = load(self.p("ko.json"))["hangul"]
        self.assertEqual(h["units"], ["ratio"])
        self.assertEqual({v["unit"] for _, v in tagged(h)}, {"ratio"})
        for cls, c in h["classes"].items():
            with self.subTest(cls=cls):
                self.assertFalse({"adv", "side", "side_asym", "center_adv", "cx", "cy"} & set(c))
        self.assertNotIn("adv", h)

    def test_its_ratios_land_on_the_font_files(self):
        h = load(self.p("ko.json"))["hangul"]
        for cls in L.HANGUL_CLASSES:
            for key in ("aspect", "face_w_h1", "face_h_h1"):
                with self.subTest(cls=cls, key=key):
                    want = value(self.file["classes"][cls][key], "ratio")
                    self.assertAlmostEqual(value(h["classes"][cls][key], "ratio") / want, 1, delta=0.02)
        self.assertAlmostEqual(value(h["stem_h1"], "ratio") / value(self.file["stem_h1"], "ratio"), 1, delta=0.05)

    def test_the_anchor_distances_are_reported_and_never_a_target(self):
        h = load(self.p("ko.json"))["hangul"]
        for cls in L.HANGUL_CLASSES:
            with self.subTest(cls=cls):
                self.assertAlmostEqual(value(h["report"]["pitch_h1"][cls], "ratio"), 2000 / 860, delta=0.05)

    def test_a_latin_H_in_the_same_screenshot_gives_cap_700_lengths(self):
        self.assertEqual(self.mixed.returncode, 0, self.mixed.stderr)
        h = load(self.p("mixed.json"))["hangul"]
        self.assertEqual(h["units"], ["cap700", "ratio"])
        self.assertAlmostEqual(value(h["classes"]["H1"]["face_h"], "cap700"), 860, delta=860 * 0.015)


class Lines(Scratch):
    """One line of Hangul rendered and read back. The H1 glyph is a ring and a stem 120 units apart."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        T.hangul_vf(p("tight.ttf"), latin=False, adv=760)  # 40 + 80 units between syllables: the same 120
        T.hangul_vf(p("loose.ttf"), latin=False, adv=1000)  # 280 + 80 between syllables

    def measure(self, font, text, read_as=None):
        """Render text in the font, then read the screenshot as read_as (by default the same text)."""
        png = self.p(f"{os.path.basename(font)}-{text}-{read_as}.png")
        sheet(font, [text], png)
        return T.run("measure_image.py", png, "--text", read_as or text, "--out", png + ".json")

    def read(self, font, text):
        return load(self.p(f"{os.path.basename(font)}-{text}-None.png.json"))["hangul"]


class Segmentation(Lines):
    """Syllables are cut at the 으 anchors; without them, at the widest gaps, and only when those stand clearly
    apart from the gaps inside a syllable."""

    def test_refuses_a_line_without_anchors_whose_gaps_do_not_fall_in_two_groups(self):
        r = self.measure(self.p("tight.ttf"), "이이이이")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("gaps", r.stderr)
        self.assertIn(L.HANGUL_ANCHOR, r.stderr)

    def test_refuses_a_line_without_anchors_that_has_one_group_of_ink_per_character(self):
        # 이이 in the tight font is four groups of ink with gaps of one width between them. Read as four syllables,
        # no gap is left inside a syllable to show that the cuts stand apart, so the line is refused.
        r = self.measure(self.p("tight.ttf"), "이이", read_as="가나이니")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("gap", r.stderr)
        self.assertIn(L.HANGUL_ANCHOR, r.stderr)

    def test_refuses_lines_of_one_character_without_anchors(self):
        # Three lines of 이이 set tight, read as 이, 니 and 미: one character to a line leaves no gap between two
        # syllables to check, so 이이 would read as one wide syllable.
        png = self.p("tight-one-per-line.png")
        sheet(self.p("tight.ttf"), ["이이"] * 3, png)
        r = T.run("measure_image.py", png, "--text", "이|니|미", "--out", png + ".json")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("one character", r.stderr)
        self.assertIn(L.HANGUL_ANCHOR, r.stderr)
        self.assertFalse(os.path.exists(png + ".json"))

    def test_cuts_a_line_without_anchors_at_its_widest_gaps_when_they_stand_apart(self):
        r = self.measure(self.p("loose.ttf"), "가나이니")
        self.assertEqual(r.returncode, 0, r.stderr)
        h1 = self.read(self.p("loose.ttf"), "가나이니")["classes"]["H1"]
        self.assertAlmostEqual(value(h1["aspect"], "ratio"), 640 / 860, delta=0.015)

    def test_cuts_at_the_anchors_whatever_the_gaps(self):
        r = self.measure(self.p("tight.ttf"), "으가으이으")
        self.assertEqual(r.returncode, 0, r.stderr)
        h1 = self.read(self.p("tight.ttf"), "으가으이으")["classes"]["H1"]
        self.assertAlmostEqual(value(h1["aspect"], "ratio"), 640 / 860, delta=0.015)


class OneSyllable(Lines):
    """A class is a mean over different syllables, and the stem a median over 이, 니 and 미: one syllable read again
    and again is still one syllable."""

    def test_refuses_a_screenshot_where_no_class_has_two_different_syllables(self):
        for text in ("이이이이", "으이으이으이으이으"):
            with self.subTest(text=text):
                r = self.measure(self.p("loose.ttf"), text)
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertIn("two different syllables", r.stderr)

    def test_a_class_with_one_syllable_is_left_out(self):
        text = "으이으이으고으노으"  # H1 is 이 alone, H2 has 고 and 노
        r = self.measure(self.p("loose.ttf"), text)
        self.assertEqual(r.returncode, 0, r.stderr)
        h = self.read(self.p("loose.ttf"), text)
        self.assertEqual(set(h["classes"]), {"H2"})
        self.assertNotIn("stem_h1", h)
        self.assertNotIn("face_w_h1", h["classes"]["H2"])
        self.assertEqual(h["left_out"], {"H1": "이", "stem": "이"})

    def test_the_stem_needs_all_three_of_its_syllables(self):
        for text, stem in (("으이으니으가으", False), ("으이으니으미으", True)):
            with self.subTest(text=text):
                r = self.measure(self.p("loose.ttf"), text)
                self.assertEqual(r.returncode, 0, r.stderr)
                h = self.read(self.p("loose.ttf"), text)
                self.assertEqual(set(h["classes"]), {"H1"})
                self.assertEqual("stem_h1" in h, stem)
                if stem:
                    self.assertAlmostEqual(value(h["stem_h1"], "ratio"), 80 / 860, delta=0.005)
                else:
                    self.assertEqual(h["left_out"], {"stem": "이니"})


if __name__ == "__main__":
    unittest.main()
