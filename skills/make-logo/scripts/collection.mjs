// Collections for make-logo (references/sources.md): what fetch_arena.mjs and fetch_photos.mjs collect lives in the
// cache, outside any project, at ${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/<name>/, and each collection's
// manifest.json lists every file in it with its sha256. trace_ref.py refuses any file with one of those hashes, and
// compares every trace against these images.
//
//   node collection.mjs <collection name>
//
// lists what a collection holds now, after files were deleted or replaced by hand: every file still there with its
// sha256. A file keeps its earlier details (a photo's credits) only while its bytes are the ones they were recorded
// for. It also clears what a pull that stopped left behind (`*.part`). Nothing is downloaded.
import {createHash} from 'node:crypto';
import {readdir, readFile, rename, rm, stat, writeFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {isAbsolute, join, posix, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

/** The caches beside the collections (fonts.py, potrace_bin.py); rights.py never reads these as collections. */
const TAKEN = new Set(['fonts', 'potrace']);
/** A file being written is named this until it is whole; one left over marks a pull that stopped (rights.py refuses). */
export const PART = '.part';

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
  if (TAKEN.has(name)) throw new Error(`collection name ${JSON.stringify(name)} is taken by make-logo's ${name} cache; use another`);
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

/** Writes `data` to `path` whole or not at all: into <path>.part, then renamed over `path`. */
export async function writeAtomic(path, data) {
  await writeFile(path + PART, data);
  await rename(path + PART, path);
}

/** file -> sha256, as the collection's manifest.json lists them now; empty when it has none. */
export async function recorded(dir) {
  try {
    return new Map((JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')).items ?? []).map((it) => [it.file, it.sha256]));
  } catch {
    return new Map();
  }
}

/**
 * Puts one pulled file in the collection and returns its sha256. A file already there is kept when it still has the
 * sha256 the manifest recorded for it (`known`, from recorded()); otherwise `download()` fetches it again, and its
 * bytes are written whole. `download()` resolves to the bytes, or to null to skip the file; this then returns null.
 */
export async function keepOrFetch(dir, file, known, download) {
  const path = join(dir, file);
  if (await exists(path)) {
    const sha = sha256(await readFile(path));
    if (known.get(file) === sha) return sha;
  }
  const data = await download();
  if (!data) return null;
  await writeAtomic(path, data);
  return sha256(data);
}

async function filesUnder(dir, prefix = '') {
  const out = [];
  for (const e of (await readdir(join(dir, prefix), {withFileTypes: true})).sort((a, b) => a.name.localeCompare(b.name))) {
    const rel = prefix ? posix.join(prefix, e.name) : e.name;
    if (e.isDirectory()) out.push(...(await filesUnder(dir, rel)));
    else if (e.isFile() && rel !== 'manifest.json' && !rel.endsWith(PART)) out.push(rel);
  }
  return out;
}

async function clearParts(dir, prefix = '') {
  for (const e of await readdir(join(dir, prefix), {withFileTypes: true})) {
    const rel = prefix ? posix.join(prefix, e.name) : e.name;
    if (e.isDirectory()) await clearParts(dir, rel);
    else if (e.name.endsWith(PART)) await rm(join(dir, rel), {force: true});
  }
}

/**
 * Writes <dir>/manifest.json, whole, listing every file in the folder with its sha256: this pull's items first, in
 * order, then files from earlier pulls, then any other file found there. A file keeps the details of an item (this
 * pull's, else an earlier pull's) only when that item's sha256 is the file's sha256 now: the details describe those
 * bytes. A file changed since is listed with its sha256 alone, so the book credits none of it. A listed file that is
 * gone is dropped, and what an unfinished write left (`*.part`) is removed first.
 */
export async function writeManifest(dir, items, extra = {}) {
  let earlier = [];
  try {
    earlier = JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')).items ?? [];
  } catch {
    // no manifest yet
  }
  await clearParts(dir);
  const recordedFor = new Map();
  for (const it of [...items, ...earlier]) recordedFor.set(it.file, [...(recordedFor.get(it.file) ?? []), it]);
  const onDisk = new Set(await filesUnder(dir));
  const order = [...recordedFor.keys(), ...[...onDisk].filter((f) => !recordedFor.has(f))];
  const out = [];
  for (const file of order) {
    if (!onDisk.has(file)) continue;
    const sha = sha256(await readFile(join(dir, file)));
    const details = (recordedFor.get(file) ?? []).find((it) => it.sha256 === sha) ?? {};
    out.push({...details, file, sha256: sha});
  }
  await writeAtomic(join(dir, 'manifest.json'), JSON.stringify({...extra, items: out}, null, 2));
  return out;
}

/**
 * Rewrites <dir>/manifest.json from the files in the folder now, keeping its other fields and the details of each file
 * whose bytes are unchanged. A folder a first pull left with no manifest gets one.
 */
export async function refreshManifest(dir) {
  let fields = {};
  try {
    fields = JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8'));
  } catch {
    // a first pull that stopped before it wrote one
  }
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
