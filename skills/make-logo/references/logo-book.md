# Logo book

The book is how the person chooses. It presents every direction the way a studio presents logo directions: each one
in use, its construction and its colour, then all of them side by side with their checks. It shows no reference logo
and no other studio's logo; its only photographs are free ones with a credits page (see Photos).

`logo_book.py` writes `book/index.html` and `pages.json`; `render_book.mjs` prints `pages/NN-slug.png` and
`logobook.pdf` at 1600 x 900 (16:9), and exits 1 if the book's font didn't load or anything runs off a page or out of
its tile. A full render (no `--pages`) removes the page images `pages.json` no longer names, so after a book printed
with `--include-failed`, `pages/` holds the new book only.

## What goes in

`logo_book.py` takes the same `--refs` and `--calibration` as `check_logo.py` and refuses a build whose `check.json`
is missing or no longer matches `build.json`, the files it lists, the `--refs` images or the calibration, or, for a
traced direction, its source or the collections (`collections-changed`), before it writes anything. It reads a
direction's pictures only as the verified bytes of `build.json` `files`: a build with no wordmark has no lockup, and
the book draws its mark, larger, wherever a lockup would go. A direction that failed the check is left out;
`--include-failed` puts it in with "Failed a check" under its title, for a person who asked to see everything.

## Language

The book follows the brief (`--brief brief.json`, or `--lang en|ko`): the brief's `language`, else Korean when the
brief is written in Korean, else English. An English book is set in Inter Tight; a Korean one in Noto Sans KR, the
OFL Hangul family `fonts.fetch` takes from Google Fonts. The titles, ideas, `--line`, `--tagline` and `--note` are
printed as given, so write them in the same language.

## Pages

| Page | What |
|-|-|
| Cover | the product's name and "Logo directions" on ink, beside a photo (or the first mark on its colour field) |
| Directions | three marks to a page, each with its title and idea; under a traced one, its source file, the kind of right, its score against the source and the person's answer, verbatim |
| For each direction: in use | the lockup reversed on ink; a browser tab with the mark as its icon; a poster: a photo with the tagline and lockup over a dark foot (or the colour field) |
| For each direction: construction | the lockup on paper; the mark on its grid with dashed guides run edge to edge; a phone with the app icon and the `--note` notification |
| For a traced direction: where it came from | the mark beside its source file, sha256, kind of right, the question shown and the person's answer, both verbatim, and the score against the source, with a line saying make-logo recorded the statement and did not verify it |
| For each direction: colour | the five palette colours with their hex values |
| For each direction: sizes | the mark at 16, 24, 32 and 64 px with its stroke at 16 px; reversed; on colour; the stacked lockup |
| Side by side | three marks to a page, each large and at 16 px, with every check and its number, and a traced one's score against its source |
| Photos | each photo's title, creator, licence and source, when the book has photos |

No page carries a numbered label or a dot separator, and the cover carries no line about how the marks were made.

## Photos

`fetch_photos.mjs` (`node scripts/fetch_photos.mjs "<words>" photos 6`) searches Openverse for free photos, public
domain and CC BY only, StockSnap's CC0 stock first and Flickr after, and keeps each one's creator, licence and source
for the credits page. They go to the `photos` collection in the cache, each with its sha256 (`sources.md`). Pull them
while gathering (SKILL.md step 2), before anything is traced: the trace gates compare with every collection, so a
pull after a traced direction's check stops its book and package (`collections-changed`) until it is built and
checked again. Broad mood words work ("laptop office", "doctor", "architect"); specific ones return museum scans and
news photos. Look at every photo and delete any that doesn't fit, then `node scripts/collection.mjs photos` so the
manifest lists what is left. The book uses a photo only when its manifest entry names its creator, licence and
source, and only while the file still has the sha256 that entry lists; a file listed without them (one put in the
folder by hand, or one replaced by hand) is left out, and named.
Without `--photos` the cover and posters use each direction's colour field.

## Guides

The construction page draws a few clean guides, not every line in the recipe: the mark's edges, then the recipe's own
lines that sit at least an eighth of the grid from those already drawn, at most five a side.

## Words

The cover and the directions page take `--line` (what the product does). The poster takes `--tagline`. Keep both
plain and short; they're placeholders the person will rewrite.
