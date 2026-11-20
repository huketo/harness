# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools"]
# ///
"""Ask the person to approve a base, then record their answer in base.json. Two runs, a person between them.

  1. uv run record_base.py --shortlist shortlist.json --family "Family" --question-only --out base.json
     uv run record_base.py --font <base-vf.ttf> --licence <OFL.txt> --source google-fonts|manifest|local \\
         [--url URL] [--manifest-entry ID] --question-only --out base.json
  2. the same file arguments, then
         --question "<the printed question, verbatim>" --answer "<their answer, verbatim>" \\
         --decision approved --font-sha256 <hash from the question> --license-sha256 <hash from the question>

Only a person can decide that a font may be the base. This script cannot check that decision; it binds it to the
files. Run 1 checks the files and prints the question, which names the font's and the OFL text's sha256 and
where the font came from, and writes nothing. Run 2 makes the question again from the same arguments and writes
base.json only when both files still have the sha256 values the question named, the question passed in is that
question word for word (so a shortlist whose source URL changed while the person read it is refused), and
--decision is "approved". The answer is kept word for word and never read for a yes; a person who declines gets
no base.json.

Both runs refuse a base this skill cannot build on (chain.read_base, the same check every later step runs): a file
that is not a plain TrueType variable font (WOFF, WOFF2, CFF, static and collections are refused), an OFL text that
is not copyright lines and then the SIL Open Font License 1.1 word for word (any other line before the licence, or
a copyright line that states a term, is refused), or a name ID 13 that does not grant the OFL 1.1 alone ("This Font
Software is licensed under the SIL Open Font License, Version 1.1"; a denial, an exception or another version is
refused). base.json holds the font's and the licence's sha256, name ID 13 exactly, the Reserved Font Names from the
OFL's copyright lines, where the font came from, and the question, answer and decision. It is written once: a
second run with the same record leaves it as it is, any other content is refused. fit_font.py, space_font.py,
package.py and check_font.py all start from it.
"""
import argparse
import datetime
import os
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain as C  # noqa: E402

SOURCES = C.SOURCES


def from_shortlist(files, path, family):
    rows = files.read(path, "shortlist").json("shortlist")["rows"]
    row = next((r for r in rows if r["family"].lower() == family.lower()), None)
    if row is None:
        raise C.Refused(f"{family!r} is not in {path}: {', '.join(r['family'] for r in rows)}")
    if not row.get("licence_path"):
        raise C.Refused(f"{family!r} in {path} has no OFL text beside it; pass --font and --licence")
    kind = "google-fonts" if str(row.get("origin", "")).startswith("google/fonts/") else "local"
    return row["file"], row["licence_path"], kind, row.get("url")


def build(a, files):
    """The question (with --question-only) or the record to write."""
    font_path, lic_path, kind, url = a.font, a.licence, a.source, a.url
    if a.shortlist:
        if not a.family:
            raise C.Refused("--shortlist needs --family, the name of the row the person approved")
        font_path, lic_path, kind, url = from_shortlist(files, a.shortlist, a.family)
    if not font_path or not lic_path or not kind:
        raise C.Refused("give --shortlist with --family, or --font, --licence and --source")
    if kind not in SOURCES:
        raise C.Refused(f"--source is one of {', '.join(SOURCES)}")
    if kind == "google-fonts" and not url:
        raise C.Refused("--source google-fonts needs --url, the address the font was fetched from")
    if kind == "manifest" and not a.manifest_entry:
        raise C.Refused("--source manifest needs --manifest-entry, the pinned entry the font came from")
    if kind == "local" and (url or a.manifest_entry):
        raise C.Refused("--source local takes neither --url nor --manifest-entry")
    source = {"kind": kind, "url": url if kind != "local" else None,
              "manifest_entry": a.manifest_entry if kind == "manifest" else None}
    base = C.read_base(files, font_path, lic_path)
    question = C.approval_question(font_path, lic_path, source, base)
    if a.question_only:
        return question
    asked = {"font": a.font_sha256, "licence": a.license_sha256}
    if not all(asked.values()):
        raise C.Refused("--font-sha256 and --license-sha256 are required: the two sha256 values the question "
                        "named. Ask with --question-only first.")
    for what, now in (("font", base.font.sha256), ("licence", base.licence.sha256)):
        if asked[what] != now:
            raise C.Refused(f"the {what} has sha256 {now} now, but the question named {asked[what]}. It changed "
                            "while the question waited, so the answer is not about this file. Ask again with "
                            "--question-only.")
    answer = a.answer or ""
    if not (a.question or "").strip() or not answer.strip():
        raise C.Refused("--question and --answer are both required, verbatim: the approval is the person's, "
                        "and base.json keeps their words")
    C.require_approval({"question": a.question, "answer": answer, "decision": a.decision}, question,
                       "--question, --answer and --decision")
    return {
        "schema": C.SCHEMA,
        "font": {"file": os.path.abspath(font_path), "sha256": base.font.sha256},
        "source": source,
        "license": {"id": C.LICENCE_ID, "file": os.path.abspath(lic_path), "sha256": base.licence.sha256,
                    "name_id_13": base.name_id_13, "reserved_font_names": base.reserved_font_names},
        "approval": {"question": a.question, "answer": answer, "decision": a.decision,
                     "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shortlist", help="shortlist.json from find_foundation.py")
    ap.add_argument("--family", help="with --shortlist: the family the person approved")
    ap.add_argument("--font")
    ap.add_argument("--licence", help="the base's OFL.txt")
    ap.add_argument("--source", choices=SOURCES)
    ap.add_argument("--url")
    ap.add_argument("--manifest-entry")
    ap.add_argument("--question-only", action="store_true",
                    help="check the files, print the approval question and write nothing")
    ap.add_argument("--question", help="the question the person saw, verbatim (the one --question-only printed)")
    ap.add_argument("--answer", help="the person's answer, verbatim")
    ap.add_argument("--decision", help='"approved" when the person approved this base; anything else writes nothing')
    ap.add_argument("--font-sha256", help="the font sha256 the question named")
    ap.add_argument("--license-sha256", help="the licence sha256 the question named")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = C.Files()
    made = build(a, files)
    if a.question_only:
        print(made)  # the question, and nothing else, so it can be passed back verbatim
        return
    rec = made
    _, wrote = C.write_base(files, a.out, rec)
    lic = rec["license"]
    print(f"{'wrote' if wrote else 'unchanged, already records this approval:'} {a.out}")
    print(f"  base    {os.path.basename(rec['font']['file'])} sha256 {rec['font']['sha256']}")
    print(f"  licence {lic['id']}, {os.path.basename(lic['file'])} sha256 {lic['sha256']}")
    print(f"  Reserved Font Names: {', '.join(lic['reserved_font_names']) or 'none'}")
    print(f"  answer  {rec['approval']['answer']!r}")


if __name__ == "__main__":
    main()
