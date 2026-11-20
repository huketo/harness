---
name: make-logo
description: Use when someone wants a logo, mark or wordmark for their product, such as "make me a logo", "/make-logo" or "a logo like these but ours". It learns proportions from logos they like and from Are.na, builds original marks from shapes and open fonts, traces only drawings the person holds rights in, sets wordmarks in display fonts, and delivers a logo book of six directions.
metadata:
  summary: Makes your own logo
---

# Make a logo

The person tells you what their product is and shows logos they like. This skill measures those references and a
wider set from Are.na, turns them into numbers, and builds an original mark to those numbers from parts it is free to
use. Every variant is checked against every reference before anyone sees it.

## The line it holds

Say this at the start, in plain words: "The logos you like and the ones I pull from Are.na set proportions only; I
never trace them. If you have a drawing or a brand of your own, I can trace it, once you tell me it's yours." Then
keep to it.

- Outlines come from four places, each kept with its source (`references/building.md`): shapes on a grid, OFL fonts
  set and outlined, permissive icon sets, and a trace of a file the person holds rights in (their own drawing, their
  own brand, or material licensed to them).
- Reference logos, Are.na pulls and stock photos are for measuring and mockups only (the owner's decision,
  2026-11-20). The scripts refuse to trace them, however they are renamed, re-saved or cropped.
- Refuse "recreate X's logo" or any famous brand named as the target.
- Nothing here is a legal clearance. Say so, and give the trademark search sheet.

## What the code holds, and what it can't

Rights are the person's statement. The code binds that statement to the hash of the file it is about, refuses a
result that sits close to any other reference, and prints the statement, word for word, in the book and the
trademark sheet. It doesn't know whether the statement is true.

- `trace_ref.py` traces only a file listed in `brief.json` `trace_sources` by sha256, never one whose sha256 is in a
  collection manifest, and never when the exact mask passed to potrace, or potrace's path rendered, reaches the
  calibrated limit against a collected image or a `--refs` logo. It compares with every image, fit to measure or
  not: SVGs rasterised, a favicon too small to split enlarged, an image with transparency seen on white and on black
  (its higher score counts). It refuses while one of them still can't be read as one mark (`not-comparable`, also a
  sheet whose mask leaves out a tenth of the ink seen on a ground), while a `--refs` folder or file named is not
  there, a folder in them can't be listed or is a link to a folder, or an image is a broken link (`refs-missing`), while a collection is or
  holds a symbolic link (`collection-linked`), while a collection holds a file its manifest does not list
  (`collection-unlisted`: a pull that stopped, or a file put there by hand), or while a collected file is gone or no
  longer has the sha256 its manifest lists (`collection-changed`). The person's
  own sketch on the moodboard (same sha256 as a `trace_sources` entry) is left out of that comparison; a collected
  file never is. Each trace gets `<svg>.provenance.json`.
- `build_logo.py` trusts no trace SVG: it checks the provenance, traces the source again with the same gates against
  today's collections and references, goes on only while the record's raster arguments give back the mask it
  recorded, and refuses a recipe that says `traced_from`. `check_logo.py` compares with the same references, refuses
  the same unreadable ones, and leaves out only a direction's own verified source; every other reference keeps the
  usual limit. It refuses a traced direction whose trace was gated against other `--refs` images, another
  calibration or other collections than it is given, and removes that `check.json`.
- `package_logo.py` and `logo_book.py` go on only while `check.json` passed and the sha256 of `build.json`, of every
  file it lists, of the `--refs` images and of the calibration all match what `check_logo.py` saw; for a traced
  direction, its source and the collections (`collected_sha256`) must match too. They verify all of it before they
  write anything, and read the build's files only as those verified bytes. A `build.json` that leaves out a part the
  build writes (the mark, its grid, the lockups of a build with a wordmark) is refused at every step.
- A shape the agent types in as `polygon` points has no source the chain can see: only the distance check stands
  between it and a copy.
- A reference sheet that holds a second mark too small to survive segmentation (a badge of a few pixels beside a
  large mark) is compared as the large mark alone; the tenth-of-the-ink rule above does not see specks. Crop every
  reference to one mark before it goes in `refs/` (step 3), and drop sheets of several marks.

## Decisions only the person makes

Two answers come from the person, never from you: whether they hold the rights to a file you would trace, and which
direction they choose. Ask each as a plain question, show the file or the book, and record the question and their
answer verbatim (`trace_sources` in step 6, `choice` in step 9). In an unattended run, stop before each of these
steps and report what you would ask; trace nothing and package nothing until a person has answered.

## Setup

Python scripts carry their dependencies (PEP 723): run each with `uv run scripts/<name>.py` (tested with Python
3.12). Tracing needs potrace: the one on `PATH`, else, on linux-x86_64, `trace_ref.py` fetches the pinned 1.16 build
from potrace's site into the cache after checking its sha256; elsewhere it prints the install command
(`brew install potrace`, `apt install potrace`). Node 18+ runs the Are.na and photo pulls, and Playwright with a
Chromium prints the book (`render_book.mjs` finds it through awesome-interface's `find-chromium.mjs` when that skill
is installed beside this one).

Collected images live outside the project, in `C=${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo`, one folder per
collection, each with a `manifest.json` listing every file and its sha256. Nothing collected is ever committed or
shipped. Below, `<refs>` stands for every reference folder, always the same list: `refs/mine/ "$C/arena/" "$C/world/"`.

## Steps

1. **Ask once.** In one message: the name, what it does and for whom, one idea the mark could carry (a letter, an
   object, a motion, a word), 3 to 6 logos they like (files, image URLs, sites, an Are.na channel), whether they have
   a drawing, sketch or brand of their own to build from, where it will live (an app icon, a site, print), colour
   limits, and mark, wordmark or both. Defaults: both, one colour, the app icon. Write the documents in the brief's
   language; a brief in Korean gets Korean documents (`"language": "ko"`).
   Done when `brief.json` holds the answers and the defaults you took.

2. **Gather.** Put the person's references in `refs/mine/` (a site: screenshot its header and crop the logo), and
   their own drawings, if any, in `sketches/`. Pull a wider set: `node scripts/fetch_arena.mjs --default arena 100`,
   or a channel they name (`references/sources.md`). Then pull one set from the product's own world: search Are.na's
   channels (`https://api.are.na/v2/search/channels?q=architecture%20identity`) for its field plus "logo" or
   "identity", and fetch the two or three with the most blocks into one collection:
   `node scripts/fetch_arena.mjs <slug> world 40`. The general set gives craft; this one gives pictures that fit the
   idea. Run the distance check (step 8) against logo references only: photos of books, rooms or products match any
   plain mark by silhouette and say nothing about copying. Last, the photos for the book's mockups:
   `node scripts/fetch_photos.mjs "<one or two mood words>" photos 6` (free CC0 and CC BY stock from Openverse, into
   `$C/photos/`; `references/logo-book.md`). Look at them and delete any that don't fit. Every collection is in
   place before anything is traced: a trace is gated against all of them, and a later pull or deletion stops a traced
   direction's book and package until it is built and checked again. After deleting or replacing a collected file by
   hand, or after a pull that stopped (`collection-unlisted`), `node scripts/collection.mjs <name>` lists what the
   collection holds now.
   Done when `refs/mine/` holds the person's references and `$C/arena/`, `$C/world/` and `$C/photos/` each hold a
   `manifest.json` listing every file there with its sha256.

3. **Measure.** `uv run scripts/measure_logo.py <refs> --out measurements.json --sheet measured.png`. Open the sheet
   and look: every mask should be the mark and nothing else. Drop any that caught a photo, a caption or a sheet of
   several marks (`references/measuring.md`). Tracing and checking refuse one whose mask leaves part of the ink out,
   but not two marks the mask keeps together, nor a small mark beside a larger one on the same ground: drop those.
   Done when the measured set is clean and the person's own references are in it.

4. **Calibrate.** With 30 or more measured references: `uv run scripts/calibrate.py measurements.json --out
   calibration.json`. With fewer, use the shipped `scripts/calibration.json` (`references/distance.md`), and pass the
   same file as `--calibration` to every later step.
   Done when the limit is set and the weakest edit it catches is reported.

5. **Targets.** Take the person's references' numbers as the target, with the Are.na set's spread as the range.
   Where their references disagree, ask which way to lean.
   Done when `targets.json` holds the numbers and the leanings.

6. **Rights, for each file to trace.** Only a file from the person themselves can be traced. Show it and ask, for
   example, "Is this your own drawing (or your brand, or licensed to you), so I may trace it into your mark?" Record
   their reply in `brief.json`:
   `"trace_sources": [{"file": "sketches/l.png", "sha256": "<from sha256sum or shasum -a 256>", "rights": "own-drawing",
   "question": "<the question, verbatim>", "answer": "<their answer, verbatim>"}]`, with `rights` one of
   `own-drawing`, `own-brand`, `licensed`. A file changed after they answered needs a new answer.
   Done when every file you will trace has an entry in their own words, or the directions use no trace.

7. **Directions.** Write six directions from the idea, each a different answer, not six takes on one shape. Mix the
   kinds (`references/building.md`): idea marks built from shapes, typographic marks in a display face with
   character, and, when step 6 gave you a source, traced marks: `uv run scripts/trace_ref.py sketches/l.png --brief
   brief.json --refs <refs> --calibration calibration.json --crop x,y,w,h --out trace/<n>.svg`, then change one thing
   with recipe shapes so it carries the idea. A refusal means the picture is another logo or a collected image:
   drop that source, never work around it. `not-comparable` names a reference the gates can't read as one mark: take
   it out of `refs/mine/` (or delete it from its collection and run `collection.mjs`), or replace it with one mark
   cropped out of it on a plain ground, then trace again. At least half carry the idea as a picture, not a letter. Each
   is a recipe (`references/building.md`): a title, the idea in one sentence, grid shapes, an OFL wordmark, a
   palette. Build each: `uv run scripts/build_logo.py dirs/<n>.json --out build/<n> --brief brief.json --refs <refs>
   --calibration calibration.json`. Render all six on one sheet and look: a mark that reads as a stock icon, the
   wrong letter, or a random pictogram gets rewritten, not kept.
   Done when six directions build, each reads as its idea at 64 px, and no two are the same move.

8. **Check.** `uv run scripts/check_logo.py build/* --refs <refs> --calibration calibration.json`: stroke at 16 px,
   counters at 16 px, palette contrast, nearest reference. A direction that is too close: open the three nearest
   beside it, look, change the recipe, build again. A traced direction is held to the limit against every reference
   but its own source; its score against that source is recorded and shown, never failed. A detailed trace may fail
   the 16 px checks; keep it if it's strong, and say it needs a simpler favicon. A `trace-gate-stale` refusal means
   the references, the calibration or the collections changed after that direction was built (a new photo pull
   counts): build it again, then check it. `not-comparable` is the same as in step 7.
   Done when every direction passes, a traced one failing nothing but the 16 px rows.

9. **Logo book.** With the photos from step 2:
   `uv run scripts/logo_book.py build/* --out book --refs <refs> --calibration calibration.json --brief brief.json
   --name "<name>" --line "<what it does>" --tagline "<...>" --note "<a notification the app would send>" --photos
   "$C/photos"`, then `node scripts/render_book.mjs book` (`references/logo-book.md`). A direction that failed the
   check is left out; `--include-failed` shows it, marked. This step and step 10 refuse a traced direction whose
   collections changed after its check (`collections-changed`): build and check it again. Open every page. Send
   `book/logobook.pdf` and ask the person to choose; record the question and their answer verbatim in `brief.json`
   as `"choice"`.
   Done when render_book.mjs exits 0 and the person's pick is recorded in their words.

10. **Package.** `uv run scripts/package_logo.py build/<chosen> --out package --refs <refs> --calibration
    calibration.json --brief brief.json --classes "<Nice classes>"`, into a new folder: SVGs (mark, wordmark,
    lockups; ink, reversed, accent, black), PNGs from 16 to 1024 px, favicon.ico, LICENSES, and the trademark search
    sheet, with KIPRIS for Korea and, for a traced mark, the person's statement word for word. For a reveal video,
    hand the mark and its guides to make-motion.

## Never

- Trace a reference logo, an Are.na image, a stock photo, or a famous brand the person names, or any file without
  the person's own answer in `trace_sources`.
- Answer the rights question or pick the direction for the person, or reword their answer.
- Edit a trace SVG, `build.json` or `check.json` by hand; change the recipe and run the steps again.
- Name a reference's brand in any output file, sheet or message.
- Call a variant cleared. Passing the distance check means it isn't a near copy of these references, nothing more.
- Use Remix Icon (its licence bans logos) or any brand-icon set.

## Files

- `scripts/fetch_arena.mjs`, `scripts/fetch_photos.mjs`, `scripts/collection.mjs`: step 2, into the cache.
- `scripts/logolib.py`: loading, finding the ink, normalising. `scripts/rights.py`: hashes, the brief's
  `trace_sources`, collection manifests, and the seal between steps.
- `scripts/measure_logo.py`: step 3. `scripts/calibrate.py`: step 4. `scripts/distance.py`: the distance check.
- `scripts/trace_ref.py` (with `scripts/potrace_bin.py`), `scripts/build_logo.py`, `scripts/fonts.py`: step 7.
  `scripts/check_logo.py`: step 8.
- `scripts/logo_book.py`, `scripts/render_book.mjs`: step 9. `scripts/package_logo.py`: step 10.
- `scripts/calibration.json`: default weights and limit, fitted on 98 references.
- `scripts/test_*.py`: the gate tests (`mise run test-logo-gates`), on synthetic images and fonts.
- `references/`: sources, measuring, distance, building, logo-book.
