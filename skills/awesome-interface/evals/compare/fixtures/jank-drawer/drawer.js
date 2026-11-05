// Project drawer: open/close with the menu button, drag the header left to close.
const body = document.body;
const root = document.documentElement;
const drawer = document.getElementById('drawer');
const nav = document.getElementById('nav');
const openBtn = document.getElementById('open');
const hint = document.getElementById('drag-hint');

const projects = Array.from({ length: 240 }, (_, i) => ({
  name: `프로젝트 ${String(i + 1).padStart(3, '0')}`,
  owner: ['디자인', '플랫폼', '결제', '성장'][i % 4],
}));

const state = { open: false, dragging: false, dragX: 0 };

function render() {
  body.classList.toggle('drawer-open', state.open);
  body.classList.toggle('is-dragging', state.dragging);
  openBtn.setAttribute('aria-expanded', String(state.open));
  root.style.setProperty('--drag-x', state.dragX + 'px');
  hint.textContent = state.dragging ? `${Math.round(-state.dragX)}px` : '';
  nav.innerHTML = projects
    .map((p) => `<li><span class="dot"></span><span>${p.name}</span><small>${p.owner}</small></li>`)
    .join('');
}

function setState(patch) {
  Object.assign(state, patch);
  render();
}

openBtn.addEventListener('click', () => setState({ open: true }));
document.getElementById('close').addEventListener('click', () => setState({ open: false }));
document.getElementById('backdrop').addEventListener('click', () => setState({ open: false }));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && state.open) setState({ open: false });
});

let startX = 0;
const head = drawer.querySelector('.drawer-head');
head.addEventListener('pointerdown', (event) => {
  if (event.target.closest('button')) return;
  startX = event.clientX;
  head.setPointerCapture(event.pointerId);
  setState({ dragging: true });
});
head.addEventListener('pointermove', (event) => {
  if (!state.dragging) return;
  const dx = Math.min(0, event.clientX - startX);
  setState({ dragX: dx });
});
head.addEventListener('pointerup', () => {
  if (!state.dragging) return;
  const shouldClose = state.dragX < -120;
  setState({ dragging: false, dragX: 0, open: !shouldClose });
});
head.addEventListener('pointercancel', () => setState({ dragging: false, dragX: 0 }));

render();
