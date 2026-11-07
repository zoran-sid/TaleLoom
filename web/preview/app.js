import './style.css';
import { GameClient } from '../runtime/client.js';
import { readSave, writeSave } from './storage.js';

const $ = (id) => document.getElementById(id);
const descriptions = {
  fog_harbor: '天亮之前，在海鸥旅馆寻找命案背后的真相。',
  deep_space: '氧气正在流失。搜集道具，找到离开“回声号”的办法。',
};
let client;
let sessionId;
let view;
let busy = false;
let catalog = [];
let retry;
let dirty = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text, handler, className) {
  const node = element('button', text, className);
  node.addEventListener('click', handler);
  return node;
}
function status(message = '', canRetry = false) {
  $('status').textContent = message;
  $('status-panel').hidden = !message;
  $('retry').hidden = !canRetry;
}
function setBusy(value) {
  busy = value;
  $('app').setAttribute('aria-busy', String(value));
  document.querySelectorAll('#app button, #app select, #app input').forEach((node) => {
    node.disabled = value || node.dataset.unavailable === 'true';
  });
}
async function run(action) {
  if (busy) return;
  setBusy(true);
  status();
  try { await action(); }
  catch (error) {
    console.error(error);
    status(error.message.startsWith('本机') || error.message.startsWith('无法读取本机')
      ? error.message : '操作未完成。请重试；已有存档可以继续读取。', Boolean(retry));
  } finally { setBusy(false); }
}
function request(method, data = {}) {
  return client.call({ method, session_id: sessionId, ...data });
}
function renderLibrary() {
  $('stories').replaceChildren();
  let storageWarning = '';
  catalog.forEach((story, index) => {
    const row = element('article', undefined, 'story');
    row.dataset.story = story.id;
    row.append(element('span', String(index + 1).padStart(2, '0'), 'story-number'));
    const detail = element('div');
    detail.append(element('p', story.genre, 'genre'), element('h3', story.title),
      element('p', descriptions[story.id] || '选择你的行动，探索故事的走向。'));
    const buttons = element('div', undefined, 'story-buttons');
    buttons.append(button('开始阅读 →', () => run(() => start(story.id)), 'primary'));
    try {
      if (readSave(story.id)) buttons.append(button('继续阅读', () => run(() => start(story.id, true))));
    } catch (error) { storageWarning = error.message; }
    row.append(detail, buttons);
    $('stories').append(row);
  });
  if (storageWarning) status(storageWarning);
}
async function loadCatalog() {
  retry = loadCatalog;
  const response = await fetch('/catalog.json', { cache: 'no-cache' });
  if (!response.ok) throw new Error('无法读取书架');
  catalog = await response.json();
  renderLibrary();
  retry = undefined;
}
async function start(storyId, resume = false) {
  retry = () => start(storyId, resume);
  const payload = resume ? readSave(storyId) : null;
  if (resume && !payload) { status('本机还没有这个故事的存档。'); return; }
  status('正在打开故事。首次加载需要下载游戏运行环境，请稍候。');
  client?.close();
  client = new GameClient();
  sessionId = crypto.randomUUID();
  let result = await request('start', { story_id: storyId });
  if (payload) result = await request('restore', { payload });
  $('library').hidden = true;
  $('game').hidden = false;
  render(result);
  dirty = false;
  if (result.error_code !== null) status(result.messages.join('\n'));
  else status();
  retry = undefined;
  $('scene-title').focus();
}
function render(result) {
  if (result.view?.protocol_version !== 1) throw new Error('网页协议版本不匹配，请刷新页面。');
  view = result.view;
  $('story-title').textContent = view.story_title;
  $('scene-title').textContent = view.scene_title;
  $('scene-text').textContent = view.text;
  $('chapter').textContent = view.ended ? `结局 · ${view.ending_title || view.ending_id}` : '故事进行中';
  $('chapter').dataset.ending = view.ending_id || '';
  $('turn').textContent = `第 ${view.turn} 回合`;
  $('messages').textContent = result.messages.join('\n');
  $('choices').replaceChildren();
  $('choice-section').hidden = view.ended || !view.choices.length;
  for (const choice of view.choices) {
    const node = button(choice.label, () => act(choice.id), 'choice');
    node.dataset.action = choice.id;
    node.disabled = !choice.enabled;
    node.dataset.unavailable = String(!choice.enabled);
    $('choices').append(node);
  }
  $('actions').replaceChildren();
  for (const action of view.actions) {
    const form = element('form', undefined, 'action-form');
    form.dataset.action = action.id;
    form.append(element('h3', action.label));
    const fields = element('div', undefined, 'action-fields');
    for (const parameter of action.parameters) {
      const label = element('label', parameter.label);
      const select = element(parameter.kind === 'text' ? 'input' : 'select');
      select.name = parameter.key;
      select.required = parameter.required;
      for (const option of parameter.kind === 'text' ? [] : parameter.options) {
        const node = element('option', option.label);
        node.value = option.id;
        select.append(node);
      }
      if (parameter.key === 'second' && select.options?.length > 1) select.selectedIndex = 1;
      label.append(select);
      fields.append(label);
    }
    const submit = element('button', action.label);
    submit.type = 'submit';
    submit.dataset.unavailable = String(!action.enabled);
    fields.append(submit);
    form.append(fields);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (busy) return;
      if (action.id === 'mystery:accuse' && !confirm('这次指认将决定故事结局。确定作出指认吗？')) return;
      act(action.id, Object.fromEntries(new FormData(form)));
    });
    $('actions').append(form);
  }
  renderNotes('inventory', view.inventory, '尚未携带物品。');
  renderNotes('clues', view.clues, '还没有发现线索。');
  $('resources').replaceChildren();
  for (const resource of view.resources) {
    const row = element('div', undefined, 'resource');
    row.append(element('span', resource.label), element('strong', String(resource.value)));
    $('resources').append(row);
  }
  $('ending').hidden = !view.ended;
  setBusy(busy);
}
function renderNotes(id, items, empty) {
  $(id).replaceChildren();
  if (!items.length) { $(id).append(element('p', empty, 'empty')); return; }
  for (const item of items) {
    const row = element('div', undefined, 'note-item');
    row.append(element('strong', item.label));
    if (item.description) row.append(element('p', item.description));
    $(id).append(row);
  }
}
function act(actionId, values = {}) {
  return run(async () => {
    const result = await request('action', { action: { action_id: actionId, expected_revision: view.revision, values } });
    render(result);
    if (result.error_code === null) dirty = true;
    $('scene-title').focus();
  });
}
function home() {
  if (busy) return;
  if (dirty && !confirm('返回书架会离开当前未保存的进度。确定返回吗？')) return;
  client?.close();
  client = null;
  view = null;
  dirty = false;
  $('game').hidden = true;
  $('library').hidden = false;
  status();
  renderLibrary();
}
$('home').onclick = home;
$('finish').onclick = home;
$('retry').onclick = () => run(() => retry?.());
$('restart').onclick = () => {
  if (confirm('重新开始当前故事？已保存的存档会保留。')) run(() => start(view.story_id));
};
$('save').onclick = () => run(async () => {
  if (readSave(view.story_id) && !confirm('覆盖这个故事在本机保存的进度吗？')) return;
  writeSave(view.story_id, await request('export'));
  dirty = false;
  status('进度已保存在当前浏览器。可以导出 JSON 文件带到其他设备。');
});
$('load').onclick = () => run(async () => {
  const payload = readSave(view.story_id);
  if (!payload) { status('本机还没有这个故事的存档。'); return; }
  if (!confirm('读取存档并替换当前未保存的进度吗？')) return;
  const result = await request('restore', { payload });
  render(result);
  if (result.error_code === null) dirty = false;
  status(result.error_code === null ? '已恢复保存的进度。' : result.messages.join('\n'));
});
$('export').onclick = () => run(async () => {
  const payload = await request('export');
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
  const link = element('a');
  link.href = url;
  link.download = `taleloom-${view.story_id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  status('存档已导出。请保留 JSON 文件以便继续游戏。');
});
$('import').onclick = () => { $('import-file').value = ''; $('import-file').click(); };
$('import-file').onchange = () => run(async () => {
  const file = $('import-file').files[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) { status('存档文件过大，请选择小于 2 MB 的 JSON 存档。'); return; }
  let payload;
  try { payload = JSON.parse(await file.text()); }
  catch { status('无法读取这个 JSON 文件，当前进度已保留。'); return; }
  if (!confirm('导入存档并替换当前未保存的进度吗？')) return;
  const result = await request('restore', { payload });
  render(result);
  if (result.error_code === null) dirty = true;
  status(result.error_code === null ? '存档已导入。点击“保存进度”可保存在本机。' : result.messages.join('\n'));
});
window.addEventListener('pagehide', () => client?.close());
window.addEventListener('beforeunload', (event) => {
  if (dirty) { event.preventDefault(); event.returnValue = ''; }
});
run(loadCatalog);
