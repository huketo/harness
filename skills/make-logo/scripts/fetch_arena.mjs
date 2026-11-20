// Pulls logo references from a public Are.na channel for measuring (references/sources.md). Plain HTTP to the v3 API
// as a guest: no package, no token. They set proportions only: never trace, ship, show or commit them.
//
//   node fetch_arena.mjs <channel slug or URL | --default> <collection name> [max=100]
//
// The images go to ${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/<collection name>/, outside the project, and its
// manifest.json lists every file with its sha256 (collection.mjs). A file already there is kept while it has the sha256
// the manifest recorded for it with its image URL, and downloaded again otherwise; each file is written whole (`.part`,
// then renamed), and the manifest last. A collection that is a symbolic link, or holds one, is refused before anything
// is asked for. --default pulls from the channels below, split evenly. Guests get 30 API requests a minute; a run of
// 100 is a few requests plus the image downloads. The CDN refuses a request with no User-Agent.
import {mkdir} from 'node:fs/promises';
import {extname, join, posix} from 'node:path';

import {collectionDir, keepOrFetch, recorded, refuseLinks, writeManifest} from './collection.mjs';

/** Public channels of flat logos, checked 2026-11-15. Any channel the person names works too. */
const DEFAULT = ['logotype-logomark', 'marks-monograms-symbols', 'design-logomark-wordmark-symbol', 'gd-logos-marks-symbols'];

const [, , arg, name = 'arena', maxArg = '100'] = process.argv;
if (!arg) {
  console.error('Usage: node fetch_arena.mjs <channel slug or URL | --default> <collection name> [max=100]');
  process.exit(1);
}
const out = collectionDir(name);
await refuseLinks(out);
const max = Number(maxArg);
const H = {'User-Agent': 'make-logo/0.1', ...(process.env.ARENA_TOKEN && {Authorization: `Bearer ${process.env.ARENA_TOKEN}`})};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function get(url, tries = 4) {
  const r = await fetch(url, {headers: H});
  if (r.status === 429 && tries) {
    await sleep((Number(r.headers.get('retry-after')) || 20) * 1000);
    return get(url, tries - 1);
  }
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r;
}

async function pull(slug, n, items, known) {
  const dir = join(out, slug);
  await mkdir(dir, {recursive: true});
  let got = 0;
  for (let page = 1; got < n; page++) {
    const {data, meta} = await (await get(`https://api.are.na/v3/channels/${slug}/contents?per=100&page=${page}`)).json();
    for (const b of data) {
      if (got >= n || b.type !== 'Image' || !b.image?.src) continue;
      const file = posix.join(slug, `${b.id}${extname(new URL(b.image.src).pathname) || '.img'}`);
      // One image that fails to download is skipped, not the whole pull.
      let sha;
      try {
        sha = await keepOrFetch(out, file, known, async () => Buffer.from(await (await get(b.image.src)).arrayBuffer()), b.image.src);
      } catch (e) {
        console.warn(`skipped ${b.id}: ${e.message}`);
        continue;
      }
      items.push({id: b.id, channel: slug, file, image_url: b.image.src, source_url: b.source?.url ?? null, uploader: b.user?.slug ?? null,
        arena_url: `https://www.are.na/block/${b.id}`, sha256: sha});
      got++;
    }
    if (!meta?.has_more_pages) break;
  }
  return got;
}

const slugs = arg === '--default' ? DEFAULT : [arg.replace(/\/+$/, '').split('/').pop()];
const items = [];
const known = await recorded(out, 'image_url');
for (const [k, slug] of slugs.entries()) {
  const share = Math.ceil((max - items.length) / (slugs.length - k));
  console.log(`${slug}: ${await pull(slug, share, items, known)} images`);
}
const all = await writeManifest(out, items, {fetched: new Date().toISOString()});
console.log(`${items.length} images pulled, ${all.length} in ${out} with their sha256 in manifest.json. They are for ` +
  'measuring only: never trace, ship, show beside the output, or commit them.');
