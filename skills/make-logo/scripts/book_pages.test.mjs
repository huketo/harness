import assert from 'node:assert/strict';
import {test} from 'node:test';

import {pageFile, stalePages} from './book_pages.mjs';

test('page images are named by their number and slug', () => {
  assert.equal(pageFile(3, 'd1-use'), '03-d1-use.png');
  assert.equal(pageFile(12, 'compare-1'), '12-compare-1.png');
});

test('a full render drops the page images an earlier book left and keeps everything else', () => {
  // The earlier book was printed with --include-failed: two more directions, so more pages under other numbers.
  const left = ['01-cover.png', '02-directions-1.png', '03-d1-use.png', '09-d2-use.png', '14-compare-1.png',
    'notes.txt', 'cover.png', '03-d1-use.png.bak'];
  const pages = [[1, 'cover'], [2, 'directions-1'], [3, 'd1-use'], [8, 'compare-1']];
  assert.deepEqual(stalePages(left, pages), ['09-d2-use.png', '14-compare-1.png']);
});
