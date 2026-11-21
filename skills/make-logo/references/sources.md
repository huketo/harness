# Sources

Every image here sets proportions or fills a mockup. None is ever traced: `trace_ref.py` takes only a file the person
holds rights in, listed in `brief.json` `trace_sources` (SKILL.md step 6), and refuses any file whose sha256 a
collection manifest lists, whose mask looks like one of these, or that is a collected one saved again, resized or
cut a little (`collected-copy`; `building.md`, "Same picture").

## The person's references

Normalise the logos they like into `refs/mine/` as image files, raster or SVG (their own drawings go in
`sketches/`):

- files they upload: copy them in;
- image URLs: download with a User-Agent header;
- a site: open it, screenshot the header and crop to the logo, or take its inline SVG, `og:image` or icon;
- an Are.na channel or block URL: `scripts/fetch_arena.mjs` takes the channel's slug or URL.

## Where collections live

`fetch_arena.mjs` and `fetch_photos.mjs` take a collection name, not a path, and write to
`${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/<name>/`, outside any project; `fonts` and `potrace` are taken by the
caches beside them. Each collection's `manifest.json` lists every file in its folder with its sha256
(`collection.mjs`): this pull's items, earlier pulls' items still on disk, and any other file found there. A file
already in the folder is kept while the manifest records it with that sha256 and with its origin (a photo's source,
an Are.na image's URL), and downloaded again otherwise: a file replaced by hand and listed by `collection.mjs` has no
origin, so the next pull fetches it again rather than credit it. Each file is written whole (as `<file>.part`, then
renamed), and the manifest last. A file keeps its details (a photo's creator, licence and source) only while its
bytes are the ones they were recorded for. A collection must be plain folders and files in the cache: a pull and
`collection.mjs` refuse one that is, or holds, a symbolic link.

`trace_ref.py` reads every collection under that folder. It refuses while a collection is or holds a symbolic link
(`collection-linked`), while a collection holds a file its manifest does not list (`collection-unlisted`: a pull that
stopped before it rewrote the manifest left its files or a `.part`, or a file was put there by hand), and while a
listed file is gone or no longer has its sha256 (`collection-changed`).
`node scripts/collection.mjs <name>` clears what a stopped pull left and rewrites the manifest from what the folder
holds, with no download; a file changed by hand is listed with its sha256 and no details.

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
