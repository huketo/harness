const events = {
  '오늘': ['10:00 디자인 리뷰', '13:30 고객 인터뷰', '16:00 주간 회고'],
  '이번 주': Array.from({ length: 24 }, (_, i) => `${(i % 5) + 1}일 ${9 + (i % 8)}:00 일정 ${i + 1}`),
  '다음 주': Array.from({ length: 12 }, (_, i) => `${(i % 5) + 8}일 ${10 + (i % 6)}:00 일정 ${i + 1}`),
};
const list = document.getElementById('events');
const indicator = document.querySelector('.tab-indicator');

function show(tab) {
  document.querySelectorAll('[role="tab"]').forEach((t) => t.setAttribute('aria-selected', String(t === tab)));
  indicator.style.left = tab.offsetLeft + 'px';
  indicator.style.width = tab.offsetWidth + 'px';
  list.innerHTML = '';
  events[tab.textContent].forEach((text, i) => {
    const li = document.createElement('li');
    li.textContent = text;
    li.style.animationDelay = `${i * 120}ms`;
    list.appendChild(li);
  });
}
document.querySelectorAll('[role="tab"]').forEach((tab) => tab.addEventListener('click', () => show(tab)));
show(document.querySelector('[role="tab"][aria-selected="true"]'));
