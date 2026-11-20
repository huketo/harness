# Licensing and naming

The output is a Modified Version of the base under the SIL Open Font License 1.1. The OFL allows that, with
conditions this skill keeps.

## What the OFL requires

- The licence travels with the fonts. `package.py` copies the base's `OFL.txt` byte for byte and adds one
  copyright line for the modifications at the top.
- The original copyright notice stays. Name ID 0 keeps the base's line, with ours under it.
- A Reserved Font Name may not be used by a Modified Version. The RFN is declared on a copyright line of the
  base's OFL.txt or name ID 0 (`with Reserved Font Name "X"`, or `Names "X" and "Y"`, quoted or not).
  `fontlib.reserved_font_names` reads only lines that start with Copyright, from that phrase to the end of its
  sentence; the OFL's own definition of the term is not a name. `package.py` refuses a family name that
  contains one.
- The fonts may not be sold on their own. They may be bundled, embedded and sold as part of a larger work.

## The base and its record

The base is an OFL-1.1 font, and the person says so. `record_base.py` writes `base.json` once, after they
answer: the font's and the `OFL.txt`'s sha256, name ID 13 exactly, the Reserved Font Names, where the font came
from (a Google Fonts URL, a pinned manifest entry, or a local file), and the question and answer verbatim. It
refuses an OFL text that is not the OFL 1.1 and a name ID 13 without the OFL notice. Every step that writes a
font checks the hashes first, and `FONTLOG.txt` repeats the record under Provenance, file names without folders.

## What this skill adds

- **A new family name**, chosen by the person, that contains neither the base's family name nor any word from
  it other than generic ones (Serif, Sans, Mono, Display, Text). Even without an RFN, keeping the base's name
  would misstate who made the modified font.
- **No trademark record.** Name ID 7 names the base's trademark. It is dropped, since the new name does not use
  the mark.
- **No base name outside the copyright line.** `check_font.py` scans every name record and the bytes of every
  other table, in ASCII and UTF-16.
- **No reference name anywhere.** The references are fonts the person likes, often commercial. Their names stay
  out of the font, FONTLOG, README and font book. The FONTLOG says "fitted to measurements of typefaces the
  requester chose".
- **Name IDs 13 and 14** carry the OFL notice and `https://openfontlicense.org`.
- **Vendor ID** is `--vendor`, four characters, or NONE.

## Name table, as written

| ID | Value |
|-|-|
| 0 | base copyright line, then `Copyright <year> <holder> (modifications)` |
| 1, 2 | family and style (non-RIBBI styles: `Family Medium`, `Regular`) |
| 3 | `<version>;<vendor>;<PostScript name>` |
| 4 | `Family Style` |
| 5 | `Version x.xxx` |
| 6 | PostScript name, letters and digits only |
| 8 | holder |
| 9 | modifier (modifications); the base's designers are credited in FONTLOG.txt |
| 11 | `--url`, if given |
| 13, 14 | OFL notice and URL |
| 16, 17 | typographic family and style |

Stylistic-set names (IDs referenced from GSUB) are kept. The base's names are read from its English record
(Windows 0x409 first), so a record in another language never stands in for it.

## Refusals

- A base without the OFL-1.1, Apache-2.0 included: not a base. Such a font is fine to measure as a reference.
- A request to keep or echo a commercial font's name ("call it X Neue"): refuse, offer a new name.
- A request to ship the reference's file, or a font made by editing it: refuse.

## FONTLOG.txt

Plain text: what the font is, the base and its axes, each modification with its numbers (y and x locations,
factors, width error per class, side moves, track, guard pairs), acknowledgements with the base's designers,
and the provenance record from `base.json`, the approval in the requester's own words included. Ask the approval
question without a reference's name, since the FONTLOG quotes it.

## Packaging against the chain

`package.py` takes `--base-json`, `--fit-log` and one or more `--space-log` files, and packages only fonts that a
space log lists as outputs, from fits the fit log lists. It writes the package to a temporary folder beside
`--out-dir`, checks each TTF against the subset's glyph order and character map and against its spaced font's
outlines and advances, and each WOFF2 against its TTF, then moves the folder into place. A non-empty `--out-dir`
is refused unless `--replace` is given. `package-log.json`, beside `--out-dir` unless `--log` says otherwise,
lists the spaced fonts as inputs and the packaged files as outputs. The README's CSS example falls back to
`sans-serif`, `serif` or `monospace` from `targets.json`'s category.
