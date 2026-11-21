# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "uharfbuzz", "skia-pathops"]
# ///
"""The approval step: the question names the sha256 of the font and the licence, the record is written only for
those exact files, and only an explicit approved decision records a base."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest

import testfonts as T


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class ApprovalIsBoundToTheFilesAsked(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mf-approval-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.base = T.glyf_vf(self.p("base.ttf"))
        self.ofl = T.write(self.p("OFL.txt"), T.ofl_text())
        self.out = self.p("base.json")

    def p(self, name):
        return os.path.join(self.dir, name)

    def ask(self):
        r = T.run("record_base.py", "--font", self.base, "--licence", self.ofl, "--source", "local",
                  "--question-only", "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        question = r.stdout.strip()
        hashes = re.findall(r"\b[0-9a-f]{64}\b", question)
        self.assertEqual(len(hashes), 2, f"the question names no font and licence sha256: {question!r}")
        return question, hashes[0], hashes[1]

    def record(self, question, font_sha, licence_sha, decision="approved", answer=T.SYNTHETIC_ANSWER):
        args = ["record_base.py", "--font", self.base, "--licence", self.ofl, "--source", "local",
                "--question", question, "--answer", answer, "--font-sha256", font_sha,
                "--license-sha256", licence_sha, "--out", self.out]
        if decision is not None:
            args += ["--decision", decision]
        return T.run(*args)

    def refused(self, r, *words):
        self.assertNotEqual(r.returncode, 0, r.stdout)
        for w in ("refused",) + words:
            self.assertIn(w, r.stderr)
        self.assertFalse(os.path.exists(self.out), "base.json was written")

    def test_the_question_names_both_files_by_sha256_and_writes_nothing(self):
        question, font_sha, licence_sha = self.ask()
        self.assertEqual((font_sha, licence_sha), (sha(self.base), sha(self.ofl)))
        self.assertIn("OFL", question)
        self.assertFalse(os.path.exists(self.out))

    def test_the_question_is_not_asked_about_a_base_that_would_be_refused(self):
        T.write(self.ofl, T.APACHE_TEXT)
        r = T.run("record_base.py", "--font", self.base, "--licence", self.ofl, "--source", "local",
                  "--question-only", "--out", self.out)
        self.refused(r, "OFL-1.1")
        self.assertEqual(r.stdout, "")

    def test_the_record_keeps_the_question_the_answer_and_the_decision(self):
        question, font_sha, licence_sha = self.ask()
        r = self.record(question, font_sha, licence_sha)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.out, encoding="utf-8") as fh:
            appr = json.load(fh)["approval"]
        self.assertEqual((appr["question"], appr["answer"], appr["decision"]),
                         (question, T.SYNTHETIC_ANSWER, "approved"))

    def test_a_font_changed_while_the_question_waited_is_refused(self):
        question, font_sha, licence_sha = self.ask()
        T.glyf_vf(self.base, copyright_line="Copyright 2026 Someone Else")  # same path, other bytes
        self.assertNotEqual(sha(self.base), font_sha)
        self.refused(self.record(question, font_sha, licence_sha), "sha256", "--question-only")

    def test_a_licence_changed_while_the_question_waited_is_refused(self):
        question, font_sha, licence_sha = self.ask()
        T.write(self.ofl, T.ofl_text("Copyright 2026 Someone Else"))
        self.refused(self.record(question, font_sha, licence_sha), "sha256", "--question-only")

    def test_a_question_that_does_not_name_the_hashes_is_refused(self):
        _, font_sha, licence_sha = self.ask()
        self.refused(self.record(T.SYNTHETIC_QUESTION, font_sha, licence_sha), "question")

    def test_a_question_other_than_the_one_these_files_give_is_refused_even_with_both_hashes(self):
        question, font_sha, licence_sha = self.ask()
        for other in (f"Synthetic: may I build on any font I like? Font {font_sha}, licence {licence_sha}.",
                      question + " Any other base is fine too."):
            with self.subTest(question=other):
                self.refused(self.record(other, font_sha, licence_sha), "question", "--question-only")

    def test_a_source_url_changed_in_the_shortlist_while_the_question_waited_is_refused(self):
        shortlist = self.p("shortlist.json")

        def rows(url):
            T.write(shortlist, json.dumps({"rows": [{"family": T.BASE_FAMILY, "file": self.base,
                                                     "licence_path": self.ofl, "origin": "google/fonts/ofl/lumen",
                                                     "url": url}]}))
        rows("https://example.org/fonts/lumen-ledger.ttf")
        src = ["--shortlist", shortlist, "--family", T.BASE_FAMILY]
        ask = T.run("record_base.py", *src, "--question-only", "--out", self.out)
        self.assertEqual(ask.returncode, 0, ask.stderr)
        question = ask.stdout.strip()
        self.assertIn("https://example.org/fonts/lumen-ledger.ttf", question)
        rows("https://example.org/elsewhere/lumen-ledger.ttf")
        r = T.run("record_base.py", *src, "--question", question, "--answer", T.SYNTHETIC_ANSWER,
                  "--decision", "approved", "--font-sha256", sha(self.base), "--license-sha256", sha(self.ofl),
                  "--out", self.out)
        self.refused(r, "question")

    def test_a_manifest_url_is_in_the_question_and_a_changed_one_is_refused(self):
        key, url = "fixtures/lumen-ledger@1", "https://example.org/fonts/lumen-ledger.ttf"
        entry = T.manifest_entry(key, self.base, self.ofl)
        entry["files"][0]["url"] = url
        skill = T.pinned_skill(self.dir, {"families": {key: entry}})
        src = ["--font", self.base, "--licence", self.ofl, "--source", "manifest", "--manifest-entry", key]
        ask = T.run("record_base.py", *src, "--url", url, "--question-only", "--out", self.out, skill=skill)
        self.assertEqual(ask.returncode, 0, ask.stderr)
        question = ask.stdout.strip()
        self.assertIn(key, question)
        self.assertIn(url, question)
        record = ["--question", question, "--answer", T.SYNTHETIC_ANSWER, "--decision", "approved",
                  "--font-sha256", sha(self.base), "--license-sha256", sha(self.ofl), "--out", self.out]
        entry["files"][0]["url"] = moved = "https://example.org/elsewhere/lumen-ledger.ttf"
        T.write(os.path.join(skill, "bases.json"), json.dumps({"families": {key: entry}}))
        self.refused(T.run("record_base.py", *src, "--url", moved, *record, skill=skill), "question")
        self.refused(T.run("record_base.py", *src, "--url", url, *record, skill=skill), "pinned manifest")
        entry["files"][0]["url"] = url
        T.write(os.path.join(skill, "bases.json"), json.dumps({"families": {key: entry}}))
        r = T.run("record_base.py", *src, "--url", url, *record, skill=skill)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_only_an_approved_decision_records_a_base(self):
        question, font_sha, licence_sha = self.ask()
        for decision in (None, "declined", "yes", "Approved "):
            with self.subTest(decision=decision):
                r = self.record(question, font_sha, licence_sha, decision=decision,
                                answer="synthetic e2e answer: no, not this one")
                self.refused(r, "--decision approved")

    def test_a_step_refuses_a_base_json_whose_decision_was_edited(self):
        question, font_sha, licence_sha = self.ask()
        self.assertEqual(self.record(question, font_sha, licence_sha).returncode, 0)
        with open(self.out, encoding="utf-8") as fh:
            rec = json.load(fh)
        for field, value in (("decision", "declined"), ("question", T.SYNTHETIC_QUESTION),
                             ("question", question + " Any other base is fine too.")):
            with self.subTest(field=field, value=value[-40:]):
                edited = json.loads(json.dumps(rec))
                edited["approval"][field] = value
                T.write(self.p("edited.json"), json.dumps(edited))
                targets = T.write(self.p("targets.json"), json.dumps({"family": T.NEW_FAMILY, "styles": [], "targets": {}}))
                r = T.run("fit_font.py", self.base, targets, "--base-json", self.p("edited.json"),
                          "--out-dir", self.p("build"))
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertIn("refused", r.stderr)
                self.assertIn("approval", r.stderr)
                self.assertFalse(os.path.exists(self.p("build")))



class PinnedHangulBase(unittest.TestCase):
    """A base recorded as from the pinned manifest is the entry it names, byte for byte, and a build with korean in
    its scripts takes no other base. The skill copy's bases.json pins one synthetic base as lumen-ledger."""
    KEY = "lumen-ledger"

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mf-pinned-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.base = T.glyf_vf(self.p("LumenLedger[wght].ttf"))
        self.ofl = T.write(self.p("OFL.txt"), T.ofl_text())
        self.out = self.p("base.json")
        self.skill = T.pinned_skill(self.dir, {"families": {self.KEY: T.manifest_entry(self.KEY, self.base, self.ofl)}})
        self.targets = T.write(self.p("targets.json"), json.dumps(
            {"family": T.NEW_FAMILY, "scripts": ["latin", "korean"], "styles": [{"name": "Regular", "weight": 400}],
             "targets": {}, "tolerances": {}, "hangul": {"stem": [{"value": 90, "unit": "cap700", "confidence": "high"}]}}))

    def p(self, *name):
        return os.path.join(self.dir, *name)

    def ask(self, *source):
        return T.run("record_base.py", "--font", self.base, "--licence", self.ofl, *source, "--question-only",
                     "--out", self.out, skill=self.skill)

    def refused(self, r, *words):
        self.assertNotEqual(r.returncode, 0, r.stdout)
        for w in ("refused",) + words:
            self.assertIn(w, r.stderr)

    def test_the_approval_step_asks_about_a_manifest_base_only_when_its_files_are_the_pinned_ones(self):
        pinned = T.pinned_source(self.KEY, self.base)
        r = self.ask(*pinned)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"from the pinned manifest entry {self.KEY}", r.stdout)
        cases = {"an entry the manifest does not have": ("--source", "manifest", "--manifest-entry", "elsewhere",
                                                         "--url", T.pinned_url(self.KEY, self.base)),
                 "a URL the entry does not pin": ("--source", "manifest", "--manifest-entry", self.KEY,
                                                  "--url", "https://fonts.example/elsewhere/LumenLedger[wght].ttf"),
                 "no URL": ("--source", "manifest", "--manifest-entry", self.KEY)}
        for case, source in cases.items():
            with self.subTest(case=case):
                self.refused(self.ask(*source), "pinned manifest")
        T.write(self.ofl, T.ofl_text("Copyright 2026 Someone Else"))
        with self.subTest(case="a licence the entry does not pin"):
            self.refused(self.ask(*pinned), "pinned manifest", "licence")

    def test_a_shortlist_row_whose_file_changed_after_the_ranking_is_refused(self):
        T.write(self.p("shortlist.json"), json.dumps({"rows": [
            {"family": T.BASE_FAMILY, "file": self.base, "licence_path": self.ofl, "origin": f"manifest/{self.KEY}",
             "manifest_entry": self.KEY, "url": T.pinned_url(self.KEY, self.base)}]}))
        src = ("--shortlist", self.p("shortlist.json"), "--family", T.BASE_FAMILY, "--question-only", "--out", self.out)
        r = T.run("record_base.py", *src, skill=self.skill)
        self.assertEqual(r.returncode, 0, r.stderr)
        T.glyf_vf(self.base, copyright_line="Copyright 2026 Someone Else")  # the cached file, other bytes
        self.refused(T.run("record_base.py", *src, skill=self.skill), "pinned manifest", sha(self.base))

    def build_steps(self, base_json):
        """fit_font.py and package.py on these targets with this base.json, as far as they get."""
        logs = ("--fit-log", self.p("build", "fit-log.json"), "--space-log", self.p("build", "x.space-log.json"))
        return {"fit": T.run("fit_font.py", self.base, self.targets, "--base-json", base_json, "--out-dir",
                             self.p("build"), skill=self.skill),
                "package": T.run("package.py", self.base, "--targets", self.targets, "--base-json", base_json, *logs,
                                 "--holder", "Synthetic Holder", "--out-dir", self.p("dist"), skill=self.skill)}

    def test_a_build_with_korean_in_its_scripts_refuses_a_base_from_outside_the_manifest(self):
        self.assertEqual(T.approve(self.base, self.ofl, self.p("local.json"), skill=self.skill).returncode, 0)
        for step, r in self.build_steps(self.p("local.json")).items():
            with self.subTest(step=step):
                self.refused(r, "pinned manifest", "local")
        self.assertFalse(os.path.exists(self.p("build")))

    def test_a_build_with_korean_in_its_scripts_refuses_a_base_the_manifest_no_longer_pins(self):
        r = T.approve(self.base, self.ofl, self.out, *T.pinned_source(self.KEY, self.base), skill=self.skill)
        self.assertEqual(r.returncode, 0, r.stderr)
        fit = self.build_steps(self.out)["fit"]
        self.assertNotIn("pinned manifest", fit.stderr)  # the pinned base passes, and the fit stops at its Hangul
        self.assertIn("H1 syllables", fit.stderr)
        entry = T.manifest_entry(self.KEY, self.base, self.ofl)
        entry["files"][0]["sha256"] = "0" * 64
        T.write(os.path.join(self.skill, "bases.json"), json.dumps({"families": {self.KEY: entry}}))
        for step, r in self.build_steps(self.out).items():
            with self.subTest(step=step):
                self.refused(r, "pinned manifest", sha(self.base))

if __name__ == "__main__":
    unittest.main()
