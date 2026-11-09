import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

const root = fileURLToPath(new URL('.', import.meta.url))

// `@deckfont/` resolves to the full fonts in dev and export, and to the subset
// fonts when tools/package.mjs builds the single HTML file (DECK_FONTS=subset).
const fontDir = join(root, 'fonts', process.env.DECK_FONTS === 'subset' ? 'subset' : 'full')

// Slidev injects output.manualChunks; Rolldown rejects it once singlefile turns
// code splitting off, so strip it before the bundle is written.
const dropManualChunks: Plugin = {
  name: 'drop-slidev-manual-chunks',
  enforce: 'post',
  outputOptions(out) {
    const { manualChunks, chunkFileNames, ...rest } = out as Record<string, unknown>
    return rest
  },
}

// Files under public/ stay plain path strings here; tools/package.mjs inlines
// them into deck.html after the build.
export default defineConfig(({ command }) => ({
  resolve: { alias: { '@deckfont': fontDir } },
  ...(command === 'build'
    ? {
        plugins: [dropManualChunks, viteSingleFile({ removeViteModuleLoader: true })],
        build: { assetsInlineLimit: 100_000_000 },
      }
    : {}),
}))
