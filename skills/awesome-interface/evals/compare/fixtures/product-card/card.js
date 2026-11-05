const HOUR = 3600000;
const lots = [
  { title: 'Mid-century walnut lounge chair', photo: 'img/chair.svg', bid: 1240, bids: 1, watchers: 38,
    seller: { name: 'Northwood Vintage', avatar: 'img/seller-wide.svg' }, updatedAt: Date.now() - 20 * 1000 },
  { title: 'Brass desk lamp, 1960s', photo: 'img/lamp.svg', bid: 185, bids: 12, watchers: 1,
    seller: { name: 'Lumen & Co', avatar: 'img/seller-tall.svg' }, updatedAt: Date.now() - 3 * HOUR },
  { title: 'Hand-thrown stoneware set (6 pieces)', photo: 'img/bowls.svg', bid: 96, bids: 4, watchers: 9,
    seller: { name: 'Clay Studio', avatar: 'img/seller-wide.svg' }, updatedAt: Date.now() - 400 * 24 * HOUR },
];

function ago(ts) {
  const minutes = Math.floor((Date.now() - ts) / 60000);
  if (minutes < 60) return `${minutes} minutes ago`;
  return `${Math.floor(minutes / 60)} hours ago`;
}

function cardHtml(lot, i) {
  return `
  <article class="card">
    <img class="photo" src="${lot.photo}" alt="${lot.title}">
    <div class="body">
      <h2 class="title">${lot.title}</h2>
      <div class="bid"><strong id="bid-${i}">$${lot.bid}</strong><span>${lot.bids} bids</span></div>
      <div class="meta"><span>${lot.watchers} watchers</span><span>Updated ${ago(lot.updatedAt)}</span></div>
      <div class="seller"><img src="${lot.seller.avatar}" alt=""><span>${lot.seller.name}</span></div>
      <button type="button">Place bid</button>
    </div>
  </article>`;
}

const grid = document.getElementById('grid');
grid.innerHTML = lots.map(cardHtml).join('');

// Simulated live bidding.
setInterval(() => {
  const i = Math.floor(Math.random() * lots.length);
  lots[i].bid += [1, 5, 10, 25][Math.floor(Math.random() * 4)];
  document.getElementById(`bid-${i}`).textContent = `$${lots[i].bid}`;
}, 900);
