#!/usr/bin/env node
// Copy the Slidev starter into a deck directory. Existing work is never overwritten.
//
//   node <skill-directory>/scripts/new-deck.mjs <deck-directory>
//
// The directory may be new or may already hold phase artifacts (brief.md,
// outline.md, DESIGN.md, design/); if any starter path already exists there,
// nothing is copied. It installs nothing and starts nothing.
import { cp, mkdir, readdir, stat } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const starter = resolve(dirname(fileURLToPath(import.meta.url)), '../assets/slidev')
const [destination, ...extra] = process.argv.slice(2)
const exists = p => stat(p).then(() => true, () => false)

try {
  if (!destination || extra.length) throw new Error('Usage: node new-deck.mjs <deck-directory>')
  const target = resolve(destination)
  const entries = (await readdir(starter)).filter(name => name !== 'node_modules')
  const taken = []
  for (const name of entries) if (await exists(join(target, name))) taken.push(name)
  if (taken.length) throw new Error(`Refusing to overwrite ${taken.join(', ')} in ${target}`)
  await mkdir(target, { recursive: true })
  for (const name of entries)
    await cp(join(starter, name), join(target, name), { recursive: true, errorOnExist: true, force: false })
  console.log(`Copied the Slidev starter to ${target}.
Next: cd ${destination} && npm ci && npm run fonts && npm run dev`)
} catch (error) {
  console.error(error.message)
  process.exit(1)
}
