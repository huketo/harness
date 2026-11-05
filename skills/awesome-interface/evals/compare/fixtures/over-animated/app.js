const orders = [
  { id: 'A-10421', customer: '김하늘', amount: 42000, status: 'paid' },
  { id: 'A-10422', customer: '이도윤', amount: 18500, status: 'shipping' },
  { id: 'A-10423', customer: '박서연', amount: 96000, status: 'paid' },
  { id: 'A-10424', customer: '최민준', amount: 7900, status: 'shipping' },
  { id: 'A-10425', customer: '정유나', amount: 132000, status: 'paid' },
  { id: 'A-10426', customer: '강지호', amount: 25000, status: 'paid' },
  { id: 'A-10427', customer: '윤채원', amount: 58000, status: 'shipping' },
  { id: 'A-10428', customer: '임수아', amount: 11000, status: 'paid' },
];
const LABEL = { paid: '결제 완료', shipping: '배송 중' };
const won = new Intl.NumberFormat('ko-KR');

// 숫자가 0부터 올라가는 효과
function countUp(el) {
  const target = Number(el.dataset.value);
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / 1200);
    el.textContent = won.format(Math.round(target * t));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// 통계 카드가 화면에 들어오면 보이게 한다
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
      countUp(entry.target.querySelector('.num'));
      observer.unobserve(entry.target);
    }
  });
});
document.querySelectorAll('.stat').forEach((el) => observer.observe(el));

const rows = document.getElementById('rows');
function renderRows(filter) {
  rows.innerHTML = '';
  orders
    .filter((o) => filter === 'all' || o.status === filter)
    .forEach((o, i) => {
      const tr = document.createElement('tr');
      tr.style.animationDelay = `${i * 90}ms`;
      tr.innerHTML = `<td>${o.id}</td><td>${o.customer}</td><td>${won.format(o.amount)}원</td><td>${LABEL[o.status]}</td>`;
      tr.addEventListener('click', () => openDetail(o));
      rows.appendChild(tr);
    });
}

const ink = document.querySelector('.tab-ink');
function moveInk(tab) {
  ink.style.left = tab.offsetLeft + 'px';
  ink.style.width = tab.offsetWidth + 'px';
}
document.querySelectorAll('[role="tab"]').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('[role="tab"]').forEach((t) => t.setAttribute('aria-selected', 'false'));
    tab.setAttribute('aria-selected', 'true');
    moveInk(tab);
    renderRows(tab.dataset.filter);
  });
});

const panel = document.getElementById('detail');
function openDetail(order) {
  document.getElementById('detail-title').textContent = `주문 ${order.id}`;
  document.getElementById('detail-body').textContent = `${order.customer} · ${won.format(order.amount)}원`;
  document.getElementById('saved').hidden = true;
  panel.hidden = false;
  requestAnimationFrame(() => panel.classList.add('is-open'));
}
function closeDetail() {
  panel.classList.remove('is-open');
  panel.addEventListener('transitionend', () => {
    panel.hidden = true;
    document.getElementById('rows').querySelector('tr')?.focus();
  }, { once: true });
}
document.getElementById('close-detail').addEventListener('click', closeDetail);
document.getElementById('mark').addEventListener('click', () => {
  document.getElementById('saved').hidden = false;
  showToast('배송 처리했습니다.');
});

const palette = document.getElementById('palette');
function openSearch() {
  palette.hidden = false;
  // 팝 애니메이션이 끝난 뒤 입력창에 포커스
  setTimeout(() => document.getElementById('search').focus(), 400);
}
document.getElementById('open-search').addEventListener('click', openSearch);
document.addEventListener('keydown', (event) => {
  if (event.key === '/' && palette.hidden) { event.preventDefault(); openSearch(); }
  if (event.key === 'Escape' && !palette.hidden) palette.hidden = true;
});

const toast = document.getElementById('toast');
function showToast(text) {
  toast.textContent = text;
  toast.classList.add('is-shown');
  setTimeout(() => toast.classList.remove('is-shown'), 2400);
}

renderRows('all');
moveInk(document.querySelector('[aria-selected="true"]'));
