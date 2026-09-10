#!/usr/bin/env node
import { cp, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const assets = resolve(dirname(fileURLToPath(import.meta.url)), '../assets')
const library = join(assets, 'template-library')
const usage = 'Usage: node new-deck.mjs html <new-directory> --template <catalog-slug>\n       node new-deck.mjs <slidev|reveal> <new-directory> [--style editorial|signal|technical]'
const [engine, destination, flag, selected, ...extra] = process.argv.slice(2)

try {
  if (!destination || extra.length || !['html', 'slidev', 'reveal'].includes(engine)) throw new Error(usage)
  let source
  let theme
  if (engine === 'html') {
    const catalog = JSON.parse(await readFile(join(library, 'index.json'), 'utf8'))
    if (flag !== '--template' || !catalog.templates.some(template => template.slug === selected))
      throw new Error(`${usage}\nChoose an actual template from ${join(library, 'index.json')}`)
    source = join(library, 'templates', selected)
  } else {
    if ((flag !== undefined && (flag !== '--style' || !selected)) || !['editorial', 'signal', 'technical'].includes(selected ?? 'editorial'))
      throw new Error(usage)
    source = join(assets, engine)
    theme = await readFile(join(assets, 'styles', `${selected ?? 'editorial'}.css`), 'utf8')
  }
  // Resolve the source before reserving a new destination. Existing work is never overwritten.
  const entries = await readdir(source)
  const target = resolve(destination)
  await mkdir(dirname(target), { recursive: true })
  await mkdir(target)
  for (const name of entries)
    await cp(join(source, name), join(target, name), { recursive: true, errorOnExist: true, force: false })

  if (engine === 'html') {
    const html = await readFile(join(target, 'template.html'), 'utf8')
    if (html.includes('src="deck-stage.js"') && !entries.includes('deck-stage.js'))
      await cp(join(library, 'runtime/deck-stage.js'), join(target, 'deck-stage.js'), { errorOnExist: true, force: false })
    for (const name of ['LICENSE', 'ORIGIN.json'])
      await cp(join(library, name), join(target, name), { errorOnExist: true, force: false })
    console.log(`Copied complete ${selected} template to ${target}. Open template.html.`)
    console.log('Read design.md and replace demo content while preserving this template\'s layouts, fonts, motifs, and runtime. Online fonts are not yet packaged for offline delivery.')
  } else {
    await writeFile(join(target, 'theme.css'), theme, { flag: 'wx' })
    if (engine === 'slidev' && selected === 'technical') {
      const slides = join(target, 'slides.md')
      await writeFile(slides, (await readFile(slides, 'utf8')).replace(/^colorSchema: light$/m, 'colorSchema: dark'))
    }
    for (const name of ['ATTRIBUTION.md', 'LICENSE.frontend-slides.txt'])
      await cp(join(assets, 'styles', name), join(target, name), { errorOnExist: true, force: false })
    console.log(`Created native ${engine} engine starter at ${target}. Run npm install, then npm run dev.`)
    console.log('This is an engine starter with a palette, not a port of the 34 HTML themes. When a theme is selected, port its actual compositions into the native engine.')
  }
} catch (error) {
  console.error(`Cannot create deck: ${error.message}`)
  process.exitCode = 1
}
