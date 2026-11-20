import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir, mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';

import {cacheRoot, collectionDir, writeManifest} from './collection.mjs';

const hex = (s) => createHash('sha256').update(s).digest('hex');

test('collections live in the XDG cache, under one-word names', () => {
  assert.equal(cacheRoot({XDG_CACHE_HOME: '/x/cache'}), join('/x/cache', 'hstack', 'make-logo'));
  assert.match(cacheRoot({XDG_CACHE_HOME: 'relative'}), /\.cache[\\/]hstack[\\/]make-logo$/);
  assert.equal(collectionDir('arena', {XDG_CACHE_HOME: '/x/cache'}), join('/x/cache', 'hstack', 'make-logo', 'arena'));
  for (const bad of ['refs/arena', '../arena', '', '.hidden']) assert.throws(() => collectionDir(bad), /one word/);
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
  const items = await writeManifest(dir, [{file: 'channel/new.png', id: 3}], {fetched: 'now'});
  assert.deepEqual(items, [
    {file: 'channel/new.png', id: 3, sha256: hex('new')},
    {file: 'channel/old.png', id: 1, sha256: hex('old')},
    {file: 'stray.jpg', sha256: hex('stray')},
  ]);
  assert.deepEqual(JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')), {fetched: 'now', items});
});

test('run on its own, it lists what a collection holds now, keeping each file\'s details', async (t) => {
  const cache = await mkdtemp(join(tmpdir(), 'make-logo-collection-'));
  t.after(() => rm(cache, {recursive: true, force: true}));
  const dir = join(cache, 'hstack', 'make-logo', 'photos');
  await mkdir(dir, {recursive: true});
  await writeFile(join(dir, 'kept.jpg'), 'kept, then edited');
  await writeFile(join(dir, 'manifest.json'), JSON.stringify({query: 'cafe', fetched: 'then', items: [
    {file: 'kept.jpg', creator: 'Synthetic Creator', sha256: hex('kept')},
    {file: 'deleted.jpg', creator: 'Synthetic Creator', sha256: hex('deleted')},
  ]}));
  const script = join(dirname(fileURLToPath(import.meta.url)), 'collection.mjs');
  const run = spawnSync(process.execPath, [script, 'photos'], {env: {...process.env, XDG_CACHE_HOME: cache}, encoding: 'utf8'});
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')), {query: 'cafe', fetched: 'then', items: [
    {file: 'kept.jpg', creator: 'Synthetic Creator', sha256: hex('kept, then edited')},
  ]});
});
