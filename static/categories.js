const categoryArea = document.querySelector('.categories.list-nav');
if (categoryArea) {
  const nav = categoryArea.querySelector('nav');
  const links = [...nav.querySelectorAll('a')];
  const trigger = categoryArea.querySelector('.category-trigger');
  const sheet = categoryArea.querySelector('dialog');
  const mobile = matchMedia('(max-width: 760px)');
  const check = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  check.setAttribute('class', 'category-icon');
  check.setAttribute('viewBox', '0 0 24 24');
  check.setAttribute('aria-hidden', 'true');
  check.innerHTML = '<path d="m4 12 5 5L20 6"/>';
  function updateSelection() {
    const selected = nav.querySelector('[aria-current]') || links[0];
    trigger.querySelector('[data-category-name]').textContent = selected.textContent.trim();
    trigger.setAttribute('aria-label', 'カテゴリを選択：' + selected.textContent.trim());
    selected.append(check);
  }

  // The standalone preview uses fragment links in place of server-side queries.
  const samples = [...document.querySelectorAll('.sample-row')];
  if (samples.length) {
    function filterSamples() {
      const selected = links.find(link => link.hash === location.hash) || links[0];
      links.forEach(link => {
        link.removeAttribute('aria-current');
        link.classList.toggle('active', link === selected);
      });
      selected.setAttribute('aria-current', 'page');
      samples.forEach(row => { row.hidden = selected !== links[0] && '#' + row.id !== selected.hash; });
      document.querySelector('[data-sample-count]').textContent = samples.filter(row => !row.hidden).length + '件';
      updateSelection();
    }
    filterSamples();
    window.addEventListener('hashchange', filterSamples);
  }

  if (typeof sheet.showModal === 'function') {
    function layoutCategories() {
      if (sheet.open) sheet.close();
      if (mobile.matches) sheet.querySelector('[data-category-options]').append(nav);
      else categoryArea.prepend(nav);
      trigger.hidden = !mobile.matches;
      updateSelection();
    }
    layoutCategories();
    mobile.addEventListener('change', layoutCategories);
    trigger.addEventListener('click', () => {
      sheet.showModal();
      trigger.setAttribute('aria-expanded', 'true');
      document.documentElement.classList.add('category-modal-open');
      (nav.querySelector('[aria-current]') || links[0]).focus();
    });
    sheet.addEventListener('close', () => {
      document.documentElement.classList.remove('category-modal-open');
      trigger.setAttribute('aria-expanded', 'false');
    });
    sheet.querySelector('[data-close-category]').onclick = () => sheet.close();
    nav.addEventListener('click', event => {
      if (sheet.open && event.target.closest('a')) sheet.close();
    });
    sheet.addEventListener('click', event => {
      if (event.target !== sheet) return;
      const rect = sheet.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right ||
          event.clientY < rect.top || event.clientY > rect.bottom) sheet.close();
    });
  }
}
