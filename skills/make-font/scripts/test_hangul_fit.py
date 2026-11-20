# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow", "skia-pathops"]
# ///
"""The Hangul fit and its gates, on synthetic fonts. The fit moves the Hangul by one scale for all of it and a final
x and y scale per class, each within its limit; the compatibility jamo take the one scale alone; a composite
syllable is decomposed first; the Hangul wght is solved for the stem over the scale. check_font.py fails a Hangul
glyph the logged transform does not put where it is, gates KS X 1001 and counts the modern syllables, and reports
weight harmony as not run without a reference that measured Latin. The Latin n stem keeps a location where the wght
axis reaches it, and a later weight steps from the first one's location."""
import copy
import json
import os
import shutil
import tempfile
import unittest

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

import check_font
import fontlib as L
import measure_image
import testfonts as T

ROUNDING = 2  # units a fitted box edge may move by rounding: once at the transform, once at the em scale


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def ok(test, r):
    test.assertEqual(r.returncode, 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
    return r


def boxes(font):
    gs = font.getGlyphSet()
    out = {}
    for name in font.getGlyphOrder():
        p = BoundsPen(gs)
        gs[name].draw(p)
        out[name] = p.bounds
    return out


class Scratch(unittest.TestCase):
    """A temporary folder per class, and the script runs its setUpClass made (StepsRan checks them)."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="mf-hangul-fit-")
        cls.p = staticmethod(lambda *n: os.path.join(cls.dir, *n))
        cls.runs = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)


class StepsRan:
    def test_every_step_ran(self):
        for step, r in self.runs.items():
            with self.subTest(step=step):
                ok(self, r)


class Transform(StepsRan, Scratch):
    """A base with Latin, two compatibility jamo (ㄱ ㅏ) and two syllables drawn as composites (가 니), fitted to a
    reference whose Hangul is drawn 1.2 times larger against its Latin at wght 400, with the H2 faces as tall as the
    base's: every class wants 1.2 on both axes but H2, which wants 1.2 across and 1.0 up. So the one scale stops at
    1.06, every class at 1.03 over it, and H2 at 3 % wider than tall. The reference has a Latin n, so the Latin keeps
    wght 400 and the Hangul solves a wght of its own: its stem, 96 at cap 700, over the H1 x scale."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        cls.base = T.hangul_vf(p("LumenLedger[wght].ttf"), latin=True, jamo="ㄱㅏ", composite="가니")
        assert T.approve(cls.base, T.write(p("OFL.txt"), T.ofl_text()), p("base.json")).returncode == 0
        T.instance(T.hangul_vf(p("ref.ttf"), latin=True, scale=1.2), p("ref-400.ttf"), 400)
        cls.runs["measure"] = T.run("measure_font.py", p("ref-400.ttf"), "--out", p("m-ref.json"))
        m = load(p("m-ref.json"))
        for e in m["hangul"]["classes"]["H2"]["face_h"]:
            e["value"] = round(e["value"] / 1.2, 1)
        T.write(p("m-far.json"), json.dumps(m, ensure_ascii=False))
        cls.runs["targets"] = T.run("make_targets.py", p("m-far.json"), "--family", T.NEW_FAMILY, "--scripts",
                                    "latin,korean", "--style", "Regular:400", "--style", "Bold:700", "--out",
                                    p("targets.json"))
        cls.runs["fit"] = T.run("fit_font.py", cls.base, p("targets.json"), "--base-json", p("base.json"), "--out-dir",
                                p("build"))
        cls.log = load(p("build", "fit-log.json"))
        cls.subset = TTFont(p("build", "subset", "base.subset.ttf"))

    def fitted(self, i):
        s = self.log["styles"][i]
        return s, TTFont(self.p("build", s["file"]))

    def scales(self, i):
        """Per Hangul glyph: (class, measured x scale, measured y scale, how far rounding can move them), the fitted
        ink box over the base's at the fit's Hangul location, after the em scale."""
        s, font = self.fitted(i)
        inst = instancer.instantiateVariableFont(copy.deepcopy(self.subset), s["hangul"]["location"])
        was, got, k = boxes(inst), boxes(font), s["em_scale"]
        out = {}
        for name, cls in L.hangul_glyphs(inst).items():
            w, h = was[name][2] - was[name][0], was[name][3] - was[name][1]
            out[name] = (cls, (got[name][2] - got[name][0]) / k / w, (got[name][3] - got[name][1]) / k / h,
                         ROUNDING / (k * min(w, h)))
        return out

    def test_the_logged_transform_stays_within_the_limits(self):
        for i in (0, 1):
            xf = self.log["styles"][i]["hangul"]["transform"]
            with self.subTest(style=i):
                self.assertEqual(xf["scale"], 1 + L.HANGUL_SCALE_LIMIT)
                self.assertGreater(xf["scale_wanted"], 1.15)
                for cls, t in xf["classes"].items():
                    for v in (t["sx"] / xf["scale"], t["sy"] / xf["scale"], t["sx"] / t["sy"]):
                        self.assertLessEqual(abs(v - 1), L.HANGUL_CLASS_LIMIT + 1e-6, (cls, t))
                h2 = xf["classes"]["H2"]
                self.assertAlmostEqual(h2["sx"] / h2["sy"], 1 + L.HANGUL_CLASS_LIMIT, places=4)
                self.assertEqual(h2["wanted"], {"sx": 1.2, "sy": 1.0})

    def test_the_final_scale_of_every_hangul_glyph_is_the_logged_one_within_the_limits(self):
        for i in (0, 1):
            xf = self.log["styles"][i]["hangul"]["transform"]
            s = xf["scale"]
            for name, (cls, rx, ry, slack) in self.scales(i).items():
                t = xf["jamo"] if cls == "jamo" else xf["classes"][cls]
                with self.subTest(style=i, glyph=name):
                    self.assertAlmostEqual(rx, t["sx"], delta=slack)
                    self.assertAlmostEqual(ry, t["sy"], delta=slack)
                    self.assertLessEqual(abs(s - 1), L.HANGUL_SCALE_LIMIT + 1e-9)
                    for v in (rx / s, ry / s, rx / ry):
                        self.assertLessEqual(abs(v - 1), L.HANGUL_CLASS_LIMIT + 2 * slack)

    def test_the_compatibility_jamo_take_the_one_scale_alone(self):
        s, font = self.fitted(0)
        scale = s["hangul"]["transform"]["scale"]
        jamo = {n: v for n, v in self.scales(0).items() if v[0] == "jamo"}
        self.assertEqual(sorted(jamo), ["uni3131", "uni314F"])
        for name, (_, rx, ry, slack) in jamo.items():
            with self.subTest(glyph=name):
                self.assertAlmostEqual(rx, scale, delta=slack)
                self.assertAlmostEqual(ry, scale, delta=slack)
                self.assertAlmostEqual(font["hmtx"][name][0], 1000 * scale * s["em_scale"], delta=1)

    def test_composite_syllables_are_decomposed_before_the_transform(self):
        self.assertTrue(all(self.subset["glyf"][n].isComposite() for n in ("uniAC00", "uniB2C8")))
        s, font = self.fitted(0)
        self.assertEqual(s["hangul"]["composites_decomposed"], 2)
        h1 = s["hangul"]["transform"]["classes"]["H1"]
        scales = self.scales(0)
        for name in ("uniAC00", "uniB2C8"):
            _, rx, ry, slack = scales[name]
            with self.subTest(glyph=name):
                self.assertFalse(font["glyf"][name].isComposite())
                self.assertAlmostEqual(rx, h1["sx"], delta=slack)
                self.assertAlmostEqual(ry, h1["sy"], delta=slack)

    def test_the_hangul_wght_is_solved_for_its_stem_over_the_h1_x_scale(self):
        first, second = self.log["styles"]
        self.assertAlmostEqual(first["y_location"]["wght"], 400, delta=3)  # the Latin n stem, 80
        h = first["hangul"]
        stem, sx = h["stem"], h["transform"]["classes"]["H1"]["sx"]
        self.assertEqual(stem["from"], "cap700")
        self.assertAlmostEqual(stem["target"], 96, delta=1)
        self.assertAlmostEqual(stem["base"] * sx / stem["target"], 1, delta=0.01)
        self.assertAlmostEqual(stem["fitted"] / stem["target"], 1, delta=0.015)
        self.assertGreater(h["location"]["wght"], first["y_location"]["wght"] + 30)
        self.assertEqual(second["hangul"]["weight_from"], "n_stem, stepped from the first style")
        self.assertAlmostEqual(second["hangul"]["location"]["wght"], h["location"]["wght"] + 300, delta=0.01)
        self.assertEqual(second["hangul"]["transform"], h["transform"])

    def test_centre_heights_and_advances_land_on_their_targets(self):
        h = self.log["styles"][0]["hangul"]
        for cls, row in h["classes"].items():
            with self.subTest(cls=cls):
                self.assertAlmostEqual(row["cy"]["fitted"], row["cy"]["target"], delta=2)
                self.assertAlmostEqual(row["cx"]["fitted"], row["cx"]["target"], delta=2)
        self.assertAlmostEqual(h["adv"]["fitted"], h["adv"]["target"], delta=1)

    def test_the_check_fails_a_hangul_glyph_the_logged_transform_does_not_explain(self):
        s, font = self.fitted(0)

        def rows(f, record=s):
            G = check_font.Gates()
            check_font.gate_hangul(G, f, self.subset, record)
            return {name: (state, detail) for _, name, state, detail in G.rows}
        got = rows(font)
        self.assertEqual(got["Hangul transform within the limits"][0], "PASS", got)
        self.assertEqual(got["every Hangul glyph where the logged transform puts it"][0], "PASS", got)
        moved = copy.deepcopy(font)
        g = moved["glyf"]["uniAC01"]
        g.coordinates[0] = (g.coordinates[0][0] - 30, g.coordinates[0][1])
        recomposed = copy.deepcopy(font)  # 니 drawn again from its components, as the base draws it
        recomposed["glyf"]["uniB2C8"] = T._composite([("uniB2C8.a", 0), ("uniB2C8.b", T.COMPONENT_SHIFT)])
        for case, f, glyph in (("a point moved", moved, "uniAC01"), ("a composite", recomposed, "uniB2C8")):
            with self.subTest(case=case):
                state, detail = rows(f)["every Hangul glyph where the logged transform puts it"]
                self.assertEqual(state, "FAIL")
                self.assertIn(glyph, detail)
        record = copy.deepcopy(s)
        record["hangul"]["transform"]["classes"]["H2"]["sx"] = 1.2
        self.assertEqual(rows(font, record)["Hangul transform within the limits"][0], "FAIL")

    def test_weight_harmony_runs_with_a_reference_that_measured_latin(self):
        t = load(self.p("targets.json"))
        self.assertAlmostEqual(L.tagged_value(t["hangul"]["stem_n"], "ratio"), 1.2, delta=0.01)
        _, font = self.fitted(0)
        G = check_font.Gates()
        check_font.gate_harmony(G, L.Face(font), t)
        got = {name: (state, detail) for _, name, state, detail in G.rows}
        self.assertEqual(got["Hangul stem / Latin n stem"][0], "PASS", got)
        self.assertEqual(got["Hangul face centre heights"][0], "PASS", got)
        no_latin = copy.deepcopy(t)  # the same Hangul targets, centre heights included, from a reference without Latin
        del no_latin["targets"]["n_stem"]
        G = check_font.Gates()
        check_font.gate_harmony(G, L.Face(font), no_latin)
        self.assertEqual({name: state for _, name, state, _ in G.rows},
                         {"Hangul stem / Latin n stem": "NOT RUN", "Hangul face centre heights": "NOT RUN"})


class Coverage(unittest.TestCase):
    def test_ks_x_1001_is_the_2350_syllables_of_euc_kr(self):
        self.assertEqual(len(L.KS_X_1001), 2350)
        self.assertEqual(len(set(L.KS_X_1001)), 2350)
        self.assertEqual((L.KS_X_1001[0], L.KS_X_1001[-1]), ("가", "힝"))
        self.assertTrue(set(L.KS_X_1001) <= set(L.MODERN_SYLLABLES))
        self.assertEqual(len(L.MODERN_SYLLABLES), 11172)

    def test_a_missing_ks_x_1001_syllable_fails_and_the_modern_syllables_are_counted(self):
        d = tempfile.mkdtemp(prefix="mf-hangul-cover-")
        self.addCleanup(shutil.rmtree, d, True)
        have = L.KS_X_1001[:-1]  # all but 힝
        f = TTFont(T.hangul_vf(os.path.join(d, "a.ttf"), syllables=have))
        G = check_font.Gates()
        check_font.gate_coverage(G, f, ["korean"])
        got = {name: (state, detail) for _, name, state, detail in G.rows}
        self.assertEqual(got["korean"][0], "FAIL")
        self.assertIn("KS X 1001: 2349 of 2350, missing 힝", got["korean"][1])
        n = len(set(have) | {c for c in L.HANGUL_TEXT if L.hangul_class(c)})
        self.assertEqual(got["korean, modern syllables"], ("INFO", f"{n} of 11172"))
        self.assertEqual(got["korean, compatibility jamo"], ("INFO", "0 of 94"))


class Chain(StepsRan, Scratch):
    """The whole chain on a base with every KS X 1001 syllable, from a screenshot of Hangul alone: fit, space,
    package and check, then the font book's HTML. The check passes, gates KS X 1001, counts the modern syllables, and
    reports weight harmony as not run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        cls.base = T.hangul_vf(p("LumenLedger[wght].ttf"), latin=True, syllables=L.KS_X_1001, jamo="ㄱㅏ")
        assert T.approve(cls.base, T.write(p("OFL.txt"), T.ofl_text()), p("base.json")).returncode == 0
        T.instance(T.hangul_vf(p("ref.ttf"), latin=False), p("ref-500.ttf"), 500)
        measure_image.render_sheet(L.Face(p("ref-500.ttf"), subset_text=L.HANGUL_TEXT), L.SAMPLE_LINES_KO, 200,
                                   p("shot.png"))
        run = cls.runs
        run["measure"] = T.run("measure_image.py", p("shot.png"), "--text", "|".join(L.SAMPLE_LINES_KO), "--out",
                               p("m.json"))
        run["targets"] = T.run("make_targets.py", p("m.json"), "--family", T.NEW_FAMILY, "--scripts", "korean",
                               "--out", p("targets.json"))
        chain = ("--base-json", p("base.json"))
        run["fit"] = T.run("fit_font.py", cls.base, p("targets.json"), *chain, "--out-dir", p("build"))
        fit_log = ("--fit-log", p("build", "fit-log.json"))
        run["space"] = T.run("space_font.py", p("build", "TesseraSans-Regular.fit.ttf"), p("targets.json"), "--out",
                             p("build", "TesseraSans-Regular.ttf"), *chain, *fit_log, "--track", "5")
        space_log = ("--space-log", p("build", "TesseraSans-Regular.ttf.space-log.json"))
        run["package"] = T.run("package.py", p("build", "TesseraSans-Regular.ttf"), "--targets", p("targets.json"),
                               *chain, *fit_log, *space_log, "--holder", "Synthetic Holder", "--out-dir", p("dist"))
        run["check"] = T.run("check_font.py", p("dist", "ttf", "TesseraSans-Regular.ttf"), "--targets",
                             p("targets.json"), *chain, *fit_log, *space_log, "--package-log",
                             p("dist", "package-log.json"), "--package", p("dist"), "--reference-image", p("shot.png"),
                             "--reference-text", "|".join(L.SAMPLE_LINES_KO), "--out-dir", p("checks"))
        run["book"] = T.run("font_book.py", p("dist", "ttf", "TesseraSans-Regular.ttf"), "--webfonts",
                            p("dist", "webfonts"), "--targets", p("targets.json"), *fit_log, *space_log,
                            "--check-report", p("checks", "check-report.json"), "--out-dir", p("book"))

    def gates(self):
        return {g["gate"]: (g["state"], g["detail"]) for g in load(self.p("checks", "check-report.json"))["gates"]}

    def test_the_check_gates_ks_x_1001_and_counts_the_modern_syllables(self):
        got = self.gates()
        self.assertEqual(got["korean"], ("PASS", "KS X 1001: 2350 of 2350"))
        n = len(set(L.KS_X_1001) | {c for c in L.HANGUL_TEXT if L.hangul_class(c)})
        self.assertEqual(got["korean, modern syllables"], ("INFO", f"{n} of 11172"))
        self.assertEqual(got["korean, compatibility jamo"], ("INFO", "2 of 94"))

    def test_without_a_latin_reference_weight_harmony_is_not_run(self):
        got = self.gates()
        self.assertEqual(got["Hangul stem / Latin n stem"][0], "NOT RUN")
        self.assertEqual(got["Hangul face centre heights"][0], "NOT RUN")
        summary = next(line for line in self.runs["check"].stdout.splitlines() if " failed, " in line)
        self.assertIn("Hangul stem / Latin n stem", summary)

    def test_every_hangul_glyph_is_where_the_logged_transform_and_the_track_put_it(self):
        got = self.gates()
        self.assertEqual(got["Hangul transform within the limits"][0], "PASS")
        self.assertEqual(got["every Hangul glyph where the logged transform puts it"][0], "PASS", got)
        self.assertEqual(got["every glyph traceable to its base glyph"][0], "PASS", got)
        self.assertIn("vertical strokes across the classes", got)

    def test_a_screenshot_of_hangul_alone_is_stacked_over_the_font_at_the_same_h1_face_height(self):
        from PIL import Image
        shot, sheet = Image.open(self.p("shot.png")), Image.open(self.p("checks", "stacked-Regular.png"))
        # our lines, set at the screenshot's H1 face height in the font the screenshot shows, are about as long
        self.assertAlmostEqual(sheet.width / shot.width, 1, delta=0.05)
        self.assertGreater(sheet.height, shot.height * 1.8)

    def test_the_package_log_records_each_webfont(self):
        web = load(self.p("dist", "package-log.json"))["webfonts"]
        self.assertEqual([w["file"] for w in web], ["webfonts/TesseraSans-Regular.woff2"])
        self.assertEqual(web[0]["bytes"], os.path.getsize(self.p("dist", "webfonts", "TesseraSans-Regular.woff2")))
        self.assertGreaterEqual(web[0]["seconds"], 0)

    def test_the_font_book_shows_a_fixed_hangul_specimen_and_counts_the_rest(self):
        pages = load(self.p("book", "pages.json"))
        slugs = [s for _, s in pages["pages"]]
        self.assertIn("hangul", slugs)
        self.assertIn("hangul-text", slugs)
        n = len(set(L.KS_X_1001) | {c for c in L.HANGUL_TEXT if L.hangul_class(c)})
        self.assertEqual(pages["coverage"]["korean"], {"KS X 1001": [2350, 2350], "modern syllables": [n, 11172],
                                                        "compatibility jamo": [2, 94]})
        with open(self.p("book", "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotIn(L.KS_X_1001[1000], html)  # the character set lists no syllable one by one


class LatinOpticalSize(StepsRan, Scratch):
    """The Latin n stem path on the base with an optical-size axis (testfonts.hangul_vf(opsz=True), whose Latin stems
    thicken with the size too): a contrast of 0.45, which opsz 90 at wght 100 comes closest to, and an n stem of 50,
    which the wght axis reaches only up to opsz 30; then a stem of 30, thinner than the base draws anywhere."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p = cls.p
        cls.base = T.hangul_vf(p("LumenLedger[opsz,wght].ttf"), latin=True, opsz=True)
        assert T.approve(cls.base, T.write(p("OFL.txt"), T.ofl_text()), p("base.json")).returncode == 0
        for name, stem in (("reach", 50.0), ("beyond", 30.0)):
            T.write(p(f"m-{name}.json"), json.dumps({"source": "image", "cap_em": None, "confidence": {},
                                                    "contrast": 0.45, "n_stem": stem}))
            cls.runs[f"targets {name}"] = T.run("make_targets.py", p(f"m-{name}.json"), "--family", T.NEW_FAMILY,
                                                "--scripts", "latin", "--style", "Regular:400", "--style", "Bold:700",
                                                "--out", p(f"targets-{name}.json"))
            cls.runs[f"fit {name}"] = T.run("fit_font.py", cls.base, p(f"targets-{name}.json"), "--base-json",
                                            p("base.json"), "--out-dir", p(f"build-{name}"))

    def styles(self, name):
        return load(self.p(f"build-{name}", "fit-log.json"))["styles"]

    def test_the_scan_keeps_an_optical_size_where_the_wght_reaches_the_n_stem(self):
        first = self.styles("reach")[0]
        self.assertEqual(first["y_location"]["opsz"], 30)  # of the sizes that reach 50, the nearest to the contrast
        self.assertNotIn("weight_missed_pct", first)

    def test_a_later_weight_takes_the_first_ones_location_with_the_wght_stepped(self):
        first, second = self.styles("reach")
        self.assertEqual(second["y_location"]["opsz"], first["y_location"]["opsz"])
        self.assertAlmostEqual(second["y_location"]["wght"], first["y_location"]["wght"] + 300, delta=0.01)

    def test_when_no_optical_size_reaches_the_n_stem_the_nearest_is_kept_and_logged(self):
        first = self.styles("beyond")[0]
        self.assertEqual(first["y_location"], {"opsz": 10, "wght": 100})  # stem 40, the thinnest the base draws
        self.assertAlmostEqual(first["weight_missed_pct"], (40 / 30 - 1) * 100, delta=0.2)
        self.assertTrue(any("reaches the n stem 30.0 at no location" in line for line in first["log"]), first["log"])


if __name__ == "__main__":
    unittest.main()
