# Fonts

Korean typography uses four roles, each filled by one pinned family. `tools/fonts.json` is the single source for URLs, versions, and sha256 hashes; this file is the judgment behind it.

| Role | CSS family | Default | Alternatives in fonts.json |
| --- | --- | --- | --- |
| sans (body, UI text) | `Deck Sans` | `pretendard` 400/500/700 | `wanted-sans` 400/500/700, `paperlogy` 700/900 |
| serif (literary titles, quotes) | `Deck Serif` | `noto-serif-kr` variable 200–900 | `gowun-batang` 400/700 |
| display (large titles) | `Deck Display` | `paperlogy` 700/900 | any sans or serif family the design calls for |
| mono (code) | `Deck Mono` | `d2coding` 400/700 | — |

All seven families are SIL OFL 1.1, cover all 11,172 Hangul syllables, and allow embedding in documents, web pages, and PDF, including commercial use. Choose by the design, not the license.

## Choosing

`theme.css` names only the role families. DESIGN.md decides which family fills each role; set it in `fonts.json`'s `use`, then `npm run fonts`. In twenty questions, a type comparison is a variant that either points a role at another role's family in its `theme.css` (`--as-font-display: 'Deck Serif'`), or carries a copy of `tools/fonts.json` with a different `use`; `variants.mjs` fetches that variant's fonts for its render only.

Latin text uses the same Korean family: every default includes Latin glyphs designed to match.

## Licensing rules the tools enforce

- `fetch` stores each file as published, converting TTF to woff2 compression only, and writes every family's copyright and license text to `fonts/LICENSES.txt`; `deck.html` embeds that text.
- `subset` produces a Modified Version under OFL. It renames every subset font to its role name (`Deck Sans`, …) so no Reserved Font Name survives: Pretendard and D2Coding reserve their names; the other five reserve none.
- PDF embedding is unrestricted under OFL (FAQ 1.12).
- A font file is never offered for sale on its own.

## Adding a family

1. Confirm OFL-1.1 (or another license permitting embedding and redistribution) in the family's own repository or foundry page, and note any Reserved Font Name.
2. Download the exact files from that primary source at a tag or commit, and count Hangul coverage; a family short of 11,172 syllables falls back on rare syllables and is listed only with that caveat.
3. Add the entry to `assets/slidev/tools/fonts.json` in the skill with `roles`, `version`, `rfn`, `license.url`/`sha256`, and per-weight `url`/`sha256` (or `archive` plus `member`), then run `npm run fonts` in a test deck.
