# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "fonttools", "uharfbuzz"]
# ///
"""Reserved Font Names come only from the OFL's copyright lines (fonts.reserved_font_names): the five shared cases,
each line inside an otherwise unmodified OFL-1.1 text, whose own definition of the term yields nothing."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fonts as F  # noqa: E402
import gate_fixtures as G  # noqa: E402

CASES = {
    "no_phrase_on_any_copyright_line": ("Copyright 2021 The Tessera Project Authors", []),
    "one_quoted_name": ('Copyright 2021 The Tessera Project Authors, with Reserved Font Name "Tessera".', ["Tessera"]),
    "two_quoted_names_joined_by_and": ('Copyright (c) 2019 Lumen Type, with Reserved Font Names "Lumen" and "Lumen Ledger".',
                                       ["Lumen", "Lumen Ledger"]),
    "two_unquoted_names_joined_by_and": ("Copyright 2017 Example Foundry, with Reserved Font Name Coda and Coda Mono.",
                                         ["Coda", "Coda Mono"]),
    "three_quoted_names_in_a_list": ('Copyright 2022 Arbor Type, with Reserved Font Names "Arbor", "Arbor Text" and "Arbor Display".',
                                     ["Arbor", "Arbor Text", "Arbor Display"]),
}


class ReservedFontNames(unittest.TestCase):
    """One test per shared case, so each is reported on its own line."""

    def names(self, case: str) -> None:
        line, expected = CASES[case]
        self.assertEqual(F.reserved_font_names(line + "\n" + G.OFL_BODY), expected)

    def test_case_1_no_phrase_on_any_copyright_line(self):
        self.names("no_phrase_on_any_copyright_line")

    def test_case_2_one_quoted_name(self):
        self.names("one_quoted_name")

    def test_case_3_two_quoted_names_joined_by_and(self):
        self.names("two_quoted_names_joined_by_and")

    def test_case_4_two_unquoted_names_joined_by_and(self):
        self.names("two_unquoted_names_joined_by_and")

    def test_case_5_three_quoted_names_in_a_list(self):
        self.names("three_quoted_names_in_a_list")

    def test_fetch_reports_the_names_from_the_copyright_line(self):
        ws = G.Workspace()
        self.addCleanup(ws.close)
        G.install_font(ws.fonts, "Lumen Sans", CASES["two_quoted_names_joined_by_and"][0])
        self.assertEqual(F.fetch("Lumen Sans", ws.fonts)["reserved_names"], ["Lumen", "Lumen Ledger"])


if __name__ == "__main__":
    unittest.main()
