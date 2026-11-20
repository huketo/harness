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
        for name, latin in (("both", True), ("hangul", False)):
            T.hangul_vf(p(f"{name}.ttf"), latin=latin)
            r = T.run("measure_font.py", p(f"{name}.ttf"), "--out", p(f"{name}.json"))
            assert r.returncode == 0, r.stderr
        cls.both, cls.hangul = load(p("both.json")), load(p("hangul.json"))

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


class Segmentation(Scratch):
    """Syllables are cut at the 으 anchors; without them, at the widest gaps, and only when those stand clearly
    apart from the gaps inside a syllable. The H1 glyph is a ring and a stem 120 units apart."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        T.hangul_vf(p("tight.ttf"), latin=False, adv=760)  # 40 + 80 units between syllables: the same 120
        T.hangul_vf(p("loose.ttf"), latin=False, adv=1000)  # 280 + 80 between syllables

    def measure(self, font, text):
        png = self.p(f"{os.path.basename(font)}-{len(text)}-{text[:2]}.png")
        sheet(font, [text], png)
        return T.run("measure_image.py", png, "--text", text, "--out", png + ".json")

    def test_refuses_a_line_without_anchors_whose_gaps_do_not_fall_in_two_groups(self):
        r = self.measure(self.p("tight.ttf"), "이이이이")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("gaps", r.stderr)
        self.assertIn(L.HANGUL_ANCHOR, r.stderr)

    def test_cuts_a_line_without_anchors_at_its_widest_gaps_when_they_stand_apart(self):
        r = self.measure(self.p("loose.ttf"), "이이이이")
        self.assertEqual(r.returncode, 0, r.stderr)
        h1 = load(self.p("loose.ttf-4-이이.png.json"))["hangul"]["classes"]["H1"]
        self.assertAlmostEqual(value(h1["aspect"], "ratio"), 640 / 860, delta=0.015)

    def test_cuts_at_the_anchors_whatever_the_gaps(self):
        r = self.measure(self.p("tight.ttf"), "으이으이으")
        self.assertEqual(r.returncode, 0, r.stderr)
        h1 = load(self.p("tight.ttf-5-으이.png.json"))["hangul"]["classes"]["H1"]
        self.assertAlmostEqual(value(h1["aspect"], "ratio"), 640 / 860, delta=0.015)


if __name__ == "__main__":
    unittest.main()
