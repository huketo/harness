// Bottom sheet: open with the filter button, drag the handle down to close.
const sheet = document.getElementById('sheet');
const scrim = document.getElementById('scrim');
const handle = document.getElementById('handle');
const openBtn = document.getElementById('open');

let currentY = 0;       // where the sheet should be (px from its open position)
let dragStartY = 0;
let dragStartTime = 0;
let dragging = false;

function setY(y) {
  sheet.style.transform = `translateY(${y}px)`;
}

function animateTo(target, done) {
  sheet.classList.add('is-animating');
  currentY = target;
  setY(target);
  setTimeout(() => {
    sheet.classList.remove('is-animating');
    if (done) done();
  }, 300);
}

function open() {
  sheet.hidden = false;
  scrim.hidden = false;
  setY(sheet.offsetHeight);
  requestAnimationFrame(() => animateTo(0));
}

function close() {
  animateTo(sheet.offsetHeight, () => {
    sheet.hidden = true;
    scrim.hidden = true;
    sheet.style.transform = '';
    openBtn.focus();
  });
}

handle.addEventListener('pointerdown', (event) => {
  dragging = true;
  dragStartY = event.clientY - currentY;
  dragStartTime = performance.now();
  sheet.classList.remove('is-animating');
});

window.addEventListener('pointermove', (event) => {
  if (!dragging) return;
  currentY = event.clientY - dragStartY;
  setY(currentY);
});

window.addEventListener('pointerup', (event) => {
  if (!dragging) return;
  dragging = false;
  const totalDistance = event.clientY - (dragStartY + 0);
  const totalElapsed = performance.now() - dragStartTime;
  const velocity = Math.abs(totalDistance) / totalElapsed;
  if (currentY > sheet.offsetHeight / 2 || velocity > 2.5) {
    close();
  } else {
    animateTo(0);
  }
});

openBtn.addEventListener('click', open);
document.getElementById('close').addEventListener('click', close);
document.getElementById('apply').addEventListener('click', close);
scrim.addEventListener('click', close);
