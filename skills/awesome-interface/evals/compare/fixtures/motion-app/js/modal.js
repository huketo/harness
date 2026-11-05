const modal = document.getElementById('modal');
const toastEl = document.getElementById('toast');

function openModal() {
  modal.hidden = false;
  setTimeout(() => document.getElementById('title').focus(), 500);
}
function closeModal() {
  modal.hidden = true;
  document.getElementById('new-btn').focus();
}
function toast(text) {
  toastEl.textContent = text;
  toastEl.classList.remove('is-shown');
  void toastEl.offsetWidth;
  toastEl.classList.add('is-shown');
}

document.getElementById('new-btn').addEventListener('click', openModal);
document.getElementById('cancel').addEventListener('click', closeModal);
document.getElementById('create').addEventListener('click', () => {
  closeModal();
  toast('일정을 만들었습니다.');
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !modal.hidden) closeModal();
});
