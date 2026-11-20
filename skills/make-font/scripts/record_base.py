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
files. Run 1 checks the files and prints the question, which names the font's and the OFL text's sha256, and
writes nothing. Run 2 writes base.json only when both files still have the sha256 values the question named,
the question passed in names them, and --decision is "approved". The answer is kept word for word and never
read for a yes; a person who declines gets no base.json.

Both runs refuse a base this skill cannot build on (chain.read_base, the same check every later step runs): a
file that is not a plain TrueType variable font (WOFF, WOFF2, CFF, static and collections are refused), an OFL
text that is not the SIL Open Font License 1.1 word for word, or a name ID 13 that does not name the OFL 1.1
alone. base.json holds the font's and the licence's sha256, name ID 13 exactly, the Reserved Font Names from the
OFL's copyright lines, where the font came from, and the question, answer and decision. It is written once: a
second run with the same record leaves it as it is, any other content is refused. fit_font.py, space_font.py,
package.py and check_font.py all start from it.
"""
import argparse
import datetime
import json
import os
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain as C  # noqa: E402

SOURCES = ("google-fonts", "manifest", "local")


def from_shortlist(path, family):
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["rows"]
    row = next((r for r in rows if r["family"].lower() == family.lower()), None)
    if row is None:
        raise C.Refused(f"{family!r} is not in {path}: {', '.join(r['family'] for r in rows)}")
    if not row.get("licence_path"):
        raise C.Refused(f"{family!r} in {path} has no OFL text beside it; pass --font and --licence")
    kind = "google-fonts" if str(row.get("origin", "")).startswith("google/fonts/") else "local"
    return row["file"], row["licence_path"], kind, row.get("url")


def question(font_path, lic_path, kind, url, manifest_entry, files):
    """The approval question, with the sha256 of both files, so the answer belongs to these exact bytes."""
    where = {"google-fonts": f"from Google Fonts ({url})", "manifest": f"from the pinned manifest entry {manifest_entry}",
             "local": "a file you supplied"}[kind]
    rfn = files["reserved_font_names"]
    rfn = (f"Its Reserved Font Names, which the new name may not use: {', '.join(rfn)}." if rfn
           else "It declares no Reserved Font Name.")
    return (f"May I build the new font on {files['family']}, {where}? The font file is {os.path.basename(font_path)}, "
            f"sha256 {files['font_sha256']}. Its licence is the SIL Open Font License 1.1, "
            f"{os.path.basename(lic_path)}, sha256 {files['license_sha256']}. {rfn} The new font stays under the OFL "
            "1.1 with a new name. Only these exact files are approved; a changed file needs a new question.")


def build(a):
    font_path, lic_path, kind, url = a.font, a.licence, a.source, a.url
    if a.shortlist:
        if not a.family:
            raise C.Refused("--shortlist needs --family, the name of the row the person approved")
        font_path, lic_path, kind, url = from_shortlist(a.shortlist, a.family)
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
    files = C.read_base(font_path, lic_path)
    if a.question_only:
        return question(font_path, lic_path, kind, url, a.manifest_entry, files)
    asked = {"font": a.font_sha256, "licence": a.license_sha256}
    if not all(asked.values()):
        raise C.Refused("--font-sha256 and --license-sha256 are required: the two sha256 values the question "
                        "named. Ask with --question-only first.")
    for what, now in (("font", files["font_sha256"]), ("licence", files["license_sha256"])):
        if asked[what] != now:
            raise C.Refused(f"the {what} has sha256 {now} now, but the question named {asked[what]}. It changed "
                            "while the question waited, so the answer is not about this file. Ask again with "
                            "--question-only.")
    question_, answer = a.question or "", a.answer or ""
    if not question_.strip() or not answer.strip():
        raise C.Refused("--question and --answer are both required, verbatim: the approval is the person's, "
                        "and base.json keeps their words")
    C.require_approval({"question": question_, "answer": answer, "decision": a.decision},
                       files["font_sha256"], files["license_sha256"], "--question, --answer and --decision")
    return {
        "schema": C.SCHEMA,
        "font": {"file": os.path.abspath(font_path), "sha256": files["font_sha256"]},
        "source": {"kind": kind, "url": url if kind != "local" else None,
                   "manifest_entry": a.manifest_entry if kind == "manifest" else None},
        "license": {"id": C.LICENCE_ID, "file": os.path.abspath(lic_path), "sha256": files["license_sha256"],
                    "name_id_13": files["name_id_13"], "reserved_font_names": files["reserved_font_names"]},
        "approval": {"question": question_, "answer": answer, "decision": a.decision,
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
    made = build(a)
    if a.question_only:
        print(made)  # the question, and nothing else, so it can be passed back verbatim
        return
    rec = made
    _, wrote = C.write_base(a.out, rec)
    lic = rec["license"]
    print(f"{'wrote' if wrote else 'unchanged, already records this approval:'} {a.out}")
    print(f"  base    {os.path.basename(rec['font']['file'])} sha256 {rec['font']['sha256']}")
    print(f"  licence {lic['id']}, {os.path.basename(lic['file'])} sha256 {lic['sha256']}")
    print(f"  Reserved Font Names: {', '.join(lic['reserved_font_names']) or 'none'}")
    print(f"  answer  {rec['approval']['answer']!r}")


if __name__ == "__main__":
    main()
