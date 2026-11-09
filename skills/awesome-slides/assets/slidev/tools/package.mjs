#!/usr/bin/env node
// Package the deck into its deliverables.
//
//   node tools/package.mjs html [--allow-large]          -> deck.html (one self-contained file)
//   node tools/package.mjs pdf  [--executable-path P]    -> deck.pdf
//
// html: subset the fonts to the characters the deck uses, build with the
//       single-file config, embed the font licenses, and check the size budget.
// pdf:  export every slide at its final click state; slides whose frontmatter
//       sets `pdf: steps` are replaced by one page per click step.
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const deck = fileURLToPath(new URL('..', import.meta.url))
const cache = join(deck, '.cache')
const slidev = join(deck, 'node_modules', '.bin', 'slidev')
const BUDGET = 30 * 1024 * 1024
const PLACEHOLDER = /⟨[^⟩\n]*⟩/

const fail = (msg, code = 1) => { console.error(`package.mjs: ${msg}`); process.exit(code) }
const run = (bin, argv, env = {}) => execFileSync(bin, argv, { cwd: deck, stdio: 'inherit', env: { ...process.env, ...env } })
const mb = n => `${(n / 1024 / 1024).toFixed(1)} MB`

// Everything whose text can reach a slide: markdown, components, root CSS
// (content: strings), and data files components import.
function sourceFiles() {
  const out = ['slides.md', 'style.css', 'theme.css'].map(f => join(deck, f)).filter(existsSync)
  const walk = dir => {
    if (!existsSync(dir)) return
    for (const name of readdirSync(dir)) {
      const p = join(dir, name)
      if (statSync(p).isDirectory()) walk(p)
      else if (['.md', '.vue', '.ts', '.js', '.json', '.css', '.yaml', '.yml', '.csv', '.txt'].includes(extname(p))) out.push(p)
    }
  }
  for (const dir of ['pages', 'layouts', 'components', 'snippets', 'setup', 'data']) walk(join(deck, dir))
  return out
}

function checkPlaceholders() {
  const left = []
  for (const file of sourceFiles()) {
    readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
      if (PLACEHOLDER.test(line)) left.push(`${file.slice(deck.length)}:${i + 1}: ${line.trim()}`)
    })
  }
  if (left.length) fail(`starter placeholders (⟨…⟩) remain; replace them before packaging:\n${left.join('\n')}`)
}

// Slidev leaves files under public/ as path strings ("/clip.mp4", "./images/a.svg")
// in markup, CSS url(), and component props, often several times per file. Each
// file's data: URI is written once, in globalThis.__deckAsset; JS template
// literals refer to it, and other contexts (CSS, attributes) get the URI itself.
const MIME = {
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
  '.webp': 'image/webp', '.avif': 'image/avif', '.mp4': 'video/mp4', '.webm': 'video/webm', '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.vtt': 'text/vtt',
}
// Insert right after the opening <head>: the inlined bundle sits inside <head>
// and can itself contain the text "</head>" (Mermaid does), so the closing tag
// is not a safe anchor.
function atHeadStart(page, html) {
  const m = page.match(/<head[^>]*>/i)
  if (!m) fail('built page has no <head>')
  return page.slice(0, m.index + m[0].length) + '\n' + html + page.slice(m.index + m[0].length)
}

function inlinePublic(page) {
  const root = join(deck, 'public')
  const files = []
  const walk = dir => {
    for (const name of readdirSync(dir)) {
      if (name.startsWith('.')) continue
      const p = join(dir, name)
      if (statSync(p).isDirectory()) walk(p)
      else files.push(p.slice(root.length + 1).split('\\').join('/'))
    }
  }
  if (existsSync(root)) walk(root)
  const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const table = []
  for (const rel of files) {
    // Vite turns a root path into `charts/a.svg` (new URL(..., import.meta.url)); Slidev keeps
    // `/charts/a.svg`. A whole template literal equal to the path is a reference with or without
    // the prefix; inside quotes or url() only a prefixed path is, so a bare "a.png" stays text.
    const literal = new RegExp(`\`(?:\\.?/)?${escape(rel)}\``, 'g')
    const quoted = new RegExp(`(["'(]\\s*)(?:\\.?/)${escape(rel)}(?=\\s*["')])`, 'g')
    if (!literal.test(page) && !quoted.test(page)) continue
    const type = MIME[extname(rel).toLowerCase()]
    if (!type) fail(`public/${rel} is used but has no known media type to inline; convert it or add its type to MIME in tools/package.mjs`)
    const uri = `data:${type};base64,${readFileSync(join(root, rel)).toString('base64')}`
    const i = table.push(uri) - 1
    page = page
      .replace(literal, `\`\${globalThis.__deckAsset[${i}]}\``)
      .replace(quoted, (_, lead) => lead + uri)
  }
  if (table.length) page = atHeadStart(page, `<script>globalThis.__deckAsset=${JSON.stringify(table)}</script>`)
  return page
}

function html(allowLarge) {
  checkPlaceholders()
  if (!existsSync(join(deck, 'fonts', 'full'))) fail('fonts/full/ is missing; run `npm run fonts` first')
  mkdirSync(cache, { recursive: true })
  const chars = new Set()
  for (let c = 0x20; c < 0x7F; c++) chars.add(String.fromCharCode(c))
  for (const file of sourceFiles()) for (const ch of readFileSync(file, 'utf8')) chars.add(ch)
  const glyphs = join(cache, 'glyphs.txt')
  writeFileSync(glyphs, [...chars].join(''))
  run('uv', ['run', join('tools', 'fonts.py'), 'subset', '--text', glyphs])
  run(slidev, ['build', 'slides.md', '--base', './', '--out', join('.cache', 'dist')], { DECK_FONTS: 'subset' })

  let page = inlinePublic(readFileSync(join(cache, 'dist', 'index.html'), 'utf8'))
  const external = [...page.matchAll(/<(?:script|link|img|source|video|audio|iframe)\b[^>]*\b(?:src|href)=["']?(https?:[^"' >]+)/gi)]
    .map(m => m[1])
    .concat([...page.matchAll(/url\(\s*["']?(https?:[^"')]+)/gi)].map(m => m[1]))
  if (external.length) fail(`the build still loads remote resources:\n${[...new Set(external)].join('\n')}`)
  const licenses = join(deck, 'fonts', 'LICENSES.txt')
  if (existsSync(licenses)) {
    const text = readFileSync(licenses, 'utf8').replaceAll('</script', '<\\/script')
    page = atHeadStart(page, `<script type="text/plain" id="font-licenses">\n${text}\n</script>`)
  }
  const out = join(deck, 'deck.html')
  writeFileSync(out, page)
  const size = statSync(out).size
  console.log(`package.mjs: wrote deck.html (${mb(size)})`)
  if (size > BUDGET && !allowLarge)
    fail(`deck.html is ${mb(size)}, over the ${mb(BUDGET)} budget. Compress media, or rerun with --allow-large once the person agrees.`, 2)
}

async function pdf(passthrough) {
  const { load } = await import('@slidev/parser/fs')
  const { PDFDocument } = await import('pdf-lib')
  const data = await load({ userRoot: deck, roots: [deck] }, join(deck, 'slides.md'))
  const rendered = data.slides.filter(s => !s.frontmatter?.hide && !s.frontmatter?.disabled)
  const steps = new Set(rendered.flatMap((s, i) => (s.frontmatter?.pdf === 'steps' ? [i + 1] : [])))
  mkdirSync(cache, { recursive: true })
  const exportTo = (name, args) => {
    const file = join(cache, name)
    run(slidev, ['export', 'slides.md', '--output', file, ...args, ...passthrough])
    return file
  }
  const finalFile = exportTo('final.pdf', ['--with-clicks', 'false'])
  const final = await PDFDocument.load(readFileSync(finalFile))
  if (final.getPageCount() !== rendered.length)
    fail(`final-state export has ${final.getPageCount()} pages for ${rendered.length} slides`)
  const merged = await PDFDocument.create()
  if (!steps.size) {
    for (const p of await merged.copyPages(final, final.getPageIndices())) merged.addPage(p)
  } else {
    // Slidev 53 ignores --range in PDF export, so export every click state once
    // and locate each slide's pages. The PNG export names each state
    // `<slide>-<click>.png`, which gives the page count per slide.
    const clicks = await PDFDocument.load(readFileSync(exportTo('clicks.pdf', ['--with-clicks'])))
    const pngDir = join(cache, 'clicks-png')
    rmSync(pngDir, { recursive: true, force: true })
    run(slidev, ['export', 'slides.md', '--format', 'png', '--with-clicks', '--output', pngDir, ...passthrough])
    const perSlide = new Map()
    for (const name of readdirSync(pngDir)) {
      const n = Number(name.split('-')[0])
      if (Number.isInteger(n)) perSlide.set(n, (perSlide.get(n) ?? 0) + 1)
    }
    const counted = [...perSlide.values()].reduce((a, b) => a + b, 0)
    if (perSlide.size !== rendered.length || counted !== clicks.getPageCount())
      fail(`click export has ${clicks.getPageCount()} pages but the PNG export names ${counted} states over ${perSlide.size} slides`)
    let start = 0
    for (let n = 1; n <= rendered.length; n++) {
      const count = perSlide.get(n)
      const [source, indices] = steps.has(n)
        ? [clicks, Array.from({ length: count }, (_, i) => start + i)]
        : [final, [n - 1]]
      for (const p of await merged.copyPages(source, indices)) merged.addPage(p)
      start += count
    }
  }
  writeFileSync(join(deck, 'deck.pdf'), await merged.save())
  console.log(`package.mjs: wrote deck.pdf (${merged.getPageCount()} pages; step slides: ${[...steps].join(', ') || 'none'})`)
}

const [cmd, ...rest] = process.argv.slice(2)
if (cmd === 'html') html(rest.includes('--allow-large'))
else if (cmd === 'pdf') await pdf(rest)
else fail('usage: node tools/package.mjs html [--allow-large] | pdf [--executable-path <chromium>]')
