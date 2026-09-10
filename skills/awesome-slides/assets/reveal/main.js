// Native npm setup adapted from content-skills; see THIRD-PARTY-NOTICES.txt.
import Reveal from 'reveal.js';
import Notes from 'reveal.js/plugin/notes/notes.esm.js';
import Highlight from 'reveal.js/plugin/highlight/highlight.esm.js';
import 'reveal.js/dist/reveal.css';
import './deck.css';

const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const deck = new Reveal(document.querySelector('.reveal'), {
  width: 1280,
  height: 720,
  margin: 0.04,
  center: false,
  hash: true,
  hashOneBasedIndex: true,
  fragmentInURL: true,
  controls: true,
  progress: true,
  slideNumber: 'c/t',
  transition: reducedMotion.matches ? 'none' : 'fade',
  backgroundTransition: 'none',
  // Scroll view preserves the stage; it is not a reflowed mobile handout.
  scrollActivationWidth: null,
  pdfSeparateFragments: false,
  showNotes: new URLSearchParams(location.search).has('notes') ? 'separate-page' : false,
  plugins: [Notes, Highlight],
});

deck.initialize();
reducedMotion.addEventListener('change', event => {
  deck.configure({ transition: event.matches ? 'none' : 'fade' });
});
