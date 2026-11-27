function minimumJST() {
  return new Date(Date.now() + 9 * 3600000 + 60000).toISOString().slice(0, 16);
}
for (const select of document.querySelectorAll('[name=deadline_mode]')) {
  const input = select.form.elements.deadline_custom;
  function sync() {
    input.disabled = select.value !== 'custom';
    input.required = !input.disabled;
    input.closest('label').hidden = input.disabled;
    input.min = minimumJST();
  }
  select.addEventListener('change', sync);
  window.addEventListener('pageshow', sync);
  input.addEventListener('focus', sync);
  sync();
}

const clocks = [...document.querySelectorAll('[data-availability]')].filter(el => +el.dataset.availability);
function updateClocks() {
  for (const el of clocks) {
    const left = Number(el.dataset.availability) - Date.now() / 1000;
    const [unit, label] = left >= 86400 ? [86400, '日'] : left >= 3600 ? [3600, '時間'] : [60, '分'];
    el.querySelector('[data-remaining]').textContent = left > 0 ? ' · 残り' + Math.ceil(left / unit) + label : '';
    if (el.dataset.fixed === '1') continue;
    el.querySelector('[data-status]').textContent = left <= 0 ? '回答受付終了' : left <= 3600 ? '期限間近' : '回答受付中';
    const note = document.querySelector('[data-expiry-note]');
    if (left <= 0 && note && !note.textContent) {
      note.textContent = '回答期限を迎えました。入力した内容はこの画面で確認できます。';
      note.closest('form').querySelector('button[type=submit],button.button').disabled = true;
    }
  }
}
if (clocks.length) {
  updateClocks();
  window.setInterval(updateClocks, 1000);
  document.addEventListener('visibilitychange', updateClocks);
}

const bar = document.querySelector('.emoji-bar');
if (bar) {
  const picker = bar.querySelector('dialog');
  const trigger = bar.querySelector('#emoji-open');
  const feedback = document.querySelector('#emoji-feedback');
  const mobile = matchMedia('(max-width:760px)');
  trigger.onclick = async () => {
    picker.showModal();
    document.documentElement.classList.add('emoji-open');
    try { await loadCatalog(); render(); positionPicker(); } catch { note.textContent = '一覧を読み込めませんでした。閉じてもう一度お試しください。'; }
  };
  picker.addEventListener('close', () => {
    document.documentElement.classList.remove('emoji-open');
    picker.style.left = picker.style.top = '';
    trigger.focus();
  });
  mobile.addEventListener('change', () => { if (picker.open) picker.close(); });
  picker.querySelector('#emoji-close').onclick = () => picker.close();
  picker.addEventListener('click', event => {
    const r = picker.getBoundingClientRect();
    if (event.target === picker && (event.clientX < r.left || event.clientX > r.right ||
        event.clientY < r.top || event.clientY > r.bottom)) picker.close();
  });
  function positionPicker() {
    if (!mobile.matches) {
      const rect = trigger.getBoundingClientRect();
      picker.style.left = Math.max(8, Math.min(innerWidth - picker.offsetWidth - 8, rect.left)) + 'px';
      picker.style.top = Math.max(8, Math.min(innerHeight - picker.offsetHeight - 8, rect.bottom + 4)) + 'px';
    }
  }
  const query = picker.querySelector('#emoji-query');
  const group = picker.querySelector('#emoji-group');
  const note = picker.querySelector('#picker-note');
  const more = picker.querySelector('#emoji-more');
  const grid = picker.querySelector('.emoji-grid');
  const groups = {'Smileys & Emotion':'表情・感情', 'People & Body':'人・身体（肌の色を含む）',
    'Animals & Nature':'動物・自然', 'Food & Drink':'食べ物・飲み物', 'Travel & Places':'旅行・場所',
    Activities:'活動', Objects:'もの', Symbols:'記号', Flags:'旗'};
  let catalog, recommended, pending, busy = false, limit = 48;
  let state = JSON.parse(document.querySelector('#emoji-state').textContent);
  function recent() {
    try { return JSON.parse(localStorage.getItem('campus:recent-emoji') || '[]').filter(code => catalog.has(code)); }
    catch { return []; }
  }
  async function loadCatalog() {
    if (catalog) return;
    if (!pending) pending = fetch(bar.dataset.catalog).then(async response => {
      if (!response.ok) throw Error();
      const data = await response.json();
      catalog = new Map(data.items.map(([code,glyph,name,category]) => [code,{glyph,name,category}]));
      recommended = data.recommended;
      for (const [value,label] of [['recommended','おすすめ'],['recent','最近使用'],['all','すべて'],
        ...Object.entries(groups)]) group.add(new Option(label,value));
    }).finally(() => { pending = null; });
    await pending;
  }
  function button(code, chip) {
    const {glyph,name} = catalog.get(code);
    const value = state[code];
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.code = code;
    b.title = name;
    b.setAttribute('aria-label', chip ? name + ' ' + value.count + '件' : name);
    b.setAttribute('aria-pressed', Boolean(value?.mine));
    b.textContent = chip ? glyph + ' ' + value.count : glyph;
    if (chip) b.className = 'emoji-chip';
    return b;
  }
  function render() {
    if (!catalog) return;
    const term = query.value.trim().normalize('NFC').replace(/[\uFE0E\uFE0F]/gu,'').toLowerCase();
    let codes;
    if (term) codes = [...catalog.keys()].filter(code => {
      const {name,glyph} = catalog.get(code);
      return name.toLowerCase().includes(term) || glyph.replace(/\uFE0F/gu,'') === term;
    });
    else if (group.value === 'recent') codes = recent();
    else if (group.value === 'recommended') codes = recommended;
    else codes = [...catalog.keys()].filter(code => group.value === 'all' || catalog.get(code).category === group.value);
    grid.replaceChildren(...codes.slice(0,limit).map(code => button(code,false)));
    const report = picker.querySelector('#emoji-report');
    const reportOptions = Object.keys(state).filter(code => state[code].count && catalog.has(code));
    report.hidden = !reportOptions.length;
    report.querySelector('select').replaceChildren(...reportOptions.map(code => {
      const {glyph,name} = catalog.get(code);
      return new Option(glyph + ' ' + name,code);
    }));
    more.hidden = codes.length <= limit;
    note.textContent = codes.length ? '' : term && /\p{Extended_Pictographic}/u.test(term)
      ? 'この絵文字はCampus Linkでは使用できません。' : '該当する絵文字はありません。';
  }
  query.oninput = () => { limit = 48; render(); };
  group.onchange = () => { query.value = ''; limit = 48; render(); };
  more.onclick = () => { limit += 48; render(); };
  bar.addEventListener('click', async event => {
    const clicked = event.target.closest('button[data-code]');
    if (!clicked || busy) return;
    busy = true;
    const code = clicked.dataset.code;
    const data = new URLSearchParams({csrf: bar.dataset.csrf, emoji: code,
      revision: state[code]?.revision || 0, active: state[code]?.mine ? '0' : '1'});
    if (picker.open) picker.close();
    bar.setAttribute('aria-busy','true');
    feedback.textContent = '更新中…';
    try {
      await loadCatalog();
      const response = await fetch(bar.dataset.api, {method:'POST', body:data});
      if (!response.ok) throw Error(response.status === 400 ? 'この絵文字はCampus Linkでは使用できません。'
        : response.status === 429 ? '少し待ってからもう一度お試しください。' : '更新できませんでした。');
      state = await response.json();
      if (state[code]?.mine && catalog.has(code)) {
        try { localStorage.setItem('campus:recent-emoji',JSON.stringify([code,...recent().filter(c=>c!==code)].slice(0,24))); } catch {}
      }
      bar.querySelectorAll('.emoji-chip').forEach(chip => chip.remove());
      for (const [key,value] of Object.entries(state)) {
        if (value.count && catalog.has(key)) bar.insertBefore(button(key,true),picker);
      }
      if (!picker.open) trigger.focus();
      render();
      feedback.textContent = '';
    } catch (err) {
      feedback.textContent = err.message || '通信できませんでした。接続を確認してください。';
    } finally {
      busy = false;
      bar.removeAttribute('aria-busy');
    }
  });
}
