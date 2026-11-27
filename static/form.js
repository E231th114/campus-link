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
