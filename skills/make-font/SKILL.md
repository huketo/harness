---
name: make-font
description: Use when someone wants their own font made from fonts they like, such as "make me a font like these", "/make-font" or "build a typeface from these screenshots". It measures the references, fits the closest OFL variable font to them, checks it, and delivers an OFL font with web files and a font book. It never copies outlines.
metadata:
  summary: Makes your own font
---

# Make a font

The person names fonts they like. This skill measures them, the person approves one OFL-1.1 variable font as the
base, and the skill bends that base to the measured numbers. Every outline in the result comes from the open
base. The references give numbers only: proportions, stem and stroke thickness, class-mean widths and spacing.
The output ships under the OFL with a new family name.

## The line it holds

Say this to the person at the start, in plain words: "I match proportions, widths and spacing on an open font.
I don't trace or copy the outlines of the fonts you send." Then hold it.

- Never open a reference font in the build step. `fit_font.py` and `space_font.py` read only the base font and
  `targets.json`, and their logs prove it: that structure, not an outline comparison, is the provenance guarantee.
- Never take a per-glyph advance, a kerning pair or a point from a reference. Targets are font-wide numbers and
  class means.
- Refuse a request to clone, trace, convert or "rebuild exactly" a commercial font, or to rename one. Offer the
  proportional match instead.
- A screenshot of a commercial font is fine to measure. Its file is fine to measure if the person has it. Neither
  is copied into the output or committed anywhere.
- The right to build on the base is the person's statement, not something code can prove. `record_base.py` binds
  their words to the base's and the licence's sha256 in `base.json`, every build step checks those hashes, and
  `FONTLOG.txt`, `check-report.json` and the font book print the statement as given.
- The chain proves that the files agree with each other and with the approved base, not who wrote them. Each
  step reads every file once, so what it checked is what it uses, and refuses an output path that leads to a file
  it read, through a link or not. Package and check remake the fit's subset from the base instead of trusting a
  file, but an agent that hand-writes the fonts and every log consistently is not stopped by code. Run every step
  with its script, and never edit a log.

The base is one TrueType (glyf) variable font in a plain `.ttf` file under the SIL Open Font License 1.1: its
`OFL.txt` is copyright lines in the supported form, then the licence word for word, and its name ID 13 is the
grant ("This Font Software is licensed under the SIL Open Font License, Version 1.1") followed only by the
sentences published fonts add to it. The check reads forms, not terms: a licence file with any other line, a
copyright line or notice with a clause of its own, and Apache-2.0, static, CFF, WOFF and WOFF2 fonts are not
bases (`references/licensing.md`); merging two fonts and splitting WOFF2 files are out of scope.

Scripts are in `scripts/`. Each Python script declares its own dependencies (PEP 723), so run it with
`uv run scripts/<name>.py`: uv installs Python 3.12, `fonttools`, `brotli`, `uharfbuzz`, `numpy`, `pillow` and
`skia-pathops` as that script needs them. The PDF needs Node 18+ with Playwright. Pass paths: every script reads
`--help`. Downloaded fonts go in their own folder and are only read, never run.

## Steps

1. **Ask once.** In one message ask for: the fonts they like, as font files or screenshots (two to four is
   plenty), what the font is for (text, display or UI), which scripts and languages it must cover, which weights,
   and a new family name. If they can type in the font (a foundry's type tester, a design tool), ask them to
   screenshot the four lines of `SAMPLE_LINES` in `scripts/fontlib.py`, large, cap height 80 px or more; for
   Korean, also the six lines of `SAMPLE_LINES_KO` (each syllable between two 으), in the same screenshot as the
   Latin lines when the font has Latin. Take defaults for anything unanswered and say which: text, Latin, Regular
   and Medium, a name you propose.
   Done when the references, use, scripts, weights and name are written down.

2. **Measure.** Files: `uv run scripts/measure_font.py <file> --out m1.json`. Screenshots:
   `uv run scripts/measure_image.py <shot.png> --text "line|line" --out m2.json`. Before trusting a screenshot,
   run `uv run scripts/measure_image.py --selftest <any open font> --px <its px per em>` at the screenshot's size:
   it prints how far pixel readings land from the file's numbers, for the Korean lines too. Report every number
   marked low confidence. Hangul is measured per structural class (H1 to H6), and every Hangul value carries its
   unit: `cap700` when a Latin H was measured with it, `em1000` from a file, `ratio` always. A screenshot of
   Hangul alone needs no H and gives ratios. Method, definitions and error sizes: `references/measuring.md`.
   Done when each reference has a measurement file and the person has seen the main numbers.

3. **Targets.** `uv run scripts/make_targets.py m1.json m2.json --family "New Name" --use text --scripts latin
   --style Regular:400 --style Medium:500 --out targets.json`. It records the category (sans, serif or mono;
   `--category` to set it). With Hangul, add `korean` to `--scripts` (`latin,korean`): the Hangul targets go in
   one `hangul` object, and only values of one unit are merged. No Latin number is needed; without one, the fit
   solves the weight from the Hangul stem ratio. Where references disagree, the script lists the spread. Ask which
   way to lean instead of averaging a serif with a sans.
   Done when `targets.json` exists and every spread has an answer or a stated default.

4. **Find the foundation.** `uv run scripts/find_foundation.py targets.json --cache <dir> --out shortlist.json`.
   It ranks OFL variable families from the Google Fonts catalogue by distance to the targets
   (`references/foundation.md`). Show the person the top three to five with their deltas, axes and Reserved Font
   Names, render each beside a reference if you can, recommend one, and ask which to build on.
   Done when the shortlist is shown and the question is asked.

5. **Record the approval.** Only the person approves the base. Once they pick one, print the question:
   `uv run scripts/record_base.py --shortlist shortlist.json --family "<their pick>" --question-only
   --out base.json` (a font of their own: `--font`, `--licence <its OFL.txt>` and `--source local` instead of
   `--shortlist` and `--family`). It checks the files the same way every later step will, prints a question that
   names the base, its licence and both sha256 values, and writes nothing. Ask that question as printed, never
   with a reference's name in it. When they answer, run the same command without `--question-only`, with
   `--question "<the printed question, verbatim>" --answer "<their answer, verbatim>" --font-sha256 <font hash
   from the question> --license-sha256 <licence hash from the question>`, and `--decision approved` only if they
   approved. That run makes the question again from the same arguments and writes only if the one passed is
   that question word for word. Any other decision, a file or a source URL (from the shortlist or `--url`) that
   changed since the question, or an edited question writes nothing; ask again. In an unattended run, stop after `--question-only`:
   report the shortlist and the question, and leave `base.json` unwritten.
   Done when `base.json` exists. It is written once; a different base or answer needs a new build folder.

6. **Fit.** `uv run scripts/fit_font.py <base-vf.ttf> targets.json --base-json base.json --out-dir build/
   [--loc opsz=..]`. It refuses a font that is not the approved base, subsets the base itself to the targets'
   scripts, solves a y instance for stems and contrast, an x instance per width class for widths, merges them
   into one static per weight, and iterates until every class mean is within 0.3 percent, never stretching more
   than 3 percent (`references/fitting.md`). If a class hits the stretch limit, tell the person what that letter
   class will be and offer a base with a width axis.
   Done when every style is written and `fit-log.json` shows each class within tolerance or explained.

7. **Space.** `uv run scripts/space_font.py build/X-Regular.fit.ttf targets.json --out build/X-Regular.ttf
   --base-json base.json --fit-log build/fit-log.json [--track -4]`. Class sidebearings to the targets, an optional
   global track, kerning carried and scaled, then the collision guard (`references/spacing.md`). More than 150
   guard pairs means the spacing is too tight. Loosen and rerun.
   Done when the guard count is under 150 and its log is saved.

8. **Package and check.** `uv run scripts/package.py build/*.ttf --targets targets.json --base-json base.json
   --fit-log build/fit-log.json --space-log build/*.space-log.json --holder "<who owns the modifications>"
   --out-dir dist/` (`references/licensing.md`). It checks the chain, remaking the fit's subset from the base,
   builds the package and its `package-log.json` in a private (0700) temporary folder, checks every TTF and WOFF2
   against the chain, and only then moves the folder to `dist/`. Give one spaced font per style. `dist/` must lie
   outside `build/` and hold no input, nor a link to one. Then
   `uv run scripts/check_font.py dist/ttf/*.ttf --targets targets.json --base-json base.json
   --fit-log build/fit-log.json --space-log build/*.space-log.json --package-log dist/package-log.json
   --reference <ref file> --package dist/ --out-dir checks/` (`references/checks.md`). It runs the same chain
   check as the package step, then the package log's links. Look at every overlay
   render yourself, at the text and the display size. A failed gate goes back to the step that owns it; a
   refusal means a file left the chain, so rerun from the step that wrote it.
   Done when the check exits 0, or each failure is listed for the person with its number and the reason.

9. **Font book.** `uv run scripts/font_book.py dist/ttf/*.ttf --webfonts dist/webfonts --targets targets.json
   --fit-log build/fit-log.json --space-log build/*.space-log.json --check-report checks/check-report.json
   --out-dir book/`, then `node scripts/render_book.mjs book/`. The check report is required, and every TTF and
   WOFF2 given must be a package output it lists by sha256; anything else is refused, so the provenance page,
   which prints the approved base's sha256 and the approval verbatim, belongs to the fonts the book shows. It
   prints the pages as PNG and one PDF and fails on a fallback glyph or an overflow (`references/font-book.md`).
   Open three pages and look before you hand it over.
   Done when `book/fontbook.pdf` exists and render_book.mjs exits 0.

## Hand-off

Tell the person, in this order: what was made (family, weights, glyph count, scripts), the base and its licence,
the gates with their numbers (pass, fail and not run), what still differs from the references and why (the
base's own drawing: terminals, serif shape, a letter that reads differently), and where the files are. Attach or
link the PDF. Name the fonts' provenance plainly: built on an open font they approved, fitted to measurements.

## Never

- Copy, trace, auto-trace or convert outlines from a reference. Copy a reference's kerning or per-glyph widths.
- Build on a font that is not an OFL-1.1 glyf variable font, or on one the person did not approve.
- Write or edit `base.json` or a step's log by hand, or answer the approval question for the person.
- Ship under any licence but the OFL, keep the base's name or a Reserved Font Name, or keep its trademark record.
- Put a reference font's name in the output files, the font book or the package README.
- Call a gate passed that was not run in this session. fontbakery not installed is "not run", not "passed".
- Stretch a glyph more than the limit to hit a number. Report the gap instead.
- Commit or publish font files unless the person asks, and never a reference font.

## Files

- `scripts/fontlib.py` shared geometry, Latin and Hangul classes, Hangul measures, character sets, Reserved Font
  Names, sample lines, rasteriser.
- `scripts/chain.py` `base.json` and the chain each step's log carries.
- `scripts/measure_font.py`, `measure_image.py`, `make_targets.py`: steps 2 and 3.
- `scripts/find_foundation.py`: step 4. `record_base.py`: step 5. `fit_font.py`: step 6. `space_font.py`: step 7.
- `scripts/package.py`, `check_font.py`: step 8. `font_book.py`, `book.css`, `render_book.mjs`: step 9.
- `scripts/test_*.py` gate tests on synthetic fonts (`testfonts.py`).
- `references/`: measuring, foundation, fitting, spacing, checks, licensing, font-book.
