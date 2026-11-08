/**
 * 网页端展示与交互。负责人：ZRS。
 *
 * 页面只渲染会话返回的快照：场景正文、可点击选项、带参数的动作、
 * 背包／线索／资源、存读档与结局。规则全部在 Python 核心中；这里不拼
 * 中文命令，也不读取引擎状态。请求串行执行，处理中禁用所有可重复提交的控件。
 */
import '../styles/ui.css';
import {
  FixtureSession, RemoteSession, FIXTURE_STORY, fixtureRequested,
} from './session.js';
// 暂时复用 ZC 的单槽存储；LQ 交付 web/storage/ 后只改这一处导入。
import { readSave, writeSave } from '../preview/storage.js';

function hasSave(storyId) {
  try {
    return readSave(storyId) !== null;
  } catch {
    return false;
  }
}

const $ = (id) => document.getElementById(id);
const descriptions = {
  fog_harbor: '天亮之前，在海鸥旅馆寻找命案背后的真相。',
  deep_space: '氧气正在流失。搜集道具，找到离开“回声号”的办法。',
};

let session = null;
let view = null;
let busy = false;
let catalog = [];
let dirty = false;
let retry = null;
let fixture = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function button(text, handler, className) {
  const node = element('button', text, className);
  node.type = 'button';
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
  try {
    await action();
  } catch (error) {
    console.error(error);
    const storage = error.message.startsWith('本机') || error.message.startsWith('无法读取本机');
    status(storage ? error.message : '操作未完成。请重试；已有存档可以继续读取。', Boolean(retry));
  } finally {
    setBusy(false);
  }
}

function closeSession() {
  session?.close?.();
  session = null;
}

async function loadCatalog() {
  retry = loadCatalog;
  if (fixture) {
    catalog = [{ ...FIXTURE_STORY }];
    renderLibrary();
    retry = null;
    return;
  }
  const response = await fetch('/catalog.json', { cache: 'no-cache' });
  if (!response.ok) throw new Error('无法读取书架');
  catalog = await response.json();
  renderLibrary();
  retry = null;
}

function renderLibrary() {
  $('stories').replaceChildren();
  for (const [index, story] of catalog.entries()) {
    const row = element('article', undefined, 'story');
    row.dataset.story = story.id;
    row.append(element('span', String(index + 1).padStart(2, '0'), 'story-number'));
    const detail = element('div');
    detail.append(element('p', story.genre, 'genre'), element('h3', story.title),
      element('p', descriptions[story.id] || '选择你的行动，探索故事的走向。'));
    const buttons = element('div', undefined, 'story-buttons');
    buttons.append(button('开始阅读 →', () => run(() => start(story.id)), 'primary'));
    try {
      if (hasSave(story.id)) buttons.append(button('继续阅读', () => run(() => start(story.id, true))));
    } catch (error) {
      status(error.message);
    }
    row.append(detail, buttons);
    $('stories').append(row);
  }
}

async function start(storyId, resume = false) {
  retry = () => start(storyId, resume);
  const payload = resume ? readSave(storyId) : null;
  if (resume && !payload) {
    status('本机还没有这个故事的存档。');
    return;
  }
  status(fixture ? '正在打开测试剧本。' : '正在打开故事。首次加载需要下载游戏运行环境，请稍候。');
  closeSession();
  session = fixture ? new FixtureSession(storyId) : new RemoteSession();
  let result = await session.start(storyId);
  if (payload) result = await session.restore(payload);
  $('library').hidden = true;
  $('game').hidden = false;
  render(result);
  dirty = payload === null || result.error_code !== null;
  status(result.error_code === null ? '' : result.messages.join('\n'));
  retry = null;
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

  $('choices').replaceChildren();
  $('choice-section').hidden = view.ended || !view.choices.length;
  for (const choice of view.choices) {
    const node = button(choice.label, () => act(choice.id), 'choice');
    node.dataset.action = choice.id;
    node.dataset.unavailable = String(!choice.enabled);
    $('choices').append(node);
  }

  $('actions').replaceChildren();
  for (const action of view.actions) {
    $('actions').append(actionForm(action));
  }

  renderNotes('inventory', view.inventory, '尚未携带物品。');
  renderNotes('clues', view.clues, '还没有发现线索。');
  renderResources(view.resources);
  $('ending').hidden = !view.ended;
  $('messages').textContent = result.messages.join('\n');
  setBusy(busy);
}

function actionForm(action) {
  const form = element('form', undefined, 'action-form');
  form.dataset.action = action.id;
  form.dataset.unavailable = String(!action.enabled);
  form.append(element('h3', action.label));
  if (action.disabled_reason) form.append(element('p', action.disabled_reason, 'hint'));
  const fields = element('div', undefined, 'action-fields');
  for (const parameter of action.parameters) {
    const label = element('label', parameter.label);
    let control;
    if (parameter.kind === 'text') {
      control = element('input');
      control.type = 'text';
    } else {
      control = element('select');
      for (const option of parameter.options) {
        const node = element('option', option.label);
        node.value = option.id;
        node.title = option.description || '';
        control.append(node);
      }
      if (parameter.key === 'second' && control.options.length > 1) control.selectedIndex = 1;
    }
    control.name = parameter.key;
    control.required = parameter.required;
    if (!action.enabled) control.disabled = true;
    label.append(control);
    fields.append(label);
  }
  const submit = element('button', action.label, undefined);
  submit.type = 'submit';
  submit.disabled = !action.enabled;
  submit.dataset.unavailable = String(!action.enabled);
  fields.append(submit);
  form.append(fields);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (busy) return;
    const values = Object.fromEntries(new FormData(form));
    for (const parameter of action.parameters) {
      if (parameter.required && !values[parameter.key]) {
        status(`请填写${parameter.label}。`);
        return;
      }
    }
    if (action.id === 'mystery:accuse' && !confirm('这次指认将决定故事结局。确定作出指认吗？')) return;
    act(action.id, values);
  });
  return form;
}

function renderNotes(id, items, empty) {
  $(id).replaceChildren();
  if (!items.length) {
    $(id).append(element('p', empty, 'empty'));
    return;
  }
  for (const item of items) {
    const row = element('div', undefined, 'note-item');
    row.dataset.item = item.id;
    row.append(element('strong', item.label));
    if (item.description) row.append(element('p', item.description));
    $(id).append(row);
  }
}

function renderResources(resources) {
  $('resources').replaceChildren();
  for (const resource of resources) {
    const row = element('div', undefined, 'resource');
    row.dataset.resource = resource.id;
    row.append(element('span', resource.label),
      element('strong', resource.maximum === null || resource.maximum === undefined
        ? String(resource.value) : `${resource.value} / ${resource.maximum}`));
    $('resources').append(row);
  }
}

function act(actionId, values = {}) {
  return run(async () => {
    setBusy(true);
    const result = await session.dispatch(actionId, view.revision, values);
    render(result);
    if (result.error_code === null) dirty = true;
    status(result.error_code === null ? '' : result.messages.join('\n'));
    $('scene-title').focus();
  });
}

function home() {
  if (busy) return;
  if (dirty && !confirm('返回书架会离开当前未保存的进度。确定返回吗？')) return;
  closeSession();
  view = null;
  dirty = false;
  $('game').hidden = true;
  $('library').hidden = false;
  status();
  renderLibrary();
}

function restart() {
  if (confirm('重新开始当前故事？已保存的存档会保留。')) run(() => start(view.story_id));
}

$('home').onclick = home;
$('finish').onclick = home;
$('retry').onclick = () => run(() => retry?.());
$('restart').onclick = restart;

$('save').onclick = () => run(async () => {
  if (hasSave(view.story_id) && !confirm('覆盖这个故事在本机保存的进度吗？')) return;
  writeSave(view.story_id, await session.exportSave());
  dirty = false;
  status('进度已保存在当前浏览器。可以导出 JSON 文件带到其他设备。');
});

$('load').onclick = () => run(async () => {
  let payload;
  try {
    payload = readSave(view.story_id);
  } catch (error) {
    status(error.message);
    return;
  }
  if (!payload) {
    status('本机还没有这个故事的存档。');
    return;
  }
  if (!confirm('读取存档并替换当前未保存的进度吗？')) return;
  const result = await session.restore(payload);
  render(result);
  if (result.error_code === null) dirty = false;
  status(result.error_code === null ? '已恢复保存的进度。' : result.messages.join('\n'));
});

$('export').onclick = () => run(async () => {
  const payload = await session.exportSave();
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
  const link = element('a');
  link.href = url;
  link.download = `taleloom-${view.story_id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  status('存档已导出。请保留 JSON 文件以便继续游戏。');
});

$('import').onclick = () => {
  $('import-file').value = '';
  $('import-file').click();
};

$('import-file').onchange = () => run(async () => {
  const file = $('import-file').files[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    status('存档文件过大，请选择小于 2 MB 的 JSON 存档。');
    return;
  }
  let payload;
  try {
    payload = JSON.parse(await file.text());
  } catch {
    status('无法读取这个 JSON 文件，当前进度已保留。');
    return;
  }
  if (!confirm('导入存档并替换当前未保存的进度吗？')) return;
  const result = await session.restore(payload);
  render(result);
  if (result.error_code === null) dirty = true;
  status(result.error_code === null ? '存档已导入。点击“保存进度”可保存在本机。' : result.messages.join('\n'));
});

window.addEventListener('pagehide', closeSession);
window.addEventListener('beforeunload', (event) => {
  if (dirty) {
    event.preventDefault();
    event.returnValue = '';
  }
});

fixture = fixtureRequested();
run(loadCatalog);
