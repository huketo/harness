// Menu buttons: click or Enter/Space to toggle, Escape or outside click to close.
function setupMenu(buttonId, menuId) {
  const button = document.getElementById(buttonId);
  const menu = document.getElementById(menuId);
  const items = () => Array.from(menu.querySelectorAll('[role="menuitem"]'));

  function open() {
    menu.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    items()[0].focus();
  }
  function close({ returnFocus = true } = {}) {
    menu.hidden = true;
    button.setAttribute('aria-expanded', 'false');
    if (returnFocus) button.focus();
  }

  button.addEventListener('click', () => (menu.hidden ? open() : close()));
  menu.addEventListener('keydown', (event) => {
    const list = items();
    const index = list.indexOf(document.activeElement);
    if (event.key === 'Escape') close();
    if (event.key === 'ArrowDown') { event.preventDefault(); list[(index + 1) % list.length].focus(); }
    if (event.key === 'ArrowUp') { event.preventDefault(); list[(index - 1 + list.length) % list.length].focus(); }
  });
  menu.addEventListener('click', (event) => {
    if (event.target.closest('[role="menuitem"]')) close();
  });
  document.addEventListener('pointerdown', (event) => {
    if (!menu.hidden && !menu.contains(event.target) && !button.contains(event.target)) {
      close({ returnFocus: false });
    }
  });
}

setupMenu('share-btn', 'share-menu');
setupMenu('more-btn', 'more-menu');
