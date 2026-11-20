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
        src = ["--font", self.base, "--licence", self.ofl, "--source", "manifest", "--manifest-entry",
               "fixtures/lumen-ledger@1"]
        ask = T.run("record_base.py", *src, "--url", "https://example.org/fonts/lumen-ledger.ttf", "--question-only",
                    "--out", self.out)
        self.assertEqual(ask.returncode, 0, ask.stderr)
        question = ask.stdout.strip()
        self.assertIn("fixtures/lumen-ledger@1", question)
        self.assertIn("https://example.org/fonts/lumen-ledger.ttf", question)
        record = ["--question", question, "--answer", T.SYNTHETIC_ANSWER, "--decision", "approved",
                  "--font-sha256", sha(self.base), "--license-sha256", sha(self.ofl), "--out", self.out]
        moved = T.run("record_base.py", *src, "--url", "https://example.org/elsewhere/lumen-ledger.ttf", *record)
        self.refused(moved, "question")
        self.refused(T.run("record_base.py", *src, *record), "question")
        r = T.run("record_base.py", *src, "--url", "https://example.org/fonts/lumen-ledger.ttf", *record)
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


if __name__ == "__main__":
    unittest.main()
