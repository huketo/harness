# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow", "skia-pathops"]
# ///
"""The provenance chain, end to end on a synthetic base: base.json, fit, space, package and check, and every way
of stepping around it."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from fontTools import subset
from fontTools.ttLib import TTFont

import testfonts as T

STYLE = "TesseraSans-Regular"


def sha(path):
    return hashlib.sha256(raw(path)).hexdigest()


def raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def ok(test, r):
    test.assertEqual(r.returncode, 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
    return r


def refused(test, r, *words):
    test.assertNotEqual(r.returncode, 0, f"accepted:\n{r.stdout}")
    for w in ("refused",) + words:
        test.assertIn(w, r.stderr)
    return r


class Pipeline(unittest.TestCase):
    """One approved synthetic base taken through every step. Each refusal test reuses these files read-only."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="mf-chain-")
        cls.p = staticmethod(lambda *n: os.path.join(cls.dir, *n))
        p = cls.p
        cls.base = T.glyf_vf(p("LumenLedger[wght].ttf"))
        cls.ofl = T.write(p("OFL.txt"), T.ofl_text())
        cls.steps = {}
        cls.steps["measure"] = T.run("measure_font.py", cls.base, "--stem", "100", "--out", p("m.json"))
        m = load(p("m.json"))
        m["widths"] = {k: round(v * 1.02, 1) for k, v in m["widths"].items()}  # a target the base must move to
        T.write(p("m2.json"), json.dumps(m))
        cls.steps["targets"] = T.run("make_targets.py", p("m2.json"), "--family", T.NEW_FAMILY, "--use", "text",
                                     "--style", "Regular:400", "--out", p("targets.json"))
        cls.targets = p("targets.json")
        cls.steps["approve"] = T.run("record_base.py", "--font", cls.base, "--licence", cls.ofl, "--source", "local",
                                     "--question", T.SYNTHETIC_QUESTION, "--answer", T.SYNTHETIC_ANSWER,
                                     "--out", p("base.json"))
        cls.base_json = p("base.json")
        cls.steps["fit"] = T.run("fit_font.py", cls.base, cls.targets, "--base-json", cls.base_json,
                                 "--out-dir", p("build"))
        cls.fit = p("build", STYLE + ".fit.ttf")
        cls.fit_log = p("build", "fit-log.json")
        cls.spaced = p("build", STYLE + ".ttf")
        cls.steps["space"] = T.run("space_font.py", cls.fit, cls.targets, "--out", cls.spaced, "--track", "4",
                                   "--base-json", cls.base_json, "--fit-log", cls.fit_log)
        cls.space_log = cls.spaced + ".space-log.json"
        cls.steps["package"] = T.run("package.py", cls.spaced, "--targets", cls.targets, "--base-json", cls.base_json,
                                     "--fit-log", cls.fit_log, "--space-log", cls.space_log,
                                     "--holder", "Fixture Holder", "--out-dir", p("dist"))
        cls.package_log = p("package-log.json")
        cls.ttf = p("dist", "ttf", STYLE + ".ttf")
        cls.steps["check"] = T.run("check_font.py", cls.ttf, "--targets", cls.targets, "--base-json", cls.base_json,
                                   "--fit-log", cls.fit_log, "--space-log", cls.space_log,
                                   "--package-log", cls.package_log, "--package", p("dist"), "--out-dir", p("checks"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def scratch(self):
        d = tempfile.mkdtemp(prefix="mf-case-", dir=self.dir)
        return lambda *n: os.path.join(d, *n)

    # ---------------------------------------------------------------- the chain holds
    def test_every_step_ran(self):
        for step in ("measure", "targets", "approve", "fit", "space", "package"):
            with self.subTest(step=step):
                ok(self, self.steps[step])

    def test_base_json_records_the_approval(self):
        rec = load(self.base_json)
        self.assertEqual(rec["schema"], "make-font/base@1")
        self.assertEqual(rec["font"], {"file": os.path.abspath(self.base), "sha256": sha(self.base)})
        self.assertEqual(rec["source"], {"kind": "local", "url": None, "manifest_entry": None})
        self.assertEqual(rec["license"]["id"], "OFL-1.1")
        self.assertEqual(rec["license"]["sha256"], sha(self.ofl))
        self.assertEqual(rec["license"]["name_id_13"], T.OFL_NOTICE)
        self.assertEqual(rec["license"]["reserved_font_names"], [])
        self.assertEqual(rec["approval"]["question"], T.SYNTHETIC_QUESTION)
        self.assertEqual(rec["approval"]["answer"], T.SYNTHETIC_ANSWER)
        self.assertRegex(rec["approval"]["recorded_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|\+00:00)$")

    def test_fit_log_records_its_own_subset(self):
        log = load(self.fit_log)
        sub = log["subset"]
        self.assertEqual(sub["source_sha256"], sha(self.base))
        self.assertEqual(sub["sha256"], sha(sub["file"]))
        self.assertTrue(sub["args"] and all(a.startswith("--") for a in sub["args"]))
        chain = log["chain"]
        self.assertEqual(chain["base_json_sha256"], sha(self.base_json))
        self.assertEqual([e["sha256"] for e in chain["inputs"]], [sha(self.base)])
        self.assertEqual([e["sha256"] for e in chain["outputs"]], [sha(self.fit)])

    def test_space_and_package_logs_link_to_the_previous_step(self):
        space = load(self.space_log)["chain"]
        self.assertEqual([e["sha256"] for e in space["inputs"]], [sha(self.fit)])
        self.assertEqual([e["sha256"] for e in space["outputs"]], [sha(self.spaced)])
        pkg = load(self.package_log)["chain"]
        self.assertEqual([e["sha256"] for e in pkg["inputs"]], [sha(self.spaced)])
        woff2 = self.p("dist", "webfonts", STYLE + ".woff2")
        self.assertEqual(sorted(e["sha256"] for e in pkg["outputs"]), sorted([sha(self.ttf), sha(woff2)]))

    def test_check_verifies_the_chain(self):
        r = self.steps["check"]
        rows = load(self.p("checks", "check-report.json"))
        chain = [x for x in rows if x["group"] == "chain"]
        self.assertTrue(chain, r.stdout + r.stderr)
        self.assertEqual({x["state"] for x in chain}, {"PASS"}, chain)
        prov = {x["gate"]: x["state"] for x in rows if x["group"] == "provenance"}
        self.assertEqual(prov["glyph order equals the subset's"], "PASS")
        self.assertEqual(prov["character map equals the subset's"], "PASS")

    def test_package_names_and_readme(self):
        f = TTFont(self.ttf)
        names = {r.nameID: r.toUnicode() for r in f["name"].names}
        self.assertNotIn("Fixture Designer", names[9])  # the base's designer field is not carried as ours
        self.assertIn("Fixture Holder", names[9])
        readme = text(self.p("dist", "README.md"))
        self.assertIn(f'font-family: "{T.NEW_FAMILY}", sans-serif;', readme)
        fontlog = text(self.p("dist", "FONTLOG.txt"))
        self.assertIn(T.SYNTHETIC_ANSWER, fontlog)
        self.assertIn(sha(self.base), fontlog)
        self.assertNotIn(self.dir, fontlog + readme)  # no builder paths in the package

    def test_a_cff_reference_is_compared_never_and_reported_not_run(self):
        q = self.scratch()
        ref = T.cff_static(q("reference.otf"), family="Arbor Text")
        T.run("check_font.py", self.ttf, "--targets", self.targets, "--base-json", self.base_json,
              "--fit-log", self.fit_log, "--space-log", self.space_log, "--package-log", self.package_log,
              "--reference", ref, "--out-dir", q("checks"))
        rows = load(q("checks", "check-report.json"))
        got = [(x["state"], x["detail"]) for x in rows if x["gate"].startswith("outline comparison")]
        self.assertEqual([g[0] for g in got], ["NOT RUN"], got)
        self.assertIn("CFF", got[0][1])
        self.assertTrue(os.path.exists(q("checks", "overlay-Regular-text.png")))

    # ---------------------------------------------------------------- base.json is written once
    def test_base_json_is_never_rewritten(self):
        before = raw(self.base_json)
        r = T.run("record_base.py", "--font", self.base, "--licence", self.ofl, "--source", "local",
                  "--question", T.SYNTHETIC_QUESTION, "--answer", "synthetic e2e approval: a different answer",
                  "--out", self.base_json)
        refused(self, r, "base.json")
        self.assertEqual(raw(self.base_json), before)
        same = T.run("record_base.py", "--font", self.base, "--licence", self.ofl, "--source", "local",
                     "--question", T.SYNTHETIC_QUESTION, "--answer", T.SYNTHETIC_ANSWER, "--out", self.base_json)
        ok(self, same)
        self.assertEqual(raw(self.base_json), before)

    def test_static_and_cff_bases_are_refused(self):
        q = self.scratch()
        for maker, name in ((T.glyf_static, "static.ttf"), (T.cff_static, "cff.otf")):
            with self.subTest(base=name):
                r = T.run("record_base.py", "--font", maker(q(name)), "--licence", self.ofl, "--source", "local",
                          "--question", T.SYNTHETIC_QUESTION, "--answer", T.SYNTHETIC_ANSWER, "--out", q(name + ".json"))
                refused(self, r, "variable")
                self.assertFalse(os.path.exists(q(name + ".json")))

    def test_fit_refuses_a_static_base_even_with_a_matching_base_json(self):
        q = self.scratch()
        static = T.glyf_static(q("static.ttf"))
        rec = load(self.base_json)
        rec["font"] = {"file": static, "sha256": sha(static)}
        T.write(q("base.json"), json.dumps(rec))
        r = T.run("fit_font.py", static, self.targets, "--base-json", q("base.json"), "--out-dir", q("build"))
        refused(self, r, "variable")

    # ---------------------------------------------------------------- stepping around the chain
    def test_fit_refuses_a_subset_made_elsewhere(self):
        q = self.scratch()
        f = TTFont(self.base)
        opts = subset.Options()
        opts.glyph_names = True
        s = subset.Subsetter(opts)
        s.populate(text="noxHO ")
        s.subset(f)
        f.save(q("outside.subset.ttf"))
        r = T.run("fit_font.py", q("outside.subset.ttf"), self.targets, "--base-json", self.base_json,
                  "--out-dir", q("build"))
        refused(self, r, "approved base")
        self.assertFalse(os.path.exists(q("build")))

    def test_fit_refuses_a_base_changed_after_approval(self):
        q = self.scratch()
        moved = shutil.copy(self.base, q("base.ttf"))
        rec = load(self.base_json)
        rec["font"]["file"] = moved
        T.write(q("base.json"), json.dumps(rec))
        with open(moved, "ab") as fh:
            fh.write(b"\0")
        r = T.run("fit_font.py", moved, self.targets, "--base-json", q("base.json"), "--out-dir", q("build"))
        refused(self, r, "sha256")

    def test_space_refuses_a_font_the_fit_log_did_not_write(self):
        q = self.scratch()
        r = T.run("space_font.py", self.base, self.targets, "--out", q(STYLE + ".ttf"),
                  "--base-json", self.base_json, "--fit-log", self.fit_log)
        refused(self, r, "fit-log")
        self.assertFalse(os.path.exists(q(STYLE + ".ttf")))

    def test_space_refuses_without_a_fit_log(self):
        q = self.scratch()
        r = T.run("space_font.py", self.fit, self.targets, "--out", q(STYLE + ".ttf"), "--base-json", self.base_json)
        refused(self, r, "--fit-log")

    def test_package_refuses_a_font_given_without_base_json(self):
        q = self.scratch()
        r = T.run("package.py", self.spaced, "--targets", self.targets, "--holder", "Fixture Holder",
                  "--out-dir", q("dist"))
        refused(self, r, "--base-json")
        self.assertFalse(os.path.exists(q("dist")))

    def test_package_refuses_a_font_outside_the_chain(self):
        q = self.scratch()
        direct = shutil.copy(self.fit, q(STYLE + ".ttf"))  # a real fit, but space_font.py never wrote it
        self.assertNotEqual(sha(direct), sha(self.spaced))
        r = T.run("package.py", direct, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                  "--out-dir", q("dist"), "--log", q("package-log.json"))
        refused(self, r, "space")
        self.assertFalse(os.path.exists(q("dist")))
        self.assertEqual([n for n in os.listdir(q()) if n.startswith(".package")], [])

    def test_package_refuses_a_font_whose_sha256_differs_from_the_space_log(self):
        q = self.scratch()
        changed = shutil.copy(self.spaced, q(STYLE + ".ttf"))
        f = TTFont(changed)
        f["hmtx"].metrics["n"] = (f["hmtx"].metrics["n"][0] + 1, f["hmtx"].metrics["n"][1])
        f.save(changed)
        r = T.run("package.py", changed, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                  "--out-dir", q("dist"), "--log", q("package-log.json"))
        refused(self, r, "sha256")
        self.assertFalse(os.path.exists(q("dist")))

    def test_package_keeps_an_existing_folder_unless_told_to_replace_it(self):
        q = self.scratch()
        shutil.copytree(self.p("dist"), q("dist"))
        args = ["package.py", self.spaced, "--targets", self.targets, "--base-json", self.base_json,
                "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                "--out-dir", q("dist"), "--log", q("package-log.json")]
        refused(self, T.run(*args), "--replace")
        self.assertFalse(os.path.exists(q("package-log.json")))
        ok(self, T.run(*args, "--replace"))
        outputs = load(q("package-log.json"))["chain"]["outputs"]
        self.assertEqual({e["sha256"] for e in outputs}, {sha(e["file"]) for e in outputs})
        self.assertTrue(all(e["file"].startswith(q("dist")) for e in outputs))

    def test_check_refuses_a_font_the_package_log_did_not_write(self):
        q = self.scratch()
        r = T.run("check_font.py", self.spaced, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--package-log", self.package_log,
                  "--out-dir", q("checks"))
        refused(self, r, "package")


if __name__ == "__main__":
    unittest.main()
