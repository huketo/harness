#!/usr/bin/env node
// Render design variants of real slides side by side as one PNG.
//
//   node tools/variants.mjs --slides 1,4 --out design/round-01.png <variant> [<variant> ...]
//   node tools/variants.mjs --slides 1,4,2 --out design/final.png          (the deck as it is)
//
// A variant is a directory design/variants/<name>/ whose files (theme.css,
// style.css, layouts/*.vue, components/*.vue, ...) overlay the deck for that
// render only; the deck itself is never modified. An optional variant.json
// overrides headmatter keys CSS cannot reach, such as {"colorSchema": "dark"}. Two variants are labelled
// 왼쪽 / 오른쪽, more are labelled A, B, C. Rows are slides, columns are variants.
import { execFileSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { chromium } from 'playwright-chromium'

const deck = fileURLToPath(new URL('..', import.meta.url))
const args = process.argv.slice(2)
const opt = name => { const i = args.indexOf(name); return i >= 0 ? args.splice(i, 2)[1] : undefined }
const slides = opt('--slides')
const out = resolve(deck, opt('--out') ?? 'design/compare.png')
const executablePath = opt('--executable-path')
const variants = args
if (!slides || !/^\d+(,\d+)*$/.test(slides)) {
  console.error('usage: node tools/variants.mjs --slides 1,4 --out design/round-01.png [variant ...]')
  process.exit(1)
}

const work = join(deck, '.cache', 'variants')
rmSync(work, { recursive: true, force: true })
mkdirSync(work, { recursive: true })
const SKIP = new Set(['node_modules', '.cache', '.font-cache', 'design', 'dist', 'fonts', 'deck.html', 'deck.pdf'])

function render(name) {
  const dir = join(work, name ?? 'deck')
  mkdirSync(dir)
  for (const entry of readdirSync(deck)) if (!SKIP.has(entry)) cpSync(join(deck, entry), join(dir, entry), { recursive: true })
  // node_modules can be linked; fonts are copied because Vite refuses to serve files that resolve outside the root.
  symlinkSync(join(deck, 'node_modules'), join(dir, 'node_modules'))
  if (existsSync(join(deck, 'fonts'))) cpSync(join(deck, 'fonts'), join(dir, 'fonts'), { recursive: true })
  if (name) {
    const overlay = join(deck, 'design', 'variants', name)
    if (!existsSync(overlay)) throw new Error(`missing ${overlay}`)
    cpSync(overlay, dir, { recursive: true, filter: src => basename(src) !== 'variant.json' })
    const settings = join(overlay, 'variant.json')
    if (existsSync(settings)) {
      // variant.json may override headmatter keys that CSS cannot, e.g. {"colorSchema": "dark"}
      // Only the headmatter (the first --- block) is edited; slide frontmatter below it stays as written.
      const entry = join(dir, 'slides.md')
      const md = readFileSync(entry, 'utf8')
      const end = md.indexOf('\n---', 4)
      if (!md.startsWith('---\n') || end < 0) throw new Error('slides.md must begin with a --- headmatter block')
      let head = md.slice(4, end)
      for (const [key, value] of Object.entries(JSON.parse(readFileSync(settings, 'utf8')))) {
        const re = new RegExp(`^${key}:.*$`, 'm')
        head = re.test(head) ? head.replace(re, `${key}: ${value}`) : `${head}\n${key}: ${value}`
      }
      writeFileSync(entry, `---\n${head}${md.slice(end)}`)
    }
    // A variant with its own tools/fonts.json renders with those fonts (cached downloads are shared).
    if (existsSync(join(overlay, 'tools', 'fonts.json'))) {
      mkdirSync(join(deck, '.font-cache'), { recursive: true })
      symlinkSync(join(deck, '.font-cache'), join(dir, '.font-cache'))
      execFileSync('uv', ['run', join('tools', 'fonts.py'), 'fetch'], { cwd: dir, stdio: 'inherit' })
    }
  }
  const png = join(dir, '.png')
  execFileSync(join(deck, 'node_modules', '.bin', 'slidev'),
    ['export', 'slides.md', '--format', 'png', '--range', slides, '--output', png, ...(executablePath ? ['--executable-path', executablePath] : [])],
    { cwd: dir, stdio: 'inherit' })
  // Slidev names each export by slide number (e.g. 004.png); return them in --slides order.
  const files = readdirSync(png).filter(f => f.endsWith('.png'))
  return slides.split(',').map(Number).map(n => {
    const f = files.find(x => Number(x.split(/[-.]/)[0]) === n)
    if (!f) throw new Error(`no export for slide ${n} in ${png}`)
    return join(png, f)
  })
}

const columns = variants.length ? variants : [null]
const shots = columns.map(render)
const rows = slides.split(',').length
const labels = columns.length === 2 ? ['왼쪽', '오른쪽'] : columns.length === 1 ? [''] : columns.map((_, i) => String.fromCharCode(65 + i))

const cell = 640
const page = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;padding:24px;background:#fff;font:600 22px system-ui,sans-serif;color:#111}
.grid{display:grid;grid-template-columns:repeat(${columns.length},${cell}px);gap:20px 28px}
.label{text-align:center;padding-bottom:4px}
img{width:${cell}px;border:1px solid #bbb;display:block}
</style><div class="grid">
${labels.map(l => `<div class="label">${l}</div>`).join('')}
${Array.from({ length: rows }, (_, r) => shots.map(s => `<img src="${pathToFileURL(s[r])}">`).join('')).join('\n')}
</div>`
const html = join(work, 'sheet.html')
writeFileSync(html, page)
const browser = await chromium.launch({ executablePath })
const tab = await browser.newPage({ viewport: { width: 48 + columns.length * cell + (columns.length - 1) * 28, height: 400 } })
await tab.goto(pathToFileURL(html).href)
await tab.waitForLoadState('load')
mkdirSync(dirname(out), { recursive: true })
await tab.screenshot({ path: out, fullPage: true })
await browser.close()
console.log(`variants.mjs: wrote ${out} (${columns.map((c, i) => `${labels[i] || 'deck'}=${c ?? 'deck'}`).join(', ')}; slides ${slides})`)

