document.addEventListener('submit', event => {
  const button = event.submitter;
  if (button) {
    button.disabled = true;
    button.textContent = '処理中…';
  }
});
window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
