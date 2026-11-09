#!/usr/bin/env node
// Open deck.html offline in headless Chromium, step through every slide and
// click state with ArrowRight, and record what a presenter would see.
//
//   node tools/check.mjs [deck.html] [--size 1280x720] [--executable-path <chromium>]
//
// Writes .cache/check/NN.png per state, .cache/check/index.html (contact
// sheet), and .cache/check/report.json. Exits 1 when anything besides the file
// itself tried to load, a load failed, the page threw, or text left the slide
// or was clipped. Console errors are listed but do not fail the run.
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { chromium } from 'playwright-chromium'

const deck = fileURLToPath(new URL('..', import.meta.url))
const args = process.argv.slice(2)
const opt = (name, fallback) => { const i = args.indexOf(name); return i >= 0 ? args.splice(i, 2)[1] : fallback }
const [w, h] = opt('--size', '1280x720').split('x').map(Number)
const executablePath = opt('--executable-path', undefined)
const file = resolve(args[0] ?? join(deck, 'deck.html'))
const out = join(deck, '.cache', 'check')
rmSync(out, { recursive: true, force: true })
mkdirSync(out, { recursive: true })

const browser = await chromium.launch({ executablePath })
const context = await browser.newContext({ viewport: { width: w, height: h }, offline: true })
const page = await context.newPage()
const report = { file, size: `${w}x${h}`, blocked: [], failed: [], pageErrors: [], consoleErrors: [], states: [] }
// The delivered file must stand alone: only itself and inline data/blob URLs may load.
const entry = pathToFileURL(file).href
await context.route('**/*', route => {
  const url = route.request().url()
  if (url.split('#')[0] === entry || /^(data|blob):/.test(url)) return route.continue()
  report.blocked.push(url)
  return route.abort('internetdisconnected')
})
page.on('requestfailed', r => { if (!report.blocked.includes(r.url())) report.failed.push(`${r.url().slice(0, 120)} ${r.failure()?.errorText}`) })
page.on('pageerror', e => { if (!/Wake Lock/i.test(String(e))) report.pageErrors.push(String(e).slice(0, 300)) })
page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push(m.text().slice(0, 300)) })

await page.goto(`${pathToFileURL(file)}#/1`)
await page.evaluate(() => document.fonts.ready)
await page.waitForTimeout(1200)

const inspect = () => page.evaluate(() => {
  const n = (location.hash.match(/#\/(\d+)/) || [0, '1'])[1]
  const slide = document.querySelector(`.slidev-page-${n} .slidev-layout`)
  const problems = []
  if (slide) {
    const box = slide.getBoundingClientRect()
    for (const el of slide.querySelectorAll('*')) {
      const own = [...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())
      const style = getComputedStyle(el)
      if (!own && !el.textContent.trim()) continue
      if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) continue
      const r = el.getBoundingClientRect()
      // Screen-reader-only text (KaTeX's MathML, sr-only utilities) is taken out of flow and shrunk to about 1px
      // in both directions; anything larger or still in flow is visible content and stays checked.
      if (/^(absolute|fixed)$/.test(style.position) && r.width <= 2 && r.height <= 2) continue
      if (r.width === 0 || r.height === 0) continue
      const label = `${el.tagName.toLowerCase()} "${el.textContent.trim().slice(0, 40)}"`
      if (own && (r.left < box.left - 1 || r.right > box.right + 1 || r.top < box.top - 1 || r.bottom > box.bottom + 1))
        problems.push(`outside slide: ${label}`)
      // Any non-visible overflow hides content: hidden/clip cut it, auto/scroll put it behind a scrollbar nobody scrolls on stage.
      const hidesX = style.overflowX !== 'visible' && el.scrollWidth > el.clientWidth + 1
      const hidesY = style.overflowY !== 'visible' && el.scrollHeight > el.clientHeight + 1
      if (hidesX || hidesY) problems.push(`clipped: ${label}`)
    }
  }
  const families = new Set()
  for (const el of slide?.querySelectorAll('*') ?? []) families.add(getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim())
  return { hash: location.hash, title: slide?.querySelector('h1')?.textContent.trim().slice(0, 60) ?? null, families: [...families], problems }
})

let last = null
for (let i = 0; i < 500; i++) {
  const state = await inspect()
  if (state.hash === last) break
  last = state.hash
  const shot = `${String(report.states.length + 1).padStart(2, '0')}.png`
  await page.screenshot({ path: join(out, shot) })
  report.states.push({ shot, ...state })
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(700)
}

report.fonts = await page.evaluate(() => [...document.fonts].map(f => `${f.family} ${f.weight} ${f.status}`))
await browser.close()

const cards = report.states.map(s => `<figure><img src="${s.shot}" loading="lazy"><figcaption>${s.shot} ${s.hash}${s.problems.length ? ` — ${s.problems.length} problem(s)` : ''}</figcaption></figure>`).join('\n')
writeFileSync(join(out, 'index.html'), `<!doctype html><meta charset="utf-8"><title>contact sheet</title>
<style>body{font:13px system-ui;margin:16px;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}img{width:100%;border:1px solid #ccc}figure{margin:0}</style>
${cards}`)
writeFileSync(join(out, 'report.json'), JSON.stringify(report, null, 2))

const problems = report.states.flatMap(s => s.problems.map(p => `${s.shot} ${s.hash}: ${p}`))
console.log(`check.mjs: ${report.states.length} states, ${report.blocked.length} blocked requests, ${report.failed.length} failed loads, ${report.pageErrors.length} page errors, ${problems.length} layout problems, ${report.consoleErrors.length} console errors`)
for (const line of [...report.blocked.map(u => `blocked: ${u}`), ...report.failed.map(u => `failed: ${u}`), ...report.pageErrors.map(e => `error: ${e}`), ...problems, ...report.consoleErrors.map(e => `console: ${e}`)]) console.log(`  ${line}`)
console.log(`check.mjs: contact sheet at ${join(out, 'index.html')}`)
process.exit(report.blocked.length || report.failed.length || report.pageErrors.length || problems.length ? 1 : 0)
