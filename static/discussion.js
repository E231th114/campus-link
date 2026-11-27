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
  trigger.onclick = () => {
    picker.showModal();
    if (!mobile.matches) {
      const rect = trigger.getBoundingClientRect();
      picker.style.left = Math.max(8, Math.min(innerWidth - picker.offsetWidth - 8, rect.left)) + 'px';
      picker.style.top = Math.max(8, Math.min(innerHeight - picker.offsetHeight - 8, rect.bottom + 4)) + 'px';
    }
    document.documentElement.classList.add('emoji-open');
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
  let busy = false;
  bar.addEventListener('click', async event => {
    const clicked = event.target.closest('button[data-code]');
    if (!clicked || busy) return;
    const code = clicked.dataset.code;
    const option = picker.querySelector('[data-code="' + code + '"]');
    const data = new URLSearchParams({csrf: bar.dataset.csrf, emoji: code,
      revision: option.dataset.revision, active: option.getAttribute('aria-pressed') === 'true' ? '0' : '1'});
    if (picker.open) picker.close();
    busy = true;
    bar.setAttribute('aria-busy', 'true');
    feedback.textContent = '更新中…';
    try {
      const response = await fetch(bar.dataset.api, {method:'POST', body:data});
      if (!response.ok) throw new Error(response.status === 429 ? '少し待ってからもう一度お試しください。' : '更新できませんでした。ページを確認してもう一度お試しください。');
      const state = await response.json();
      for (const button of picker.querySelectorAll('[data-code]')) {
        const value = state[button.dataset.code];
        const chip = bar.querySelector('.emoji-chip[data-code="' + button.dataset.code + '"]');
        button.dataset.revision = value.revision;
        button.setAttribute('aria-pressed', value.mine);
        chip.setAttribute('aria-pressed', value.mine);
        chip.setAttribute('aria-label', button.dataset.label + ' ' + value.count + '件');
        chip.querySelector('span').textContent = value.count;
        if (document.activeElement === chip && !value.count) trigger.focus();
        chip.hidden = !value.count;
      }
      feedback.textContent = '';
    } catch (err) {
      feedback.textContent = err instanceof TypeError ? '通信できませんでした。接続を確認して再度お試しください。' : err.message;
    } finally {
      busy = false;
      bar.removeAttribute('aria-busy');
    }
  });
}
