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
import { readSave, writeSave, describeSaves } from '../storage/index.js';
import { worldOf, drawWorld, drawFilm, scenePlateKey, drawScenePlate } from './art.js';

function hasSave(storyId, slot = 'quick') {
  try {
    return readSave(storyId, slot) !== null;
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
let sceneKey = null;
let plateKey = null;
let resourceValues = new Map();

/** 重新触发一次样式动画（翻页、配图切换、数值变化）。 */
function replay(node, name) {
  node.classList.remove(name);
  void node.offsetWidth;
  node.classList.add(name);
}

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
    const world = worldOf(story.id);
    if (world) row.dataset.world = world;
    row.style.setProperty('--i', String(index));
    const thumb = drawWorld(element('div', undefined, 'story-thumb'), world, story.title);
    const detail = element('div');
    detail.append(element('p', story.genre, 'genre'), element('h3', story.title),
      element('p', descriptions[story.id] || '选择你的行动，探索故事的走向。'));
    const buttons = element('div', undefined, 'story-buttons');
    buttons.append(button('开始阅读 →', () => run(() => start(story.id)), 'primary'));
    try {
      if (hasSave(story.id) || hasSave(story.id, 'auto')) buttons.append(button('继续阅读', () => run(() => start(story.id, true))));
    } catch (error) {
      status(error.message);
    }
    row.append(thumb, detail, buttons);
    $('stories').append(row);
  }
  $('films').replaceChildren(...FILMS.map(cinematicCard));
}

/** 影像版剧本不在书架目录里（不在桌面和命令行出现），在影像模式推荐位各给一个入口。 */
const FILMS = [
  { id: 'fog_harbor_ledger', href: '/cinematic', genre: '互动影像 · 推理搜证', title: '雾港旧案：未结的账',
    text: '一九三一年的雾港旅馆：查看现场、核对账目、比对证词，在天亮前把问题说完整。' },
  { id: 'deep_space_film', href: '/cinematic?story=deep_space_film', genre: '互动影像 · 资源与解谜', title: '深空回声 · 影像版',
    text: '氧气和电量都在下降：在耗尽之前找到离开回声号的办法，选错会付出代价。' },
];

/** 影像模式入口：不是会话剧本，只链到 /cinematic，不读取存档。题图是版画处理后的剧照。 */
function cinematicCard(film) {
  const card = element('article', undefined, 'film reveal');
  card.dataset.cinematic = film.id;
  const world = worldOf(film.id);
  if (world) card.dataset.world = world;
  const link = element('a', '进入影像模式 →', 'cinematic-link');
  link.href = film.href;
  card.append(drawFilm(element('div', undefined, 'film-plate'), film.id),
    element('p', film.genre, 'genre'), element('h3', film.title), element('p', film.text, 'film-text'), link);
  return card;
}

async function start(storyId, resume = false) {
  retry = () => start(storyId, resume);
  let payload = null;
  if (resume) {
    const candidates = [];
    for (const slot of ['quick', 'auto']) {
      try { const data = readSave(storyId, slot); if (data) candidates.push(data); } catch { /* 另一个槽仍可恢复。 */ }
    }
    candidates.sort((a, b) => (Date.parse(b.saved_at) || 0) - (Date.parse(a.saved_at) || 0));
    payload = candidates[0] ?? null;
  }
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
  const world = worldOf(storyId);
  if (world) $('game').dataset.world = world;
  else delete $('game').dataset.world;
  sceneKey = null;
  plateKey = null;
  resourceValues = new Map();
  window.scrollTo(0, 0);
  render(result);
  dirty = payload === null || result.error_code !== null;
  status(result.error_code === null ? '' : result.messages.join('\n'));
  retry = null;
  $('scene-title').focus({ preventScroll: true });
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
  renderScenePlate();
  const nextScene = `${view.story_id}/${view.scene_id}/${view.ended}`;
  if (nextScene !== sceneKey) {
    sceneKey = nextScene;
    replay(document.querySelector('.page'), 'turning');
  }

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

/** 场景配图：有对应剧照用版画处理后的剧照，否则用故事的几何版画；未登记的故事不显示。 */
function renderScenePlate() {
  const key = scenePlateKey(view.story_id, view.scene_id);
  if (key === plateKey) return;
  plateKey = key;
  const plate = $('scene-plate');
  plate.hidden = key === null;
  if (key === null) return;
  drawScenePlate(plate, view.story_id, key);
  replay(plate, 'fresh');
}

function renderResources(resources) {
  $('resources').replaceChildren();
  const seen = new Map();
  for (const resource of resources) {
    const row = element('div', undefined, 'resource');
    row.dataset.resource = resource.id;
    const limited = resource.maximum !== null && resource.maximum !== undefined;
    const value = element('strong', limited ? `${resource.value} / ${resource.maximum}` : String(resource.value));
    if (resourceValues.has(resource.id) && resourceValues.get(resource.id) !== resource.value) value.className = 'changed';
    seen.set(resource.id, resource.value);
    row.append(element('span', resource.label), value);
    if (limited && resource.maximum > 0) {
      const fill = Math.max(0, Math.min(1, resource.value / resource.maximum));
      const meter = element('div', undefined, 'meter');
      const bar = element('i');
      bar.style.setProperty('--fill', String(fill));
      meter.append(bar);
      row.classList.toggle('low', fill <= 0.25);
      row.append(meter);
    }
    $('resources').append(row);
  }
  resourceValues = seen;
}

function act(actionId, values = {}) {
  return run(async () => {
    setBusy(true);
    const previousRevision = view.revision;
    const result = await session.dispatch(actionId, view.revision, values);
    render(result);
    if (result.error_code === null) {
      dirty = true;
      if (view.revision !== previousRevision) {
        try { writeSave(view.story_id, await session.exportSave(), 'auto'); }
        catch (error) { status('自动存档失败：' + error.message); return; }
      }
    }
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
  $('save-menu').open = false;
  $('save-list').hidden = true;
  $('game').hidden = true;
  $('library').hidden = false;
  status();
  renderLibrary();
}

function restart() {
  if (confirm('重新开始当前故事？已保存的存档会保留。')) run(() => start(view.story_id));
}

// 存档菜单：点菜单以外的地方或按 Esc 收起。
document.addEventListener('click', (event) => {
  const menu = $('save-menu');
  if (menu.open && !menu.contains(event.target)) menu.open = false;
});
document.addEventListener('keydown', (event) => {
  const menu = $('save-menu');
  if (event.key !== 'Escape' || !menu.open) return;
  menu.open = false;
  menu.querySelector('summary').focus();
});

$('save-list-button').onclick = () => run(async () => {
  const rows = describeSaves(view.story_id);
  $('save-list').textContent = rows.map(r => `${r.slot} · ${r.saved_at ? new Date(r.saved_at).toLocaleString() : '旧存档时间未知'} · 场景 ${r.scene || '?'} · 回合 ${r.turn ?? '?'} ${r.error || ''}`).join('\n') || '还没有存档。';
  $('save-list').hidden = false;
});
$('home').onclick = home;
$('finish').onclick = home;
$('retry').onclick = () => run(() => retry?.());
$('restart').onclick = restart;

$('save').onclick = () => run(async () => {
  if (hasSave(view.story_id, $('save-slot').value) && !confirm('覆盖这个故事在本机保存的进度吗？')) return;
  writeSave(view.story_id, await session.exportSave(), $('save-slot').value);
  dirty = false;
  status('进度已保存在当前浏览器。可以导出 JSON 文件带到其他设备。');
});

$('load').onclick = () => run(async () => {
  let payload;
  try {
    payload = readSave(view.story_id, $('save-slot').value);
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

drawWorld($('plate-fog'), 'fog');
drawWorld($('plate-deep'), 'deep');
fixture = fixtureRequested();
run(loadCatalog);
