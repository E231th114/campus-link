const manual = document.querySelector('.manual');
const device = matchMedia('(max-width:760px)').matches ? 'phone' : 'pc';
manual.dataset.device = device;
manual.querySelector('input[value="' + device + '"]').checked = true;
manual.querySelector('.device-picker').addEventListener('change', event => {
  manual.dataset.device = event.target.value;
});

const steps = [
  ['すべての投稿', 'カテゴリ選択を開いてみましょう。', 'カテゴリ一覧が開きました。'],
  ['勉強', '質問を勉強カテゴリに絞りましょう。', '勉強カテゴリの質問が表示されました。'],
  ['定期テストの復習は何から始める？', 'タイトルを押して質問の詳細を読みましょう。', '「みんなの復習方法を教えてください。」という本文が開きました。'],
  ['参考になった 0', '役に立ったことを伝えてみましょう。', '「参考になった」が1件になりました。']
];
const get = id => document.getElementById(id);
const progressKey = 'campus:guide-practice';
let step = 0;
try { const n = Number(sessionStorage.getItem(progressKey)); if (Number.isInteger(n) && n >= 0 && n < steps.length) step = n; } catch {}
function remember() { try { sessionStorage.setItem(progressKey, String(step)); } catch {} }
function renderStep() {
  remember();
  get('tour-hint').textContent = (step + 1) + ' / ' + steps.length + '　' + steps[step][1];
  get('tour-target').textContent = steps[step][0];
  get('tour-target').disabled = false;
  get('tour-prev').disabled = step === 0;
  get('tour-next').textContent = step === steps.length - 1 ? '練習を完了' : '次へ';
  get('tour-target').focus();
}
function start() {
  get('tour').hidden = false;
  get('start-tour').hidden = true;
  get('restart-tour').hidden = true;
  renderStep();
}
function stop(complete) {
  if (complete) step = 0;
  remember();
  get('tour').hidden = true;
  get('start-tour').hidden = false;
  get('start-tour').textContent = complete ? '練習完了・もう一度練習する' : '続きから再開';
  get('restart-tour').hidden = complete;
  get('start-tour').focus();
}
if (step) {
  get('start-tour').textContent = '続きから再開';
  get('restart-tour').hidden = false;
}
get('start-tour').onclick = start;
get('restart-tour').onclick = () => { step = 0; start(); };
get('tour-target').onclick = () => {
  get('tour-hint').textContent = (step + 1) + ' / ' + steps.length + '　' + steps[step][2];
  if (step === 3) get('tour-target').textContent = '参考になった 1';
  get('tour-target').disabled = true;
  get('tour-next').focus();
};
get('tour-prev').onclick = () => { step--; renderStep(); };
function advance() {
  if (step === steps.length - 1) stop(true);
  else { step++; renderStep(); }
}
get('tour-next').onclick = advance;
get('tour-skip').onclick = advance;
get('tour-end').onclick = () => stop(false);
