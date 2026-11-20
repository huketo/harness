# Sources

Every image here sets proportions or fills a mockup. None is ever traced: `trace_ref.py` takes only a file the person
holds rights in, listed in `brief.json` `trace_sources` (SKILL.md step 6), and refuses any file whose sha256 a
collection manifest lists or whose mask looks like one of these.

## The person's references

Normalise the logos they like into `refs/mine/` as image files (their own drawings go in `sketches/`):

- files they upload: copy them in;
- image URLs: download with a User-Agent header;
- a site: open it, screenshot the header and crop to the logo, or take its inline SVG, `og:image` or icon;
- an Are.na channel or block URL: `scripts/fetch_arena.mjs` takes the channel's slug or URL.

## Where collections live

`fetch_arena.mjs` and `fetch_photos.mjs` take a collection name, not a path, and write to
`${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/<name>/`, outside any project. Each collection's `manifest.json` lists
every file in its folder with its sha256 (`collection.mjs`): this pull's items, earlier pulls' items still on disk,
and any other file found there. A file already in the folder is hashed, not downloaded again. `trace_ref.py` reads
every manifest under that folder.

## Are.na

`fetch_arena.mjs` uses the public v3 API as a guest: no account, no token, no package.

- `node scripts/fetch_arena.mjs <slug | --default> <collection name> [max=100]`; the API underneath is
  `GET https://api.are.na/v3/channels/<slug>/contents?per=100&page=N`. Pages of up to 100; `meta.has_more_pages`.
- The original image is `image.src` on Are.na's CDN. A request without a User-Agent gets a bot challenge, not the file.
- Guests get 30 API requests a minute (free accounts 120). A pull of 100 is a few API requests plus the downloads.
- Search on v3 is Premium only. The older v2 channel search still answers guests:
  `GET https://api.are.na/v2/search/channels?q=<words>&per=20` returns channels with their slugs and block counts, and
  `fetch_arena.mjs` pulls any of them by slug. The script also ships a short list of public logo channels
  (`--default`). Set `ARENA_TOKEN` to use the person's account.
- The official CLI (`arena download`) and Are.na's hosted MCP work too for someone already signed in.

## What the images are

People upload logos they found; the brands own them, not Are.na and not the uploader. Are.na's terms let it limit
bulk use. So:

- pull on the person's request, about 100 a run, from channels they chose or the defaults;
- keep them in the cache for measuring, and never trace, ship, commit, redistribute or show them beside the output;
- keep `manifest.json` (block, source, uploader, sha256) so every image's origin is known and no copy of it can be
  traced;
- never name a reference's brand anywhere.
