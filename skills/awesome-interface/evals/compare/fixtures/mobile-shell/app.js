const items = [
  { label: '우유 1L', done: false },
  { label: '대파', done: true },
  { label: '계란 30구', done: false },
  { label: '두부', done: false },
  { label: '사과 한 봉지', done: false },
  { label: '주방 세제', done: true },
  { label: '냉동 만두', done: false },
  { label: '그릭 요거트', done: false },
  { label: '양파', done: false },
  { label: '키친타월', done: false },
  { label: '바나나', done: false },
  { label: '시리얼', done: false },
];

const list = document.getElementById('list');

function render() {
  list.innerHTML = '';
  items.forEach((item, i) => {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'row' + (item.done ? ' is-done' : '');
    row.setAttribute('aria-pressed', String(item.done));
    row.innerHTML = '<span class="check" aria-hidden="true"></span><span class="label"></span>';
    row.querySelector('.label').textContent = item.label;
    row.addEventListener('click', () => {
      items[i].done = !items[i].done;
      render();
    });
    list.appendChild(row);
  });
}

document.getElementById('composer').addEventListener('submit', (event) => {
  event.preventDefault();
  const input = document.getElementById('item');
  const label = input.value.trim();
  if (!label) return;
  items.unshift({ label, done: false });
  input.value = '';
  render();
});

function selectOne(selector, activeClass) {
  document.querySelectorAll(selector).forEach((el) => {
    el.addEventListener('click', () => {
      document.querySelectorAll(selector).forEach((other) => other.classList.remove(activeClass));
      el.classList.add(activeClass);
    });
  });
}
selectOne('.chip', 'is-active');
selectOne('.tab', 'is-active');

render();
