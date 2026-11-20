# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow", "skia-pathops"]
# ///
"""The provenance chain, end to end on a synthetic base: base.json, fit, space, package and check, and every way
of stepping around it."""
import builtins
import contextlib
import hashlib
import html
import importlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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


def in_process(script, *args):
    """Run one skill script's main() in this process, so a test can watch the files it opens. Returns (exit
    status, stdout, stderr); a refusal's status is its message."""
    mod = importlib.import_module(script[:-3])
    out, err, code = io.StringIO(), io.StringIO(), 0
    with mock.patch.object(sys, "argv", [script, *map(str, args)]), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        try:
            mod.main()
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class _SwapOnClose:
    def __init__(self, fh, after):
        self._fh, self._after = fh, after

    def __getattr__(self, name):
        return getattr(self._fh, name)

    def __iter__(self):
        return iter(self._fh)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if not self._fh.closed:
            self._fh.close()
            self._after()


@contextlib.contextmanager
def watched(*paths, swap=None):
    """Count how often each of these files is opened for reading. With swap={path: bytes}, that file holds those
    bytes from the moment its first reader closes it, as a process racing the step could arrange: a step that
    reads it again, by any means, reads the other bytes."""
    real = builtins.open
    keys = {os.path.realpath(p): p for p in paths}
    count = dict.fromkeys(paths, 0)

    def put(p):
        with real(p, "wb") as fh:
            fh.write(swap[p])

    def fake(file, mode="r", *a, **k):
        p = keys.get(os.path.realpath(file)) if isinstance(file, (str, os.PathLike)) else None
        fh = real(file, mode, *a, **k)
        if p is None or any(c in mode for c in "wax+"):
            return fh
        count[p] += 1
        if swap and p in swap and count[p] == 1:
            return _SwapOnClose(fh, lambda: put(p))
        return fh
    with mock.patch("builtins.open", fake):
        yield count


def outlines_moved(path):
    """The font's bytes with one outline moved: the same glyph order and character map, other ink."""
    f = TTFont(path)
    g = f["glyf"]["n"]
    g.coordinates[0] = (g.coordinates[0][0] + 7, g.coordinates[0][1])
    buf = io.BytesIO()
    f.save(buf)
    return buf.getvalue()


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
        cls.steps["approve"] = T.approve(cls.base, cls.ofl, p("base.json"))
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
        cls.package_log = p("dist", "package-log.json")
        cls.ttf = p("dist", "ttf", STYLE + ".ttf")
        cls.steps["check"] = T.run("check_font.py", cls.ttf, "--targets", cls.targets, "--base-json", cls.base_json,
                                   "--fit-log", cls.fit_log, "--space-log", cls.space_log,
                                   "--package-log", cls.package_log, "--package", p("dist"), "--out-dir", p("checks"))
        cls.steps["book"] = T.run("font_book.py", cls.ttf, "--webfonts", p("dist", "webfonts"), "--targets", cls.targets,
                                  "--fit-log", cls.fit_log, "--space-log", cls.space_log,
                                  "--check-report", p("checks", "check-report.json"), "--out-dir", p("book"))

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
        self.assertEqual(rec["approval"]["question"], self.steps["approve"].question)
        self.assertIn(sha(self.base), rec["approval"]["question"])
        self.assertIn(sha(self.ofl), rec["approval"]["question"])
        self.assertEqual(rec["approval"]["answer"], T.SYNTHETIC_ANSWER)
        self.assertEqual(rec["approval"]["decision"], "approved")
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
        rows = load(self.p("checks", "check-report.json"))["gates"]
        chain = [x for x in rows if x["group"] == "chain"]
        self.assertTrue(chain, r.stdout + r.stderr)
        self.assertEqual({x["state"] for x in chain}, {"PASS"}, chain)
        prov = {x["gate"]: x["state"] for x in rows if x["group"] == "provenance"}
        self.assertEqual(prov["glyph order equals the subset's"], "PASS")
        self.assertEqual(prov["character map equals the subset's"], "PASS")

    def test_the_check_report_states_the_approved_base_and_the_approval(self):
        rep = load(self.p("checks", "check-report.json"))
        self.assertIsInstance(rep, dict, "check-report.json is a bare list of gates, with no provenance record")
        rec = load(self.base_json)
        self.assertEqual(rep["base"]["sha256"], sha(self.base))
        self.assertEqual(rep["base"]["license"]["sha256"], sha(self.ofl))
        self.assertEqual(rep["approval"], rec["approval"])

    def test_the_font_book_prints_the_approved_base_and_the_approval(self):
        ok(self, self.steps["book"])
        page = text(self.p("book", "index.html"))
        appr = load(self.base_json)["approval"]
        for want in (sha(self.base), sha(self.ofl), appr["question"], appr["answer"]):
            self.assertIn(html.escape(want), page)

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
        rows = load(q("checks", "check-report.json"))["gates"]
        got = [(x["state"], x["detail"]) for x in rows if x["gate"].startswith("outline comparison")]
        self.assertEqual([g[0] for g in got], ["NOT RUN"], got)
        self.assertIn("CFF", got[0][1])
        self.assertTrue(os.path.exists(q("checks", "overlay-Regular-text.png")))

    # ---------------------------------------------------------------- base.json is written once
    def test_base_json_is_never_rewritten(self):
        before = raw(self.base_json)
        r = T.approve(self.base, self.ofl, self.base_json, answer="synthetic e2e approval: a different answer")
        refused(self, r, "base.json")
        self.assertEqual(raw(self.base_json), before)
        ok(self, T.approve(self.base, self.ofl, self.base_json))
        self.assertEqual(raw(self.base_json), before)

    def test_static_and_cff_bases_are_refused(self):
        q = self.scratch()
        for maker, name in ((T.glyf_static, "static.ttf"), (T.cff_static, "cff.otf")):
            with self.subTest(base=name):
                r = T.approve(maker(q(name)), self.ofl, q(name + ".json"))
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
                  "--out-dir", q("dist"))
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
                  "--out-dir", q("dist"))
        refused(self, r, "sha256")
        self.assertFalse(os.path.exists(q("dist")))

    def test_package_keeps_an_existing_folder_unless_told_to_replace_it(self):
        q = self.scratch()
        shutil.copytree(self.p("dist"), q("dist"))
        args = ["package.py", self.spaced, "--targets", self.targets, "--base-json", self.base_json,
                "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                "--out-dir", q("dist")]
        before = raw(q("dist", "package-log.json"))
        refused(self, T.run(*args), "--replace")
        self.assertEqual(raw(q("dist", "package-log.json")), before)
        ok(self, T.run(*args, "--replace"))
        outputs = load(q("dist", "package-log.json"))["chain"]["outputs"]
        self.assertEqual({e["sha256"] for e in outputs}, {sha(q("dist", e["file"])) for e in outputs})
        self.assertEqual(sorted(n for n in os.listdir(q()) if n.startswith(".package")), [])

    # ---------------------------------------------------------------- the subset is made again from the base
    def forged_fit_log(self, q):
        """A subset made from another font with the fit log's arguments, and the fit log edited to name it: what a
        caller could pass so that package.py and check_font.py compare against the wrong glyphs."""
        other = T.glyf_vf(q("ArborText[wght].ttf"), family="Arbor Text", copyright_line="Copyright 2026 Arbor Type")
        log = load(self.fit_log)
        sub = log["subset"]
        opts = subset.Options()
        rest = opts.parse_opts(list(sub["args"]), ignore_unknown=["unicodes"])
        s = subset.Subsetter(opts)
        s.populate(unicodes=[u for r in rest for u in subset.parse_unicodes(r.split("=", 1)[1])])
        f = TTFont(other, recalcTimestamp=False)
        s.subset(f)
        f.save(q("other.subset.ttf"))
        self.assertEqual(TTFont(q("other.subset.ttf")).getGlyphOrder(), TTFont(sub["file"]).getGlyphOrder())
        sub.update(file=q("other.subset.ttf"), sha256=sha(q("other.subset.ttf")))
        return T.write(q("fit-log.json"), json.dumps(log))

    def test_package_makes_the_subset_again_and_refuses_one_from_another_font(self):
        q = self.scratch()
        r = T.run("package.py", self.spaced, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.forged_fit_log(q), "--space-log", self.space_log, "--holder", "Fixture Holder",
                  "--out-dir", q("dist"))
        refused(self, r, "subset")
        self.assertFalse(os.path.exists(q("dist")))

    def test_check_makes_the_subset_again_and_refuses_one_from_another_font(self):
        q = self.scratch()
        r = T.run("check_font.py", self.ttf, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.forged_fit_log(q), "--space-log", self.space_log,
                  "--package-log", self.package_log, "--out-dir", q("checks"))
        refused(self, r, "subset")

    # ---------------------------------------------------------------- package and check check one chain
    def test_package_refuses_targets_other_than_the_ones_fit_and_space_read(self):
        q = self.scratch()
        targets = load(self.targets)
        targets["use"] = "display"
        T.write(q("targets.json"), json.dumps(targets))
        r = T.run("package.py", self.spaced, "--targets", q("targets.json"), "--base-json", self.base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                  "--out-dir", q("dist"))
        refused(self, r, "targets")
        self.assertFalse(os.path.exists(q("dist")))

    def test_check_refuses_logs_other_than_the_ones_package_recorded(self):
        for flag in ("--fit-log", "--space-log"):
            with self.subTest(flag=flag):
                q = self.scratch()
                logs = {"--fit-log": self.fit_log, "--space-log": self.space_log}
                logs[flag] = T.write(q(os.path.basename(logs[flag])), json.dumps(load(logs[flag]), indent=2))
                self.assertNotEqual(sha(logs[flag]), sha(self.fit_log if flag == "--fit-log" else self.space_log))
                r = T.run("check_font.py", self.ttf, "--targets", self.targets, "--base-json", self.base_json,
                          "--fit-log", logs["--fit-log"], "--space-log", logs["--space-log"],
                          "--package-log", self.package_log, "--out-dir", q("checks"))
                refused(self, r, "package")

    # ---------------------------------------------------------------- publishing the package
    def test_package_publishes_its_log_inside_the_package(self):
        log = self.p("dist", "package-log.json")
        self.assertTrue(os.path.exists(log))
        self.assertFalse(os.path.exists(self.p("package-log.json")))
        self.assertIn("package-log.json", text(self.p("dist", "README.md")))
        self.assertNotIn(self.dir, text(log))  # hashes and file names, no builder paths

    def test_package_refuses_an_out_dir_that_holds_its_inputs(self):
        q = self.scratch()
        os.makedirs(q("build"))
        files = [shutil.copy(x, q("build")) for x in (self.spaced, self.fit_log, self.space_log)]
        before = {f: raw(f) for f in files}
        r = T.run("package.py", files[0], "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", files[1], "--space-log", files[2], "--holder", "Fixture Holder",
                  "--out-dir", q("build"), "--replace")
        self.assertTrue(all(os.path.exists(f) for f in files), "package.py removed its own inputs")
        refused(self, r, "--out-dir")
        self.assertEqual({f: raw(f) for f in files}, before)

    def test_package_refuses_an_out_dir_that_is_an_input_file(self):
        q = self.scratch()
        base_json = shutil.copy(self.base_json, q("base.json"))
        r = T.run("package.py", self.spaced, "--targets", self.targets, "--base-json", base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                  "--out-dir", base_json, "--replace")
        refused(self, r, "--out-dir")
        self.assertEqual(raw(base_json), raw(self.base_json))

    def test_package_refuses_two_fonts_that_would_package_as_one_file(self):
        q = self.scratch()
        os.makedirs(q("again"))
        again = q("again", STYLE + ".ttf")
        ok(self, T.run("space_font.py", self.fit, self.targets, "--out", again, "--track", "8",
                       "--base-json", self.base_json, "--fit-log", self.fit_log))
        self.assertNotEqual(sha(again), sha(self.spaced))
        r = T.run("package.py", self.spaced, again, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, again + ".space-log.json",
                  "--holder", "Fixture Holder", "--out-dir", q("dist"))
        refused(self, r, f"ttf/{STYLE}.ttf", self.spaced, again)
        self.assertFalse(os.path.exists(q("dist")))
        self.assertEqual([n for n in os.listdir(q()) if n.startswith(".package")], [])

    def test_package_refuses_an_out_dir_that_holds_a_link_to_or_from_an_input(self):
        """--replace removes the old package. An input given by a path inside it (a link to a file outside), or by a
        link outside it to a file inside, is refused before anything is removed."""
        for case in ("the input path is a link inside the package", "the input path links into the package"):
            with self.subTest(case):
                q = self.scratch()
                shutil.copytree(self.p("dist"), q("dist"))
                if case.endswith("inside the package"):
                    given = q("dist", "base.json")
                    os.symlink(self.base_json, given)
                else:
                    shutil.copy(self.base_json, q("dist", "base.json"))
                    given = q("base.json")
                    os.symlink(q("dist", "base.json"), given)
                r = T.run("package.py", self.spaced, "--targets", self.targets, "--base-json", given,
                          "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                          "--out-dir", q("dist"), "--replace")
                refused(self, r, "--out-dir")
                self.assertTrue(os.path.lexists(q("dist", "base.json")), "--replace removed an input")
                self.assertEqual(raw(given), raw(self.base_json))

    def test_package_stages_in_a_private_folder_and_publishes_with_the_umask(self):
        """Under a shared umask (0002) the staging folder stays 0700 while the package is verified and its log is
        written, up to the rename; the published folder then has the umask's usual folder mode."""
        import package as P
        q = self.scratch()
        seen = []

        def mode(path):
            return stat.S_IMODE(os.stat(path).st_mode)

        def staging():
            return [mode(os.path.join(q(), n)) for n in os.listdir(q()) if n.startswith(".package-")]
        real_verify, real_save, real_rename = P.verify, P.L.save_json, os.rename

        def verify(*a, **k):
            seen.extend(("verify", m) for m in staging())
            return real_verify(*a, **k)

        def save_json(obj, path):
            real_save(obj, path)
            seen.append(("log", mode(os.path.dirname(path))))

        def rename(src, dst):
            if os.path.basename(src).startswith(".package-"):
                seen.append(("rename", mode(src)))
            return real_rename(src, dst)
        old = os.umask(0o002)
        try:
            with mock.patch.object(P, "verify", verify), mock.patch.object(P.L, "save_json", save_json), \
                    mock.patch("os.rename", rename):
                code, _, err = in_process("package.py", self.spaced, "--targets", self.targets,
                                          "--base-json", self.base_json, "--fit-log", self.fit_log,
                                          "--space-log", self.space_log, "--holder", "Fixture Holder",
                                          "--out-dir", q("dist"))
        finally:
            os.umask(old)
        self.assertEqual(code, 0, err)
        self.assertEqual(seen, [("verify", 0o700), ("log", 0o700), ("rename", 0o700)])
        self.assertEqual(mode(q("dist")), 0o775)

    def test_package_refuses_when_no_spaced_font_is_left(self):
        q = self.scratch()
        r = T.run("package.py", self.fit, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--holder", "Fixture Holder",
                  "--out-dir", q("dist"))
        refused(self, r, "no spaced font")
        self.assertFalse(os.path.exists(q("dist")))

    def test_check_refuses_a_font_the_package_log_did_not_write(self):
        q = self.scratch()
        r = T.run("check_font.py", self.spaced, "--targets", self.targets, "--base-json", self.base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--package-log", self.package_log,
                  "--out-dir", q("checks"))
        refused(self, r, "package")

    # ---------------------------------------------------------------- what is checked is what is used
    def test_each_step_reads_every_input_once(self):
        q = self.scratch()
        common = [self.base_json, self.base, self.ofl, self.targets]
        logs = ["--base-json", self.base_json, "--fit-log", self.fit_log]
        steps = [
            ("fit_font.py", [self.base, self.targets, "--base-json", self.base_json, "--out-dir", q("fit")], common),
            ("space_font.py", [self.fit, self.targets, "--out", q(STYLE + ".ttf"), *logs],
             common + [self.fit_log, self.fit]),
            ("package.py", [self.spaced, "--targets", self.targets, *logs, "--space-log", self.space_log,
                            "--holder", "Fixture Holder", "--out-dir", q("dist")],
             common + [self.fit_log, self.space_log, self.spaced]),
            ("check_font.py", [self.ttf, "--targets", self.targets, *logs, "--space-log", self.space_log,
                               "--package-log", self.package_log, "--out-dir", q("checks")],
             common + [self.fit_log, self.space_log, self.package_log, self.ttf]),
        ]
        for script, args, inputs in steps:
            with self.subTest(step=script):
                with watched(*inputs) as count:
                    code, _, err = in_process(script, *args)
                self.assertIn(code, (0, 1) if script == "check_font.py" else (0,), err)
                again = {os.path.basename(p): n for p, n in count.items() if n > 1}
                self.assertEqual(again, {}, f"{script} opened these inputs again after reading them")

    def test_space_spaces_the_bytes_it_checked(self):
        import package as P
        q = self.scratch()
        font, out = shutil.copy(self.fit, q(STYLE + ".fit.ttf")), q(STYLE + ".ttf")
        with watched(font, swap={font: outlines_moved(self.fit)}):
            code, _, err = in_process("space_font.py", font, self.targets, "--out", out, "--track", "4",
                                      "--base-json", self.base_json, "--fit-log", self.fit_log)
        self.assertEqual(code, 0, err)
        self.assertEqual([e["sha256"] for e in load(out + ".space-log.json")["chain"]["inputs"]], [sha(self.fit)])
        self.assertEqual(P.drawings(TTFont(out))["n"], P.drawings(TTFont(self.spaced))["n"],
                         "space_font.py spaced the file it found after checking another")

    def test_package_publishes_the_bytes_it_checked(self):
        import package as P
        q = self.scratch()
        font = shutil.copy(self.spaced, q(STYLE + ".ttf"))
        with watched(font, swap={font: outlines_moved(self.spaced)}):
            code, _, err = in_process("package.py", font, "--targets", self.targets, "--base-json", self.base_json,
                                      "--fit-log", self.fit_log, "--space-log", self.space_log,
                                      "--holder", "Fixture Holder", "--out-dir", q("dist"))
        self.assertEqual(code, 0, err)
        self.assertEqual([e["sha256"] for e in load(q("dist", "package-log.json"))["chain"]["inputs"]],
                         [sha(self.spaced)])
        published = P.drawings(TTFont(q("dist", "ttf", STYLE + ".ttf")))["n"]
        self.assertEqual(published, P.drawings(TTFont(self.spaced))["n"], "package.py published outlines it never checked")

    # ---------------------------------------------------------------- an output never lands on an input
    def assert_kept(self, r, target, before, script):
        self.assertEqual(raw(target), before, f"{script} wrote over {target}")
        refused(self, r, "input")

    def test_fit_refuses_an_output_path_that_leads_to_an_input(self):
        for name, which, link in [("subset/base.subset.ttf", "base.json", os.symlink),
                                  ("subset/base.subset.ttf", "base.json", os.link),
                                  ("fit-log.json", "OFL.txt", os.symlink),
                                  (STYLE + ".fit.ttf", "base.ttf", os.symlink),
                                  ("fit-log.json", "targets.json", os.symlink)]:
            with self.subTest(output=name, input=which, link=link.__name__):
                q = self.scratch()
                base, ofl = shutil.copy(self.base, q("base.ttf")), shutil.copy(self.ofl, q("OFL.txt"))
                targets = shutil.copy(self.targets, q("targets.json"))
                ok(self, T.approve(base, ofl, q("base.json")))
                os.makedirs(os.path.dirname(q("build", name)), exist_ok=True)
                link(q(which), q("build", name))
                before = raw(q(which))
                r = T.run("fit_font.py", base, targets, "--base-json", q("base.json"), "--out-dir", q("build"))
                self.assert_kept(r, q(which), before, "fit_font.py")

    def test_space_refuses_an_output_path_that_leads_to_an_input(self):
        for out, linked, which in [("out.ttf", "out.ttf", "base.json"),
                                   ("out.ttf", "out.ttf.space-log.json", "fit-log.json"),
                                   ("fit-log.json", None, "fit-log.json")]:
            with self.subTest(out=out, linked=linked, input=which):
                q = self.scratch()
                base_json = shutil.copy(self.base_json, q("base.json"))
                fit_log = shutil.copy(self.fit_log, q("fit-log.json"))
                if linked:
                    os.symlink(q(which), q(linked))
                before = raw(q(which))
                r = T.run("space_font.py", self.fit, self.targets, "--out", q(out), "--base-json", base_json,
                          "--fit-log", fit_log)
                self.assert_kept(r, q(which), before, "space_font.py")

    def test_check_refuses_a_report_path_that_leads_to_an_input(self):
        q = self.scratch()
        base_json = shutil.copy(self.base_json, q("base.json"))
        os.makedirs(q("checks"))
        os.symlink(base_json, q("checks", "check-report.json"))
        before = raw(base_json)
        r = T.run("check_font.py", self.ttf, "--targets", self.targets, "--base-json", base_json,
                  "--fit-log", self.fit_log, "--space-log", self.space_log, "--package-log", self.package_log,
                  "--out-dir", q("checks"))
        self.assert_kept(r, base_json, before, "check_font.py")

    def test_the_font_book_refuses_an_output_path_that_leads_to_an_input(self):
        for linked in (os.path.join("fonts", STYLE + ".ttf"), "index.html"):
            with self.subTest(linked=linked):
                q = self.scratch()
                report = shutil.copy(self.p("checks", "check-report.json"), q("check-report.json"))
                os.makedirs(os.path.dirname(q("book", linked)), exist_ok=True)
                os.symlink(report, q("book", linked))
                before = raw(report)
                r = T.run("font_book.py", self.ttf, "--check-report", report, "--out-dir", q("book"))
                self.assert_kept(r, report, before, "font_book.py")

    # ---------------------------------------------------------------- the font book and the check report
    def test_the_check_report_lists_the_package_outputs_it_verified(self):
        rep = load(self.p("checks", "check-report.json"))
        listed = {(e["file"], e["sha256"]) for e in (rep.get("package") or {}).get("outputs") or []}
        logged = {(e["file"], e["sha256"]) for e in load(self.package_log)["chain"]["outputs"]}
        self.assertEqual(listed, logged)
        self.assertEqual({f for f, _ in listed}, {f"ttf/{STYLE}.ttf", f"webfonts/{STYLE}.woff2"})
        for f, h in listed:
            self.assertEqual(h, sha(self.p("dist", f)))

    def test_the_font_book_refuses_fonts_the_check_report_does_not_list(self):
        q = self.scratch()
        report = self.p("checks", "check-report.json")
        os.makedirs(q("webfonts"))
        w = TTFont(self.ttf)
        w.flavor = "woff2"
        w.save(q("webfonts", STYLE + ".woff2"))
        self.assertNotEqual(sha(q("webfonts", STYLE + ".woff2")), sha(self.p("dist", "webfonts", STYLE + ".woff2")))
        old = load(report)
        old.pop("package", None)
        T.write(q("old-report.json"), json.dumps(old))
        cases = {"a spaced font from the build folder": [self.spaced, "--check-report", report],
                 "a WOFF2 the package did not write": [self.ttf, "--webfonts", q("webfonts"), "--check-report", report],
                 "a report that lists no package output": [self.ttf, "--check-report", q("old-report.json")]}
        for i, (what, args) in enumerate(cases.items()):
            with self.subTest(what):
                r = T.run("font_book.py", *args, "--out-dir", q(f"book{i}"))
                refused(self, r, "check-report")
                self.assertFalse(os.path.exists(q(f"book{i}", "index.html")), "the book was written anyway")


class SubsetBytes(unittest.TestCase):
    """package.py and check_font.py make the fit's subset again and compare bytes, each in its own uv
    environment. The bytes may depend only on the base, the arguments and fontTools, not on whether an optional
    package (uharfbuzz, whose repacker fontTools uses for GSUB and GPOS when it can import it) is installed."""

    def test_the_subset_bytes_do_not_depend_on_uharfbuzz_being_installed(self):
        try:
            import uharfbuzz  # noqa: F401
        except ImportError:
            self.skipTest("uharfbuzz is not installed here, so there is no second serializer to compare with")
        import chain as C
        import fontlib as L
        d = tempfile.mkdtemp(prefix="mf-subset-")
        self.addCleanup(shutil.rmtree, d, True)
        base = T.with_kerning(T.glyf_vf(os.path.join(d, "base.ttf")))
        args = C.subset_args(L.charset_unicodes(["latin"]))
        here = hashlib.sha256(C.build_subset(raw(base), args)).hexdigest()
        code = ("import sys, hashlib; sys.modules['uharfbuzz'] = None; sys.path.insert(0, %r); import chain as C;"
                "print(hashlib.sha256(C.build_subset(open(%r, 'rb').read(), %r)).hexdigest())" % (T.HERE, base, args))
        r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), here, "the subset differs when uharfbuzz cannot be imported")


class Publish(unittest.TestCase):
    def test_replace_keeps_the_old_package_until_the_new_one_is_in_place(self):
        import package as P
        d = tempfile.mkdtemp(prefix="mf-publish-")
        self.addCleanup(shutil.rmtree, d, True)
        out, new = os.path.join(d, "dist"), os.path.join(d, ".package-new")
        os.makedirs(out)
        os.makedirs(new)
        T.write(os.path.join(out, "old.txt"), "the package already published")
        T.write(os.path.join(new, "new.txt"), "the package being published")
        real = os.rename

        def rename(src, dst):
            if os.path.abspath(src) == new:
                raise OSError("synthetic failure while moving the new package into place")
            return real(src, dst)
        with mock.patch("os.rename", rename), mock.patch("os.replace", rename):
            with self.assertRaises(OSError):
                P.publish(new, out, True)
        self.assertTrue(os.path.exists(os.path.join(out, "old.txt")), "the old package was deleted first")
        self.assertEqual(text(os.path.join(out, "old.txt")), "the package already published")
        self.assertEqual([n for n in os.listdir(d) if n not in ("dist", ".package-new")], [])


if __name__ == "__main__":
    unittest.main()
