# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow", "skia-pathops"]
# ///
"""Hangul targets: make_targets.py merges values of one unit only, and make_targets.py and fit_font.py run on
Hangul measurements without any Latin number. The fit solves the weight from the Hangul stem as a length when a
reference gave one, else from the stem ratio, steps the second weight from it, and states each Hangul target in
the y instance's own units."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from fontTools.ttLib import TTFont

import fontlib as L
import measure_image
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
        """make_targets.py on these measurements, each run in files of its own."""
        run = len(os.listdir(self.dir))
        paths = []
        for i, m in enumerate(measurements):
            paths.append(T.write(self.p(f"m{i}-{run}.json"), json.dumps(m, ensure_ascii=False)))
        out = self.p(f"targets-{run}.json")
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

    def test_a_tag_without_a_value_or_a_unit_is_refused(self):
        em = [v(560.0, "em1000")]
        cases = {  # each reference's face_w, in order
            "a tag where a list of tags belongs": [{"unit": "cap700"}],
            "a tag holding a list": [{"unit": "cap700", "value": em}],
            "a tag, then a list of tags": [{"unit": "cap700"}, em],
            "a list of tags, then a tag": [em, {"unit": "cap700"}],
            "no value": [[{"unit": "cap700"}]],
            "no unit": [[{"value": 560.0}]],
            "a flag for a value": [[v(True, "ratio")]],
            "an unknown confidence": [[v(560.0, "em1000", "sure")]],
            "a bare number": [560.0],
            "an empty list": [[]],
            "two values in one unit": [[v(560.0, "em1000"), v(580.0, "em1000")]],
        }
        for case, face_w in cases.items():
            with self.subTest(case=case):
                r, out = self.targets(*(measurement("file", {"H1": {"face_w": f}}) for f in face_w))
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertIn("H1.face_w", r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                self.assertFalse(os.path.exists(out))

    def test_fixed_width_and_proportional_references_give_one_advance_form(self):
        def fixed(adv):
            return measurement("file", {"H1": {"aspect": [v(0.9, "ratio")]}}, fixed_width=True,
                               adv=[v(adv, "em1000")])

        def proportional(adv):
            return measurement("file", {"H1": {"aspect": [v(0.9, "ratio")], "adv": [v(adv, "em1000")]}},
                               fixed_width=False)
        for refs, want in (((fixed(1000.0), fixed(990.0), proportional(940.0)), True),
                           ((proportional(940.0), proportional(950.0), fixed(1000.0)), False)):
            with self.subTest(fixed_width=want):
                r, out = self.targets(*refs)
                ok(self, r)
                h = load(out)["hangul"]
                self.assertIs(h["fixed_width"], want)
                self.assertEqual("adv" in h, want)
                self.assertEqual("adv" in h["classes"]["H1"], not want)
                self.assertEqual(h["spread"]["fixed_width"], [r_["hangul"]["fixed_width"] for r_ in refs])

    def test_an_advance_that_does_not_match_its_reference_fixed_width_is_refused(self):
        for case, m in (
                ("per class, fixed width", measurement("file", {"H1": {"adv": [v(940.0, "em1000")]}},
                                                       fixed_width=True)),
                ("font-wide, proportional", measurement("file", {"H1": {"aspect": [v(0.9, "ratio")]}},
                                                        fixed_width=False, adv=[v(1000.0, "em1000")])),
                ("no fixed_width", measurement("file", {"H1": {"adv": [v(940.0, "em1000")]}}))):
            with self.subTest(case=case):
                r, out = self.targets(m)
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertIn("fixed_width", r.stderr)
                self.assertFalse(os.path.exists(out))

    def test_hangul_is_left_out_when_the_scripts_have_no_korean(self):
        m = measurement("image", {"H1": {"aspect": [v(0.75, "ratio")]}})
        r, out = self.targets(m, args=("--scripts", "latin"))
        ok(self, r)
        self.assertNotIn("hangul", load(out))
        self.assertIn("korean", r.stdout)


SHOT_PX = 200  # pixels per em of the screenshots: a stem of 96 units at 1250 per em is 15 px


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
        cls.runs = {}
        two_weights = ("--style", "Regular:400", "--style", "Bold:700")
        # A reference font with Hangul only, at wght 500: no Latin number, lengths per 1000 em and ratios.
        T.instance(T.hangul_vf(p("ref-hangul.ttf"), latin=False), p("ref-hangul-500.ttf"), 500)
        cls.chain("file", ("measure_font.py", p("ref-hangul-500.ttf")), ("--scripts", "korean", *two_weights))
        # A screenshot of the same reference's Hangul alone: ratios only.
        cls.shot(p("ref-hangul-500.ttf"), L.SAMPLE_LINES_KO, p("ratio.png"))
        cls.chain("ratio", ("measure_image.py", p("ratio.png"), "--text", "|".join(L.SAMPLE_LINES_KO)),
                  ("--scripts", "korean", *two_weights))
        # A screenshot with a Latin H and no n, of a face whose Hangul is drawn 1.2 times larger against its cap
        # height, at wght 400. Its Hangul stem is 96 at cap 700, which the base draws at wght 500; its stem over its
        # H1 face height is the base's at wght 400.
        T.instance(T.hangul_vf(p("ref-big.ttf"), latin=True, scale=1.2), p("ref-big-400.ttf"), 400)
        lines = ["HOH", *L.SAMPLE_LINES_KO]
        cls.shot(p("ref-big-400.ttf"), lines, p("cap.png"))
        cls.chain("cap", ("measure_image.py", p("cap.png"), "--text", "|".join(lines)), ("--scripts", "latin,korean"))
        cls.runs["measure cap fitted"] = T.run("measure_font.py", p("build-cap", "TesseraSans-Regular.fit.ttf"),
                                               "--out", p("m-cap-fitted.json"))
        # A reference with Latin too, at the default wght 400: the Hangul lengths are at cap height 700.
        cls.chain("latin", ("measure_font.py", cls.base), ("--scripts", "latin,korean"))
        cls.runs["measure latin fitted"] = T.run("measure_font.py", p("build-latin", "TesseraSans-Regular.fit.ttf"),
                                                 "--out", p("m-latin-fitted.json"))

    @classmethod
    def chain(cls, name, measure, targets):
        """Measure a reference, make targets from it and fit the base to them, in files named after `name`."""
        p = cls.p
        cls.runs[f"measure {name}"] = T.run(*measure, "--out", p(f"m-{name}.json"))
        cls.runs[f"targets {name}"] = T.run("make_targets.py", p(f"m-{name}.json"), "--family", T.NEW_FAMILY,
                                            *targets, "--out", p(f"targets-{name}.json"))
        cls.runs[f"fit {name}"] = T.run("fit_font.py", cls.base, p(f"targets-{name}.json"), "--base-json",
                                        p("base.json"), "--out-dir", p(f"build-{name}"))

    @staticmethod
    def shot(font, lines, path):
        measure_image.render_sheet(L.Face(font, subset_text=L.MEASURE_TEXT + L.HANGUL_TEXT), lines, SHOT_PX, path)

    def test_every_step_ran(self):
        for step, r in self.runs.items():
            with self.subTest(step=step):
                ok(self, r)

    def style(self, log, i):
        return load(self.p(log, "fit-log.json"))["styles"][i]

    def test_without_a_stem_length_the_first_weight_is_solved_from_the_hangul_stem_ratio(self):
        self.assertEqual(load(self.p("targets-ratio.json"))["hangul"].get("stem"), None)
        s = self.style("build-ratio", 0)
        self.assertAlmostEqual(s["y_location"]["wght"], 500, delta=15)
        self.assertEqual(s["hangul"]["weight_from"], "stem_h1")
        stem = s["hangul"]["stem_h1"]
        self.assertAlmostEqual(stem["got"], stem["target"], delta=0.001)

    def test_a_stem_per_1000_em_sets_the_weight_of_a_reference_without_latin(self):
        s = self.style("build-file", 0)
        self.assertEqual(s["hangul"]["weight_from"], "stem em1000")
        self.assertAlmostEqual(s["y_location"]["wght"], 500, delta=3)
        stem = s["hangul"]["stem"]
        self.assertEqual(stem["from"], "em1000")
        self.assertAlmostEqual(stem["base"], stem["target"], delta=0.5)

    def test_a_stem_at_cap_700_sets_the_weight_when_the_targets_have_no_n(self):
        t = load(self.p("targets-cap.json"))
        self.assertNotIn("n_stem", t["targets"])
        want = L.tagged_value(t["hangul"]["stem"], "cap700")
        self.assertAlmostEqual(want, 96, delta=96 * 0.02)
        s = self.style("build-cap", 0)
        self.assertEqual(s["hangul"]["weight_from"], "stem cap700")
        self.assertAlmostEqual(s["y_location"]["wght"], 500, delta=15)  # the stem ratio alone would give 400
        stem = s["hangul"]["stem"]
        self.assertEqual(stem["from"], "cap700")
        self.assertAlmostEqual(stem["base"] / stem["target"], 1, delta=0.01)
        fitted = L.tagged_value(load(self.p("m-cap-fitted.json"))["hangul"]["stem"], "cap700")
        self.assertAlmostEqual(fitted / want, 1, delta=0.015)

    def test_the_second_weight_steps_from_the_first_by_the_weight_class(self):
        for name, weight_from in (("ratio", "stem_h1"), ("file", "stem em1000")):
            with self.subTest(reference=name):
                first, second = self.style(f"build-{name}", 0), self.style(f"build-{name}", 1)
                self.assertAlmostEqual(second["y_location"]["wght"], first["y_location"]["wght"] + 300, delta=0.01)
                self.assertEqual(second["hangul"]["weight_from"], f"{weight_from}, stepped from the first style")

    def test_the_two_weights_have_different_outlines(self):
        a = outline_hash(self.p("build-ratio", "TesseraSans-Regular.fit.ttf"), L.HANGUL_CLASSES["H1"])
        b = outline_hash(self.p("build-ratio", "TesseraSans-Bold.fit.ttf"), L.HANGUL_CLASSES["H1"])
        self.assertNotEqual(a, b)

    def test_lengths_per_1000_em_resolve_to_the_y_instance(self):
        face_h = self.style("build-file", 0)["hangul"]["classes"]["H1"]["face_h"]
        self.assertEqual(face_h["from"], "em1000")
        self.assertAlmostEqual(face_h["target"], 880, delta=1)
        self.assertAlmostEqual(face_h["base"], 880, delta=2)

    def test_lengths_at_cap_700_resolve_against_the_y_instance_cap(self):
        s = self.style("build-latin", 0)
        self.assertEqual(s["hangul"]["weight_from"], "n_stem")
        face_h = s["hangul"]["classes"]["H1"]["face_h"]
        self.assertEqual(face_h["from"], "cap700")
        self.assertAlmostEqual(face_h["target"], 860, delta=1)
        self.assertAlmostEqual(face_h["base"], 860, delta=2)

    def test_hangul_targets_are_refused_on_a_base_without_hangul(self):
        p = self.p
        latin_only = T.glyf_vf(p("latin-only[wght].ttf"))
        assert T.approve(latin_only, self.ofl, p("base-latin-only.json")).returncode == 0
        r = T.run("fit_font.py", latin_only, p("targets-file.json"), "--base-json", p("base-latin-only.json"),
                  "--out-dir", p("build-latin-only"))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("refused", r.stderr)
        self.assertIn("H1 syllables", r.stderr)
        self.assertFalse(os.path.exists(p("build-latin-only", "TesseraSans-Regular.fit.ttf")))

    def test_the_em_rescale_keeps_the_ratios_to_the_cap(self):
        want = load(self.p("m-latin.json"))["hangul"]["classes"]
        got = load(self.p("m-latin-fitted.json"))["hangul"]["classes"]
        for cls in L.HANGUL_CLASSES:
            with self.subTest(cls=cls):
                self.assertAlmostEqual(got[cls]["face_h_cap"][0]["value"], want[cls]["face_h_cap"][0]["value"],
                                       delta=0.003)


if __name__ == "__main__":
    unittest.main()
