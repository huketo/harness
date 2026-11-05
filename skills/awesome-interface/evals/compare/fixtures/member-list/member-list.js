// Members panel used in workspace settings.
function initials(name) {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function lastActive(ts) {
  const days = Math.floor((Date.now() - ts) / 86400000);
  return days + ' days ago';
}

const STATUS_LABEL = {
  active: 'Active',
  invited: 'Invited',
  expired: 'Invitation expired',
  suspended: 'Suspended',
};

function memberRow(m) {
  return `
    <li class="member">
      <img class="avatar" src="${m.avatar}" alt="">
      <span class="initials" aria-hidden="true">${initials(m.name)}</span>
      <div class="who">
        <div class="name-line">
          <span class="name">${m.name}</span>
          <span class="status status-${m.status}">${STATUS_LABEL[m.status]}</span>
        </div>
        <div class="email">${m.email}</div>
        <div class="meta">${m.title} · ${lastActive(m.lastActiveAt)}</div>
      </div>
      <button class="more" type="button" aria-label="Member actions">•••</button>
    </li>`;
}

function renderMemberList(root, workspace) {
  const { members, seatLimit } = workspace;
  root.innerHTML = `
    <header class="members-head">
      <h2 id="members-title">${members.length} members</h2>
      <span class="seats">${members.length}/${seatLimit} seats</span>
    </header>
    <ul class="members">${members.map(memberRow).join('')}</ul>`;
}
