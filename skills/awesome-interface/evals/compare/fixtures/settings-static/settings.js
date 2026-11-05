document.querySelectorAll('.switch').forEach((sw) => {
  sw.addEventListener('click', () => {
    sw.setAttribute('aria-checked', String(sw.getAttribute('aria-checked') !== 'true'));
  });
});

const disclosure = document.querySelector('.disclosure');
const advanced = document.getElementById('advanced');
disclosure.addEventListener('click', () => {
  const open = disclosure.getAttribute('aria-expanded') === 'true';
  disclosure.setAttribute('aria-expanded', String(!open));
  advanced.hidden = open;
});

document.getElementById('domains').addEventListener('click', (event) => {
  const button = event.target.closest('.remove');
  if (button) button.closest('li').remove();
});

const filter = document.getElementById('filter');
document.addEventListener('keydown', (event) => {
  if (event.key === '/' && document.activeElement !== filter) {
    event.preventDefault();
    filter.focus();
  }
});
filter.addEventListener('input', () => {
  const q = filter.value.trim();
  document.querySelectorAll('.row').forEach((row) => {
    row.hidden = q !== '' && !row.textContent.includes(q);
  });
});

const saveState = document.getElementById('save-state');
document.getElementById('save').addEventListener('click', () => {
  saveState.textContent = '저장 중…';
  setTimeout(() => { saveState.textContent = '저장했습니다.'; }, 600);
});
