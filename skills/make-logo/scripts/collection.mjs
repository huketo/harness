// Collections for make-logo (references/sources.md): what fetch_arena.mjs and fetch_photos.mjs collect lives in the
// cache, outside any project, at ${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/<name>/, and each collection's
// manifest.json lists every file in it with its sha256. trace_ref.py refuses any file with one of those hashes, and
// compares every trace against these images.
//
//   node collection.mjs <collection name>
//
// lists what a collection holds now, after files were deleted or replaced by hand: every file still there with its
// sha256, each keeping its earlier details (a photo's credits). Nothing is downloaded.
import {createHash} from 'node:crypto';
import {readdir, readFile, stat, writeFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {isAbsolute, join, posix, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

export function cacheRoot(env = process.env) {
  const base = env.XDG_CACHE_HOME && isAbsolute(env.XDG_CACHE_HOME) ? env.XDG_CACHE_HOME : join(homedir(), '.cache');
  return join(base, 'hstack', 'make-logo');
}

/** The folder for a collection name: one word, no path, so a pull can't land inside a project. */
export function collectionDir(name, env = process.env) {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(name ?? '')) {
    throw new Error(`collection name ${JSON.stringify(name)}: use one word (letters, digits, dot, dash, underscore); ` +
      `collections live in ${cacheRoot(env)}`);
  }
  return join(cacheRoot(env), name);
}

export const sha256 = (data) => createHash('sha256').update(data).digest('hex');

export async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

async function filesUnder(dir, prefix = '') {
  const out = [];
  for (const e of (await readdir(join(dir, prefix), {withFileTypes: true})).sort((a, b) => a.name.localeCompare(b.name))) {
    const rel = prefix ? posix.join(prefix, e.name) : e.name;
    if (e.isDirectory()) out.push(...(await filesUnder(dir, rel)));
    else if (e.isFile() && rel !== 'manifest.json' && !rel.endsWith('.part')) out.push(rel);
  }
  return out;
}

/**
 * Writes <dir>/manifest.json listing every file in the folder with its sha256: this pull's items first, in order,
 * then files from earlier pulls with their earlier details, then any other file found there. A listed file that is
 * gone is dropped.
 */
export async function writeManifest(dir, items, extra = {}) {
  let earlier = [];
  try {
    earlier = JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')).items ?? [];
  } catch {
    // no manifest yet
  }
  const known = new Map();
  for (const it of [...items, ...earlier]) if (!known.has(it.file)) known.set(it.file, it);
  const onDisk = new Set(await filesUnder(dir));
  const order = [...known.keys(), ...[...onDisk].filter((f) => !known.has(f))];
  const out = [];
  for (const file of order) {
    if (!onDisk.has(file)) continue;
    out.push({...(known.get(file) ?? {}), file, sha256: sha256(await readFile(join(dir, file)))});
  }
  await writeFile(join(dir, 'manifest.json'), JSON.stringify({...extra, items: out}, null, 2));
  return out;
}

/** Rewrites <dir>/manifest.json from the files in the folder now, keeping its other fields and each file's details. */
export async function refreshManifest(dir) {
  const fields = JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8'));
  delete fields.items; // writeManifest reads them back with their details
  return writeManifest(dir, [], fields);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [, , name] = process.argv;
  if (!name) {
    console.error('Usage: node collection.mjs <collection name>');
    process.exit(1);
  }
  const dir = collectionDir(name);
  const items = await refreshManifest(dir);
  console.log(`${items.length} files in ${dir}, each with its sha256 in manifest.json`);
}
