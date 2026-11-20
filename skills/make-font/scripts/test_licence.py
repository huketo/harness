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
        return T.approve(font, licence, self.p(out))

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
        out = self.p(f"{os.path.basename(font)}-{os.path.basename(licence)}.json")
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

    def test_a_licence_head_with_a_line_that_is_not_a_copyright_line_is_refused_at_record(self):
        head = T.ofl_text().replace("\n\n", "\nYou may not modify this Font Software.\n\n", 1)
        self.refused_at_record(self.base, T.write(self.p("head.txt"), head), "OFL-1.1", "copyright")

    def test_a_licence_head_with_a_line_that_is_not_a_copyright_line_is_refused_at_load(self):
        head = T.ofl_text().replace("\n\n", "\nYou may not modify this Font Software.\n\n", 1)
        self.refused_at_load(self.base, "OFL-1.1", license__file=T.write(self.p("head.txt"), head))

    def test_a_copyright_line_that_adds_a_condition_is_refused(self):
        line = "Copyright 2026 The Lumen Ledger Project Authors. Modified versions may not be distributed."
        self.refused_at_record(self.base, T.write(self.p("cond.txt"), T.ofl_text(line)), "OFL-1.1", "copyright")

    def test_a_name_id_13_that_does_not_affirm_the_ofl_1_1_is_refused_at_record(self):
        for i, notice in enumerate(NOT_AN_OFL_11_NOTICE):
            with self.subTest(notice=notice):
                self.refused_at_record(T.glyf_vf(self.p(f"n13-{i}.ttf"), notice=notice), self.ofl, "name ID 13")

    def test_a_name_id_13_that_denies_the_ofl_1_1_is_refused_at_load(self):
        font = T.glyf_vf(self.p("denied.ttf"), notice=NOT_AN_OFL_11_NOTICE[0])
        self.refused_at_load(font, "name ID 13", font__file=font, license__name_id_13=NOT_AN_OFL_11_NOTICE[0])

    def test_a_copyright_line_with_a_trailing_clause_is_refused_as_an_unsupported_form(self):
        for i, line in enumerate(TRAILING_CLAUSE_COPYRIGHT_LINES):
            with self.subTest(line=line):
                self.refused_at_record(self.base, T.write(self.p(f"tail-{i}.txt"), T.ofl_text(line)), "OFL-1.1",
                                       "not a supported copyright line")

    def test_a_copyright_line_with_a_trailing_clause_is_refused_at_load(self):
        licence = T.write(self.p("tail.txt"), T.ofl_text(TRAILING_CLAUSE_COPYRIGHT_LINES[0]))
        self.refused_at_load(self.base, "not a supported copyright line", license__file=licence)

    def test_a_name_id_13_with_a_trailing_clause_is_refused_at_record(self):
        for i, notice in enumerate(TRAILING_CLAUSE_NOTICES):
            with self.subTest(notice=notice):
                self.refused_at_record(T.glyf_vf(self.p(f"tail-{i}.ttf"), notice=notice), self.ofl, "name ID 13")

    def test_a_name_id_13_with_a_trailing_clause_is_refused_at_load(self):
        font = T.glyf_vf(self.p("tail.ttf"), notice=TRAILING_CLAUSE_NOTICES[0])
        self.refused_at_load(font, "name ID 13", font__file=font, license__name_id_13=TRAILING_CLAUSE_NOTICES[0])

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


# Notices that mention the OFL 1.1 without granting it: a denial, an exception, a condition, a bare label.
NOT_AN_OFL_11_NOTICE = [
    "This font is not licensed under the SIL Open Font License, Version 1.1.",
    "This Font Software is licensed under the SIL Open Font License, Version 1.1, except the figures.",
    "This Font Software is licensed under the SIL Open Font License, Version 1.1 unless you sell it.",
    "OFL-1.1",
]
# Notices that grant the OFL 1.1 and then add a clause of their own, in words no list of terms would catch.
TRAILING_CLAUSE_NOTICES = [
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. Distribution is subject to "
    "prior written approval.",
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a "
    "FAQ at: https://openfontlicense.org. Redistribution is subject to prior written approval by Lumen Type.",
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a "
    "FAQ at: https://openfontlicense.org Redistribution is subject to prior written approval.",
]
# Copyright lines that end in a clause of their own: after a full stop, after a comma, after the Reserved Font
# Name, and in a script without capital letters.
TRAILING_CLAUSE_COPYRIGHT_LINES = [
    "Copyright 2026 The Lumen Ledger Project Authors (https://example.org/lumen-ledger). Distribution is subject "
    "to prior written approval.",
    "Copyright 2026 Lumen Type, distribution is subject to prior written approval.",
    'Copyright 2021 The Tessera Project Authors, with Reserved Font Name "Tessera". Distribution is subject to '
    "prior written approval.",
    "Copyright 2017 Example Foundry, with Reserved Font Name Coda and Coda Mono, subject to prior written approval.",
    "Copyright 2026 Lumen Type. \ubc30\ud3ec\ub294 \uc0ac\uc804 \uc11c\uba74 \uc2b9\uc778\uc744 "
    "\ubc1b\uc544\uc57c \ud569\ub2c8\ub2e4.",
    "Copyright 2026 Lumen Type (https://example.org/lumen) (approval needed).",
]


class WhatRealOflFilesSay(unittest.TestCase):
    """The stricter reading still takes the OFL files and notices published fonts carry."""

    def test_published_notices_are_ofl_1_1_notices(self):
        for notice in (T.OFL_NOTICE,
                       "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is "
                       "available with a FAQ at: http://scripts.sil.org/OFL",
                       "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is "
                       "available with a FAQ at: https://scripts.sil.org/OFL. The license for the Example Foundry's "
                       "Modified Version is available at https://example.org/LICENSE.md.",
                       "This Font Software is licensed under the SIL Open Font License, Version 1.1. This Font "
                       "Software is distributed on an \"AS IS\" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, "
                       "either express or implied."):
            with self.subTest(notice=notice):
                self.assertTrue(L.is_ofl_11_notice(notice))

    def test_supported_copyright_line_forms_are_an_ofl_1_1_text(self):
        """Copyright, an optional (c) or the sign, the years, the holder, an optional address in parentheses, an
        optional Reserved Font Name clause (C3), an optional full stop."""
        c3 = ['Copyright 2021 The Tessera Project Authors, with Reserved Font Name "Tessera".',
              'Copyright (c) 2019 Lumen Type, with Reserved Font Names "Lumen" and "Lumen Ledger".',
              "Copyright 2017 Example Foundry, with Reserved Font Name Coda and Coda Mono.",
              'Copyright 2022 Arbor Type, with Reserved Font Names "Arbor", "Arbor Text" and "Arbor Display".']
        for line in c3 + [
                "Copyright 2026 The Lumen Ledger Project Authors (https://example.org/lumen-ledger)",
                "Copyright 2026 The Lumen Ledger Project Authors.",
                "copyright \u00a9 2015, 2019 Arbor Type, Inc. (https://example.org/arbor)",
                'Copyright (c) 2010-2014 by Lumen Type Studio (team@example.org) with Reserved Font Name "Lumen"',
                "Copyright (c) 2011, J. Fixture and the Arbor Type Authors (www.example.org|type@example.org), "
                "with Reserved Font Name Arbor.",
                "Copyright 2020 Lumen Type GmbH & Co. KG"]:
            with self.subTest(line=line):
                self.assertIsNone(L.ofl_11_text_problem(T.ofl_text(line)))

    def test_copyright_lines_with_reserved_names_and_windows_line_ends_are_an_ofl_1_1_text(self):
        head = ('Copyright © 2017 Lumen Type. with Reserved Font Name "Lumen"\r\n'
                "Copyright 2026 The Lumen Ledger Project Authors (https://example.org/lumen-ledger)\r\n\r\n")
        text = head + T.OFL_BODY.replace("\n", "\r\n")
        self.assertTrue(L.is_ofl_11_text(text))
        self.assertEqual(L.reserved_font_names(text), ["Lumen"])


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
