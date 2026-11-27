for (const field of document.querySelectorAll('.stack [maxlength]')) {
  const count = document.createElement('small');
  count.className = 'counter';
  count.id = 'count-' + field.name;
  field.closest('label').after(count);
  field.setAttribute('aria-describedby', count.id);
  const update = () => { count.textContent = field.value.length + ' / ' + field.maxLength + ' 文字'; };
  field.addEventListener('input', update);
  update();
}

const imageInput = document.querySelector('input[name="image"]');
if (imageInput) {
  imageInput.addEventListener('change', () => {
    const file = imageInput.files[0];
    let problem = '';
    if (file && !['image/jpeg', 'image/png'].includes(file.type)) problem = 'JPEG または PNG を選んでください。';
    if (file && file.size > 5 * 1024 * 1024) problem = '5 MB 以下の画像を選んでください。';
    imageInput.setCustomValidity(problem);
    const info = file ? [file.name, Math.ceil(file.size / 1024) + ' KB', file.type, problem] : [];
    document.querySelector('#file-info').textContent = info.filter(Boolean).join(' ・ ');
  });
}

document.addEventListener('submit', event => {
  const form = event.target;
  if (form.dataset.pending) {
    event.preventDefault();
    return;
  }
  form.dataset.pending = 'true';
  if (event.submitter) {
    event.submitter.disabled = true;
    event.submitter.textContent = '処理中…';
  }
});
window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });

// Text drafts and reading position are scoped to this browser tab.
const tabState = {
  read(key) {
    try { return JSON.parse(sessionStorage.getItem('campus:' + key)); }
    catch { return null; }
  },
  write(key, value) {
    try {
      if (value === null) sessionStorage.removeItem('campus:' + key);
      else sessionStorage.setItem('campus:' + key, JSON.stringify(value));
    } catch { /* Storage may be disabled in private browsing. */ }
  }
};
if (document.querySelector('[data-result="posted"]')) tabState.write('post', null);
if (document.querySelector('[data-result="answered"]')) {
  tabState.write('reply-' + location.pathname.split('/').pop(), null);
}
const editor = document.querySelector('[data-draft]');
if (editor) {
  const fields = [...editor.querySelectorAll('[maxlength], select[name=category]')];
  const saved = tabState.read(editor.dataset.draft);
  for (const field of fields) {
    if (typeof saved?.[field.name] === 'string') field.value = saved[field.name];
    field.dispatchEvent(new Event('input'));
  }
  editor.addEventListener('input', () => {
    tabState.write(editor.dataset.draft, Object.fromEntries(fields.map(f => [f.name, f.value])));
  });
}
for (const area of document.querySelectorAll('textarea')) {
  const grow = () => {
    area.style.height = 'auto';
    area.style.height = Math.min(area.scrollHeight + 2, Math.max(180, innerHeight * .55)) + 'px';
  };
  grow();
  area.addEventListener('input', grow);
}
if (imageInput) {
  const preview = document.querySelector('#image-preview');
  const remove = document.querySelector('#remove-image');
  let objectURL;
  imageInput.addEventListener('change', () => {
    if (objectURL) URL.revokeObjectURL(objectURL);
    preview.removeAttribute('src');
    remove.hidden = !imageInput.files.length;
    preview.hidden = remove.hidden || !imageInput.validity.valid;
    if (!preview.hidden) {
      objectURL = URL.createObjectURL(imageInput.files[0]);
      preview.src = objectURL;
    }
  });
  remove.addEventListener('click', () => {
    imageInput.value = '';
    imageInput.dispatchEvent(new Event('change'));
    imageInput.focus();
  });
}

const filters = document.querySelector('#search-form');
if (filters) {
  const sheet = document.querySelector('#filter-sheet');
  const trigger = document.querySelector('#open-filters');
  const options = document.querySelector('#filter-options');
  const slot = document.querySelector('#sheet-fields');
  const mobile = matchMedia('(max-width: 760px)');
  function layoutFilters() {
    if (sheet.open) sheet.close();
    trigger.hidden = !mobile.matches;
    if (mobile.matches) slot.append(options);
    else trigger.after(options);
  }
  if (typeof sheet.showModal === 'function') {
    layoutFilters();
    mobile.addEventListener('change', layoutFilters);
    let sort, unanswered;
    trigger.addEventListener('click', () => {
      sort = filters.elements.sort.value;
      unanswered = filters.elements.unanswered.checked;
      sheet.returnValue = '';
      sheet.showModal();
    });
    document.querySelector('#close-filters').onclick = () => sheet.close();
    document.querySelector('#apply-filters').onclick = () => {
      sheet.close('apply');
      filters.requestSubmit();
    };
    sheet.addEventListener('close', () => {
      if (sheet.returnValue !== 'apply') {
        filters.elements.sort.value = sort;
        filters.elements.unanswered.checked = unanswered;
      }
    });
  }
  const listURL = location.pathname + location.search;
  tabState.write('list', listURL);
  const reading = tabState.read('reading');
  if (reading?.url === listURL) {
    requestAnimationFrame(() => window.scrollTo(0, reading.y));
    tabState.write('reading', null);
  }
  document.addEventListener('click', e => {
    if (e.target.closest('a[href^="/p/"],a[href="/new"]')) {
      tabState.write('reading', {url: listURL, y: scrollY});
    }
  });
  if (location.hash === '#keyword') document.querySelector('#keyword').focus();
  const url = new URL(location.href);
  if (url.searchParams.get('view') === 'search' || url.searchParams.get('q')) {
    url.searchParams.set('view','search');
    tabState.write('search', '/?' + url.searchParams + '#keyword');
  }
  const clear = filters.querySelector('a[href="/"]');
  clear?.addEventListener('click', () => tabState.write('search', null));
}
const list = tabState.read('list');
if (typeof list === 'string' && (list === '/' || list.startsWith('/?'))) {
  document.querySelectorAll('[data-list-back]').forEach(link => { link.href = list; });
  if (location.pathname.startsWith('/p/')) {
    const query = new URL(list, location.origin).searchParams;
    const section = query.get('view') === 'mine' ? 'mine'
      : query.get('view') === 'search' || query.get('q') ? 'search'
      : query.get('unanswered') ? 'unanswered' : 'home';
    document.querySelector('.bottom-nav [aria-current]')?.removeAttribute('aria-current');
    document.querySelector('.dest-' + section).setAttribute('aria-current', 'location');
  }
}
const lastSearch = tabState.read('search');
if (typeof lastSearch === 'string' && lastSearch.startsWith('/?')) {
  document.querySelector('.dest-search').href = lastSearch;
}
let restingHeight = window.innerHeight;
function updateKeyboard() {
  const editing = document.activeElement?.matches('textarea,input:not([type=checkbox]):not([type=file])');
  const height = window.visualViewport?.height || innerHeight;
  if (!editing) restingHeight = innerHeight;
  document.body.classList.toggle('keyboard-open', Boolean(editing && restingHeight - height > 100));
}
window.visualViewport?.addEventListener('resize', updateKeyboard);
window.addEventListener('resize', updateKeyboard);
document.addEventListener('focusin', updateKeyboard);
document.addEventListener('focusout', () => requestAnimationFrame(updateKeyboard));
