import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir, mkdtemp, readdir, readFile, rm, symlink, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath, pathToFileURL} from 'node:url';

import {cacheRoot, collectionDir, keepOrFetch, recorded, refreshManifest, writeAtomic, writeManifest} from './collection.mjs';

const hex = (s) => createHash('sha256').update(s).digest('hex');
const here = dirname(fileURLToPath(import.meta.url));

/**
 * Runs a pull script with `fetch` replaced: a URL starting with a key of `routes` gets that answer (`json`, or `body`
 * with `type`), and any other URL throws, so no test reaches the network.
 */
async function pull(cache, script, args, routes = {}) {
  const stub = join(cache, 'fetch-stub.mjs');
  await writeFile(stub, `const routes = ${JSON.stringify(routes)};
globalThis.fetch = async (url) => {
  const hit = Object.entries(routes).find(([prefix]) => String(url).startsWith(prefix));
  if (!hit) throw new Error('no network in tests: ' + url);
  const r = hit[1];
  return new Response(r.json ? JSON.stringify(r.json) : r.body, {status: 200, headers: {'content-type': r.type ?? 'application/json'}});
};
`);
  return spawnSync(process.execPath, ['--import', pathToFileURL(stub).href, join(here, script), ...args],
    {env: {...process.env, XDG_CACHE_HOME: cache}, encoding: 'utf8'});
}

test('collections live in the XDG cache, under one-word names', () => {
  assert.equal(cacheRoot({XDG_CACHE_HOME: '/x/cache'}), join('/x/cache', 'hstack', 'make-logo'));
  assert.match(cacheRoot({XDG_CACHE_HOME: 'relative'}), /\.cache[\\/]hstack[\\/]make-logo$/);
  assert.equal(collectionDir('arena', {XDG_CACHE_HOME: '/x/cache'}), join('/x/cache', 'hstack', 'make-logo', 'arena'));
  for (const bad of ['refs/arena', '../arena', '', '.hidden']) assert.throws(() => collectionDir(bad), /one word/);
  // The font and potrace caches live beside the collections; a collection can't take their names.
  for (const taken of ['fonts', 'potrace']) assert.throws(() => collectionDir(taken), /taken/);
});

test('the manifest lists every file in the collection with its sha256', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  await mkdir(join(dir, 'channel'));
  await writeFile(join(dir, 'channel', 'new.png'), 'new');
  await writeFile(join(dir, 'channel', 'old.png'), 'old');
  await writeFile(join(dir, 'stray.jpg'), 'stray');
  await writeFile(join(dir, 'manifest.json'), JSON.stringify({items: [
    {file: 'channel/old.png', id: 1, sha256: 'stale'},
    {file: 'channel/gone.png', id: 2},
  ]}));
  const items = await writeManifest(dir, [{file: 'channel/new.png', id: 3, sha256: hex('new')}], {fetched: 'now'});
  assert.deepEqual(items, [
    {file: 'channel/new.png', id: 3, sha256: hex('new')},
    {file: 'channel/old.png', sha256: hex('old')},
    {file: 'stray.jpg', sha256: hex('stray')},
  ]);
  assert.deepEqual(JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')), {fetched: 'now', items});
});

test('run on its own, it lists what a collection holds now, and a file edited since keeps no details', async (t) => {
  const cache = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(cache, {recursive: true, force: true}));
  const dir = join(cache, 'hstack', 'make-logo', 'photos');
  await mkdir(dir, {recursive: true});
  await writeFile(join(dir, 'kept.jpg'), 'kept, then edited');
  await writeFile(join(dir, 'manifest.json'), JSON.stringify({query: 'cafe', fetched: 'then', items: [
    {file: 'kept.jpg', creator: 'Synthetic Creator', sha256: hex('kept')},
    {file: 'deleted.jpg', creator: 'Synthetic Creator', sha256: hex('deleted')},
  ]}));
  const run = spawnSync(process.execPath, [join(here, 'collection.mjs'), 'photos'], {env: {...process.env, XDG_CACHE_HOME: cache}, encoding: 'utf8'});
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')), {query: 'cafe', fetched: 'then', items: [
    {file: 'kept.jpg', sha256: hex('kept, then edited')},
  ]});
});

test('details stay only with the bytes they were recorded for', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  const credit = {creator: 'Synthetic Creator', license: 'CC0 1.0', source: 'https://example.org/p'};
  await writeFile(join(dir, 'same.jpg'), 'same');
  await writeFile(join(dir, 'replaced.jpg'), 'someone else\'s photo');
  await writeFile(join(dir, 'pulled.jpg'), 'pulled now');
  await writeFile(join(dir, 'raced.jpg'), 'changed after the pull hashed it');
  await writeFile(join(dir, 'manifest.json'), JSON.stringify({items: [
    {file: 'same.jpg', ...credit, sha256: hex('same')},
    {file: 'replaced.jpg', ...credit, sha256: hex('the photo the credit is for')},
  ]}));
  const items = await writeManifest(dir, [
    {file: 'pulled.jpg', ...credit, sha256: hex('pulled now')},
    {file: 'raced.jpg', ...credit, sha256: hex('the bytes the pull wrote')},
  ]);
  assert.deepEqual(items, [
    {file: 'pulled.jpg', ...credit, sha256: hex('pulled now')},
    {file: 'raced.jpg', sha256: hex('changed after the pull hashed it')},
    {file: 'same.jpg', ...credit, sha256: hex('same')},
    {file: 'replaced.jpg', sha256: hex("someone else's photo")},
  ]);
});

test('listing a collection again clears what an unfinished pull left', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  await mkdir(join(dir, 'channel'));
  await writeFile(join(dir, 'channel', '1.png'), 'one');
  await writeFile(join(dir, 'channel', '2.png.part'), 'half a download');
  await writeFile(join(dir, 'manifest.json'), JSON.stringify({items: [{file: 'channel/1.png', sha256: hex('one')}]}));
  await writeFile(join(dir, 'manifest.json.part'), '{"items": [');
  const items = await refreshManifest(dir);
  assert.deepEqual(items, [{file: 'channel/1.png', sha256: hex('one')}]);
  assert.deepEqual((await readdir(dir, {recursive: true})).sort(), ['channel', 'channel/1.png', 'manifest.json']);
  // A first pull that stopped before it wrote any manifest.
  await rm(join(dir, 'manifest.json'));
  assert.deepEqual(await refreshManifest(dir), [{file: 'channel/1.png', sha256: hex('one')}]);
});

test('a pull keeps a file only while it has the sha256 recorded for it, and fetches it again otherwise', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  await writeFile(join(dir, 'kept.jpg'), 'as pulled');
  await writeFile(join(dir, 'edited.jpg'), 'edited by hand');
  const known = new Map([['kept.jpg', hex('as pulled')], ['edited.jpg', hex('as pulled too')]]);
  const fetched = [];
  const download = (file, bytes) => async () => {
    fetched.push(file);
    return bytes && Buffer.from(bytes);
  };
  assert.equal(await keepOrFetch(dir, 'kept.jpg', known, download('kept.jpg', 'x')), hex('as pulled'));
  assert.equal(await keepOrFetch(dir, 'edited.jpg', known, download('edited.jpg', 'as pulled too')), hex('as pulled too'));
  assert.equal(await keepOrFetch(dir, 'new.jpg', known, download('new.jpg', 'new')), hex('new'));
  assert.equal(await keepOrFetch(dir, 'refused.jpg', known, download('refused.jpg', null)), null);
  assert.deepEqual(fetched, ['edited.jpg', 'new.jpg', 'refused.jpg']);
  assert.equal(await readFile(join(dir, 'edited.jpg'), 'utf8'), 'as pulled too');
  assert.deepEqual((await readdir(dir)).sort(), ['edited.jpg', 'kept.jpg', 'new.jpg']);
});

test('a file is written whole or not at all', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  await writeAtomic(join(dir, 'a.png'), Buffer.from('whole'));
  await writeManifest(dir, [{file: 'a.png', sha256: hex('whole')}]);
  assert.deepEqual((await readdir(dir)).sort(), ['a.png', 'manifest.json'], 'a .part file was left behind');
  assert.equal(await readFile(join(dir, 'a.png'), 'utf8'), 'whole');
});

test('a pull fetches again a file the manifest lists without its origin, and credits the bytes it fetched', async (t) => {
  const cache = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(cache, {recursive: true, force: true}));
  const root = join(cache, 'hstack', 'make-logo');
  const image = {body: 'the photo the result is for', type: 'image/jpeg'};
  const cases = [
    ['fetch_photos.mjs', ['cafe', 'photos', '1'], 'photos', 'p1.jpg', {
      'https://api.openverse.org/': {json: {results: [{id: 'p1', url: 'https://example.org/p1.jpg', title: 'Synthetic',
        creator: 'Synthetic Creator', license: 'cc0', license_version: '1.0', foreign_landing_url: 'https://example.org/p1'}]}},
      'https://example.org/p1.jpg': image}],
    ['fetch_arena.mjs', ['chan', 'arena', '1'], 'arena', 'chan/9.png', {
      'https://api.are.na/': {json: {data: [{type: 'Image', id: 9, image: {src: 'https://example.org/9.png'}}], meta: {has_more_pages: false}}},
      'https://example.org/9.png': image}],
  ];
  for (const [script, args, name, file, routes] of cases) {
    const dir = join(root, name);
    await mkdir(dirname(join(dir, file)), {recursive: true});
    // Someone replaced the pulled file by hand and listed it with collection.mjs: its sha256, and no origin.
    await writeFile(join(dir, file), 'put there by hand');
    await writeFile(join(dir, 'manifest.json'), JSON.stringify({items: [{file, sha256: hex('put there by hand')}]}));
    const run = await pull(cache, script, args, routes);
    assert.equal(run.status, 0, run.stderr);
    assert.equal(await readFile(join(dir, file), 'utf8'), 'the photo the result is for', `${script} kept the replaced bytes`);
    const [item] = JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')).items;
    assert.equal(item.sha256, hex('the photo the result is for'));
  }
});

test('the bytes a pull keeps are the ones whose origin the manifest records', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  await writeFile(join(dir, 'credited.jpg'), 'as pulled');
  await writeFile(join(dir, 'listed.jpg'), 'put there by hand');
  await writeFile(join(dir, 'manifest.json'), JSON.stringify({items: [
    {file: 'credited.jpg', creator: 'Synthetic Creator', source: 'https://example.org/1', sha256: hex('as pulled')},
    {file: 'listed.jpg', sha256: hex('put there by hand')},
  ]}));
  assert.deepEqual(await recorded(dir, 'source'), new Map([['credited.jpg', hex('as pulled')]]));
});

test('a collection that is a link, or holds one, is refused before a pull and when it is listed', async (t) => {
  const cache = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(cache, {recursive: true, force: true}));
  const root = join(cache, 'hstack', 'make-logo');
  const elsewhere = join(cache, 'elsewhere');
  await mkdir(join(elsewhere, 'chan'), {recursive: true});
  await writeFile(join(elsewhere, 'chan', '1.png'), 'outside the cache');
  await mkdir(join(root, 'arena'), {recursive: true});
  await symlink(join(elsewhere, 'chan'), join(root, 'arena', 'chan'));
  await symlink(elsewhere, join(root, 'photos'));
  for (const [name, link] of [['arena', join(root, 'arena', 'chan')], ['photos', join(root, 'photos')]]) {
    for (const [script, args] of [['fetch_arena.mjs', ['chan', name, '1']], ['fetch_photos.mjs', ['cafe', name, '1']],
      ['collection.mjs', [name]]]) {
      const run = await pull(cache, script, args);
      assert.notEqual(run.status, 0, `${script} ${name} went on`);
      assert.match(run.stderr, /symbolic link/, `${script} ${name}: ${run.stderr}`);
      assert.ok(run.stderr.includes(link), run.stderr);
      assert.doesNotMatch(run.stderr, /no network in tests/, `${script} asked the network first`);
    }
  }
  assert.deepEqual((await readdir(elsewhere, {recursive: true})).sort(), ['chan', 'chan/1.png'], 'a pull wrote through a link');
});
