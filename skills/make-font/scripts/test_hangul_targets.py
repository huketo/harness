# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow", "skia-pathops"]
# ///
"""Hangul targets: make_targets.py merges values of one unit only, and make_targets.py and fit_font.py run on
Hangul measurements without any Latin number. The fit solves the weight from the Hangul stem ratio, steps the
second weight from it, and states each Hangul target in the y instance's own units."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from fontTools.ttLib import TTFont

import fontlib as L
import testfonts as T


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def ok(test, r):
    test.assertEqual(r.returncode, 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
    return r


def v(value, unit, confidence="high"):
    return {"value": value, "unit": unit, "confidence": confidence}


def measurement(source, classes, **top):
    return {"source": source, "cap_em": None, "confidence": {}, "hangul": {"classes": classes, **top}}


def outline_hash(path, chars):
    f = TTFont(path)
    glyf, cmap = f["glyf"], f.getBestCmap()
    h = hashlib.sha256()
    for c in chars:
        h.update(repr(list(glyf[cmap[ord(c)]].coordinates)).encode())
    return h.hexdigest()


class Scratch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="mf-hangul-targets-")
        cls.p = staticmethod(lambda *n: os.path.join(cls.dir, *n))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def targets(self, *measurements, args=("--scripts", "korean")):
        paths = []
        for i, m in enumerate(measurements):
            paths.append(T.write(self.p(f"m{i}-{self.id()}.json"), json.dumps(m, ensure_ascii=False)))
        out = self.p(f"targets-{self.id()}.json")
        r = T.run("make_targets.py", *paths, "--family", T.NEW_FAMILY, *args, "--out", out)
        return r, out


class Merge(Scratch):
    def test_values_in_different_units_are_never_merged(self):
        m1 = measurement("file", {"H1": {"face_w": [v(800.0, "cap700")], "aspect": [v(0.90, "ratio")]}})
        m2 = measurement("file", {"H1": {"face_w": [v(560.0, "em1000")], "aspect": [v(0.94, "ratio")]}})
        r, out = self.targets(m1, m2)
        ok(self, r)
        H1 = load(out)["hangul"]["classes"]["H1"]
        self.assertEqual(sorted((e["unit"], e["value"]) for e in H1["face_w"]), [("cap700", 800.0), ("em1000", 560.0)])
        self.assertEqual([(e["unit"], e["value"]) for e in H1["aspect"]], [("ratio", 0.92)])

    def test_values_of_one_unit_merge_by_confidence(self):
        m1 = measurement("image", {"H1": {"aspect": [v(0.90, "ratio", "high")]}})
        m2 = measurement("image", {"H1": {"aspect": [v(1.00, "ratio", "low")]}})
        r, out = self.targets(m1, m2)
        ok(self, r)
        got = load(out)["hangul"]["classes"]["H1"]["aspect"]
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0]["value"], (0.90 * 3 + 1.00) / 4, places=4)

    def test_a_unit_outside_the_three_is_refused(self):
        m = measurement("image", {"H1": {"face_w": [v(81.0, "px")]}})
        r, out = self.targets(m)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("px", r.stderr)
        self.assertFalse(os.path.exists(out))

    def test_hangul_measurements_without_latin_make_targets(self):
        m = measurement("image", {"H1": {"aspect": [v(0.75, "ratio")]}}, stem_h1=[v(0.1, "ratio")])
        r, out = self.targets(m, args=("--scripts", "korean", "--style", "Regular:400", "--style", "Bold:700"))
        ok(self, r)
        t = load(out)
        self.assertNotIn("n_stem", t["targets"])
        self.assertEqual([s for s in t["styles"] if "n_stem" in s], [])
        self.assertEqual(t["hangul"]["stem_h1"], [v(0.1, "ratio")])
        self.assertIsNone(t["cap_em"])

    def test_hangul_is_left_out_when_the_scripts_have_no_korean(self):
        m = measurement("image", {"H1": {"aspect": [v(0.75, "ratio")]}})
        r, out = self.targets(m, args=("--scripts", "latin"))
        ok(self, r)
        self.assertNotIn("hangul", load(out))
        self.assertIn("korean", r.stdout)


class Fit(Scratch):
    """One synthetic Latin and Hangul base, approved. The H1 face grows with the weight: 860 tall at wght 400, 880 at
    500, while the stem goes 80 to 96."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        cls.base = T.hangul_vf(p("LumenLedger[wght].ttf"), latin=True)
        cls.ofl = T.write(p("OFL.txt"), T.ofl_text())
        assert T.approve(cls.base, cls.ofl, p("base.json")).returncode == 0
        # A reference with Hangul only, at wght 500: no Latin number, lengths per 1000 em and ratios.
        T.instance(T.hangul_vf(p("ref-hangul.ttf"), latin=False), p("ref-hangul-500.ttf"), 500)
        cls.runs = {}
        cls.runs["measure"] = T.run("measure_font.py", p("ref-hangul-500.ttf"), "--out", p("m-hangul.json"))
        cls.runs["targets"] = T.run("make_targets.py", p("m-hangul.json"), "--family", T.NEW_FAMILY, "--scripts",
                                    "korean", "--style", "Regular:400", "--style", "Bold:700",
                                    "--out", p("targets-hangul.json"))
        cls.runs["fit"] = T.run("fit_font.py", cls.base, p("targets-hangul.json"), "--base-json", p("base.json"),
                                "--out-dir", p("build-hangul"))
        # A reference with Latin too, at the default wght 400: the Hangul lengths are at cap height 700.
        cls.runs["measure latin"] = T.run("measure_font.py", cls.base, "--out", p("m-both.json"))
        cls.runs["targets latin"] = T.run("make_targets.py", p("m-both.json"), "--family", T.NEW_FAMILY,
                                          "--scripts", "latin,korean", "--out", p("targets-both.json"))
        cls.runs["fit latin"] = T.run("fit_font.py", cls.base, p("targets-both.json"), "--base-json",
                                      p("base.json"), "--out-dir", p("build-both"))
        cls.runs["measure fitted"] = T.run("measure_font.py", p("build-both", "TesseraSans-Regular.fit.ttf"),
                                           "--out", p("m-fitted.json"))

    def test_every_step_ran(self):
        for step, r in self.runs.items():
            with self.subTest(step=step):
                ok(self, r)

    def style(self, log, i):
        return load(self.p(log, "fit-log.json"))["styles"][i]

    def test_the_first_weight_is_solved_from_the_hangul_stem_ratio(self):
        s = self.style("build-hangul", 0)
        self.assertAlmostEqual(s["y_location"]["wght"], 500, delta=3)
        self.assertEqual(s["hangul"]["weight_from"], "stem_h1")
        stem = s["hangul"]["stem_h1"]
        self.assertAlmostEqual(stem["got"], stem["target"], delta=0.001)

    def test_the_second_weight_steps_from_the_first_by_the_weight_class(self):
        first, second = self.style("build-hangul", 0), self.style("build-hangul", 1)
        self.assertAlmostEqual(second["y_location"]["wght"], first["y_location"]["wght"] + 300, delta=0.01)
        self.assertEqual(second["hangul"]["weight_from"], "stem_h1, stepped from the first style")

    def test_the_two_weights_have_different_outlines(self):
        a = outline_hash(self.p("build-hangul", "TesseraSans-Regular.fit.ttf"), L.HANGUL_CLASSES["H1"])
        b = outline_hash(self.p("build-hangul", "TesseraSans-Bold.fit.ttf"), L.HANGUL_CLASSES["H1"])
        self.assertNotEqual(a, b)

    def test_lengths_per_1000_em_resolve_to_the_y_instance(self):
        face_h = self.style("build-hangul", 0)["hangul"]["classes"]["H1"]["face_h"]
        self.assertEqual(face_h["from"], "em1000")
        self.assertAlmostEqual(face_h["target"], 880, delta=1)
        self.assertAlmostEqual(face_h["base"], 880, delta=2)

    def test_lengths_at_cap_700_resolve_against_the_y_instance_cap(self):
        s = self.style("build-both", 0)
        self.assertEqual(s["hangul"]["weight_from"], "n_stem")
        face_h = s["hangul"]["classes"]["H1"]["face_h"]
        self.assertEqual(face_h["from"], "cap700")
        self.assertAlmostEqual(face_h["target"], 860, delta=1)
        self.assertAlmostEqual(face_h["base"], 860, delta=2)

    def test_hangul_targets_are_refused_on_a_base_without_hangul(self):
        p = self.p
        latin_only = T.glyf_vf(p("latin-only[wght].ttf"))
        assert T.approve(latin_only, self.ofl, p("base-latin-only.json")).returncode == 0
        r = T.run("fit_font.py", latin_only, p("targets-hangul.json"), "--base-json", p("base-latin-only.json"),
                  "--out-dir", p("build-latin-only"))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("refused", r.stderr)
        self.assertIn("H1 syllables", r.stderr)
        self.assertFalse(os.path.exists(p("build-latin-only", "TesseraSans-Regular.fit.ttf")))

    def test_the_em_rescale_keeps_the_ratios_to_the_cap(self):
        want = load(self.p("m-both.json"))["hangul"]["classes"]
        got = load(self.p("m-fitted.json"))["hangul"]["classes"]
        for cls in L.HANGUL_CLASSES:
            with self.subTest(cls=cls):
                self.assertAlmostEqual(got[cls]["face_h_cap"][0]["value"], want[cls]["face_h_cap"][0]["value"],
                                       delta=0.003)


if __name__ == "__main__":
    unittest.main()
