// The page images render_book.mjs writes into <book-dir>/pages/: NN-slug.png, one for each page pages.json names.

export const pageFile = (n, slug) => `${String(n).padStart(2, '0')}-${slug}.png`;

/**
 * The page images among `names` (a listing of pages/) that the book in pages.json no longer has: left by an earlier
 * book, one printed with --include-failed, say. A full render removes them, so pages/ holds this book only. Files
 * that are not named like a page image are not render_book.mjs's and are kept.
 */
export function stalePages(names, pages) {
  const keep = new Set(pages.map(([n, slug]) => pageFile(n, slug)));
  return names.filter((f) => /^\d{2,}-.+\.png$/.test(f) && !keep.has(f));
}
