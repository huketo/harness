# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "uharfbuzz"]
# ///
"""Licence gates: Reserved Font Names, OFL-1.1 only, and English name records."""
import json
import os
import shutil
import tempfile
import unittest

from fontTools.ttLib import TTFont

import fontlib as L
import testfonts as T


class ReservedFontNames(unittest.TestCase):
    """C3: one line inside an otherwise unmodified OFL-1.1 text, expected list in order."""

    def rfn(self, line):
        return L.reserved_font_names(T.ofl_text(line))

    def test_c3_case1_no_rfn_phrase(self):
        self.assertEqual(self.rfn("Copyright 2026 The Lumen Ledger Project Authors (https://example.org/lumen-ledger)"), [])

    def test_c3_case2_one_quoted_name(self):
        self.assertEqual(self.rfn('Copyright 2021 The Tessera Project Authors, with Reserved Font Name "Tessera".'),
                         ["Tessera"])

    def test_c3_case3_two_quoted_names(self):
        self.assertEqual(self.rfn('Copyright (c) 2019 Lumen Type, with Reserved Font Names "Lumen" and "Lumen Ledger".'),
                         ["Lumen", "Lumen Ledger"])

    def test_c3_case4_two_unquoted_names_joined_by_and(self):
        self.assertEqual(self.rfn("Copyright 2017 Example Foundry, with Reserved Font Name Coda and Coda Mono."),
                         ["Coda", "Coda Mono"])

    def test_c3_case5_three_quoted_names(self):
        self.assertEqual(self.rfn('Copyright 2022 Arbor Type, with Reserved Font Names "Arbor", "Arbor Text" and '
                                  '"Arbor Display".'), ["Arbor", "Arbor Text", "Arbor Display"])

    def test_body_definition_sentence_is_not_a_name(self):
        self.assertIn('"Reserved Font Name" refers to', T.OFL_BODY)
        self.assertEqual(L.reserved_font_names(T.OFL_BODY), [])


class OflOnly(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mf-licence-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def p(self, name):
        return os.path.join(self.dir, name)

    def record(self, font, licence, out="base.json"):
        return T.run("record_base.py", "--font", font, "--licence", licence, "--source", "local",
                     "--question", T.SYNTHETIC_QUESTION, "--answer", T.SYNTHETIC_ANSWER, "--out", self.p(out))

    def test_apache_licence_text_is_refused(self):
        font = T.glyf_vf(self.p("base.ttf"))
        r = self.record(font, T.write(self.p("LICENSE.txt"), T.APACHE_TEXT))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("refused", r.stderr)
        self.assertIn("OFL-1.1", r.stderr)
        self.assertFalse(os.path.exists(self.p("base.json")))

    def test_apache_notice_in_name_13_is_refused(self):
        font = T.glyf_vf(self.p("base.ttf"), notice=T.APACHE_NOTICE)
        r = self.record(font, T.write(self.p("OFL.txt"), T.ofl_text()))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("refused", r.stderr)
        self.assertIn("name ID 13", r.stderr)
        self.assertFalse(os.path.exists(self.p("base.json")))

    def test_base_json_with_another_licence_id_is_refused(self):
        font = T.glyf_vf(self.p("base.ttf"))
        r = self.record(font, T.write(self.p("OFL.txt"), T.ofl_text()))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.p("base.json"), encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["license"]["id"] = "Apache-2.0"
        T.write(self.p("edited.json"), json.dumps(rec))
        targets = T.write(self.p("targets.json"), json.dumps({"family": T.NEW_FAMILY, "styles": [], "targets": {}}))
        r = T.run("fit_font.py", font, targets, "--base-json", self.p("edited.json"), "--out-dir", self.p("build"))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("refused", r.stderr)
        self.assertIn("OFL-1.1", r.stderr)
        self.assertFalse(os.path.exists(self.p("build")))

    def test_find_foundation_keeps_only_ofl_candidates(self):
        import find_foundation as FF
        ofl = TTFont(T.glyf_vf(self.p("ofl.ttf")))
        apache = TTFont(T.glyf_vf(self.p("apache.ttf"), notice=T.APACHE_NOTICE))
        self.assertEqual(FF.licence_of(ofl, T.ofl_text())["licence"], "OFL-1.1")
        self.assertIsNone(FF.licence_of(apache)["licence"])
        catalog = [{"id": f, "family": f, "type": "google", "license": lic, "category": "sans-serif",
                    "subsets": ["latin"], "styles": ["normal"], "defSubset": "latin"}
                   for f, lic in (("Lumen Ledger", "OFL-1.1"), ("Arbor Text", "Apache-2.0"))]
        for wanted in ([], ["arbor text", "lumen ledger"]):
            with self.subTest(wanted=wanted):
                got = [c["family"] for c in FF.candidates(catalog, "sans-serif", {"latin"}, wanted)]
                self.assertEqual(got, ["Lumen Ledger"])


class RecordAndLoadCheckTheSameThings(unittest.TestCase):
    """record_base.py and every step that reads base.json run one check of the base's files: a TrueType variable
    font in a plain SFNT file, the OFL 1.1 text word for word, a name ID 13 that names the OFL 1.1 and no other
    version, and the notice and Reserved Font Names base.json records equal to what the files say now."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mf-shared-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.base = T.glyf_vf(self.p("base.ttf"))
        self.ofl = T.write(self.p("OFL.txt"), T.ofl_text())
        r = T.approve(self.base, self.ofl, self.p("base.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.p("base.json"), encoding="utf-8") as fh:
            self.rec = json.load(fh)
        self.targets = T.write(self.p("targets.json"), json.dumps({"family": T.NEW_FAMILY, "styles": [], "targets": {}}))

    def p(self, name):
        return os.path.join(self.dir, name)

    def refused_at_record(self, font, licence, *words):
        out = self.p(os.path.basename(font) + ".json")
        r = T.approve(font, licence, out)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        for w in ("refused",) + words:
            self.assertIn(w, r.stderr)
        self.assertFalse(os.path.exists(out))

    def refused_at_load(self, font, *words, **edit):
        """base.json edited by hand to name these files, with their true sha256: fit_font.py must still refuse."""
        rec = json.loads(json.dumps(self.rec))
        for key, value in edit.items():
            section, field = key.split("__")
            rec[section][field] = value
        for section in ("font", "license"):
            rec[section]["sha256"] = sha(rec[section]["file"])
        T.write(self.p("edited.json"), json.dumps(rec))
        r = T.run("fit_font.py", font, self.targets, "--base-json", self.p("edited.json"), "--out-dir", self.p("build"))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        for w in ("refused",) + words:
            self.assertIn(w, r.stderr)
        self.assertFalse(os.path.exists(self.p("build")))

    def test_a_licence_file_with_only_the_title_is_refused_at_record(self):
        self.refused_at_record(self.base, T.write(self.p("title.txt"), T.TITLE_ONLY_TEXT), "OFL-1.1")

    def test_a_licence_file_with_only_the_title_is_refused_at_load(self):
        title = T.write(self.p("title.txt"), T.TITLE_ONLY_TEXT)
        self.refused_at_load(self.base, "OFL-1.1", license__file=title)

    def test_a_licence_text_with_a_changed_condition_is_refused(self):
        edited = T.ofl_text().replace("may be sold by itself", "may be sold")
        self.refused_at_record(self.base, T.write(self.p("edited.txt"), edited), "OFL-1.1")

    def test_a_name_id_13_that_names_ofl_1_0_is_refused_at_record(self):
        font = T.glyf_vf(self.p("ofl10.ttf"), notice=T.OFL_10_NOTICE)
        self.refused_at_record(font, self.ofl, "name ID 13")

    def test_a_name_id_13_that_names_ofl_1_0_is_refused_at_load(self):
        font = T.glyf_vf(self.p("ofl10.ttf"), notice=T.OFL_10_NOTICE)
        self.refused_at_load(font, "name ID 13", font__file=font, license__name_id_13=T.OFL_10_NOTICE)

    def test_a_recorded_notice_other_than_the_fonts_is_refused_at_load(self):
        self.refused_at_load(self.base, "name ID 13", license__name_id_13=T.OFL_NOTICE + " (edited)")

    def test_recorded_reserved_font_names_other_than_the_licences_are_refused_at_load(self):
        self.assertEqual(self.rec["license"]["reserved_font_names"], [])
        self.refused_at_load(self.base, "Reserved Font Name", license__reserved_font_names=["Lumen"])

    def test_a_woff_or_woff2_base_is_refused_at_record(self):
        for flavor in ("woff", "woff2"):
            with self.subTest(flavor=flavor):
                font = T.flavoured(self.base, self.p(f"base.{flavor}"), flavor)
                self.refused_at_record(font, self.ofl, flavor.upper())

    def test_a_woff2_base_is_refused_at_load(self):
        font = T.flavoured(self.base, self.p("base.woff2"), "woff2")
        self.refused_at_load(font, "WOFF2", font__file=font)


def sha(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class EnglishNames(unittest.TestCase):
    def test_english_record_wins_over_a_later_language(self):
        d = tempfile.mkdtemp(prefix="mf-names-")
        self.addCleanup(shutil.rmtree, d, True)
        p = T.glyf_vf(os.path.join(d, "base.ttf"),
                      extra_names={"designer": {"en": "Fixture Designer", "ja": "フィクスチャ"}})
        f = TTFont(p)
        langs = [r.langID for r in f["name"].names if r.nameID == 9]
        self.assertEqual(langs, [0x409, 0x411])  # English first, so a last-one-wins read gets Japanese
        self.assertEqual(L.english_names(f)[9], "Fixture Designer")


if __name__ == "__main__":
    unittest.main()
