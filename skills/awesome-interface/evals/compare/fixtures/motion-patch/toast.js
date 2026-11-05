// Small toast stack: newest at the bottom, older toasts move up.
const toaster = document.createElement('div');
toaster.className = 'toaster';
document.body.appendChild(toaster);

const GAP = 8;
const live = [];

function layout() {
  let offset = 0;
  for (let i = live.length - 1; i >= 0; i--) {
    live[i].style.setProperty('--offset', `${-offset}px`);
    offset += live[i].offsetHeight + GAP;
  }
}

function dismiss(el) {
  if (el.dataset.state === 'closing') return;
  el.dataset.state = 'closing';
  live.splice(live.indexOf(el), 1);
  layout();
  el.addEventListener('transitionend', () => el.remove(), { once: true });
}

export function toast(message, { type = 'info', duration = 4000 } = {}) {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  el.addEventListener('click', () => dismiss(el));
  toaster.appendChild(el);
  live.push(el);
  layout();
  requestAnimationFrame(() => { el.dataset.state = 'open'; });
  setTimeout(() => dismiss(el), duration);
  return () => dismiss(el);
}
