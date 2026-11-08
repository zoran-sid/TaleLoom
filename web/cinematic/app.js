/**
 * 影像模式样片（《雾港旧案》）。负责人：ZC。
 *
 * 剧情、选项与判定全部来自浏览器里运行的同一个 Python 引擎（GameClient →
 * Pyodide Worker → session_factory 会话）；本页只把快照与反馈演成画面：
 * 场景转场、逐字字幕、审问特写、线索卡片和画面上的选项。不新增剧情文字。
 *
 * 默认播放影像版专用剧本 stories/film/fog_harbor_film（线性分支，不上书架）；
 * ?story=<id> 可以换成其他剧本，例如探索版 fog_harbor。
 *
 * 失败惩罚：每次选择前用会话的标准存档记一个检查点；到达 id 以 fail_ 开头的
 * 结局时，可以退回上一个选择重来，整局共 CHANCES 次机会，每次退回记一次失误。
 */
import './cinematic.css';
import { GameClient } from '../runtime/client.js';
import { Stage } from './stage.js';
import { Sound } from './sound.js';

const STORY_ID = new URLSearchParams(location.search).get('story') || 'fog_harbor_film';
const CHANCES = 3;
const FAST = new URLSearchParams(location.search).get('fast') === '1';
const T = (ms) => (FAST ? Math.min(ms, 40) : ms);
// 场景 → 画面：[画面名, 选项]。审问类节点用人物特写，speaker 作为字幕上的说话人。
const ART = {
  lobby: ['lobby'], ebb: ['lobby'], gathering: ['lobby', { gathering: true }],
  office: ['office'], office_ledger: ['office'], office_window: ['office'],
  kitchen: ['kitchen'], kitchen_zhou: ['kitchen'], vat: ['kitchen'],
  dock: ['harbor'], backyard: ['generic'],
  gu_first: ['portrait', { suspect: 'gu', place: 'lobby', speaker: '顾先生' }],
  gu_confront: ['portrait', { suspect: 'gu', place: 'lobby', speaker: '顾先生' }],
  gu_bluff: ['portrait', { suspect: 'gu', place: 'lobby', speaker: '顾先生' }],
  gu_silent: ['portrait', { suspect: 'gu', place: 'lobby', speaker: '顾先生' }],
  zhou_bluff: ['portrait', { suspect: 'zhou', place: 'kitchen', speaker: '周文' }],
  zhou_guarded: ['portrait', { suspect: 'zhou', place: 'kitchen', speaker: '周文' }],
  ayun_bluff: ['portrait', { suspect: 'ayun', place: 'kitchen', speaker: '阿芸' }],
  ayun_silent: ['generic', { speaker: '阿芸' }],
  zhou_gap: ['portrait', { suspect: 'zhou', place: 'kitchen', speaker: '周文' }],
  zhou_weight: ['portrait', { suspect: 'zhou', place: 'kitchen', speaker: '周文' }],
  kitchen_ayun: ['portrait', { suspect: 'ayun', place: 'kitchen', speaker: '阿芸' }],
  ayun_truth: ['portrait', { suspect: 'ayun', place: 'kitchen', speaker: '阿芸' }],
};
const AMBIENCE = { lobby: 'lobby', office: 'office', kitchen: 'kitchen', portrait: 'portrait', harbor: 'harbor' };
const SUSPECTS = { 顾先生: 'gu', 周文: 'zhou', 阿芸: 'ayun' };
const VERBS = { 'mystery:ask': '审问', 'mystery:examine': '深入调查', 'puzzle:use': '使用' };

const $ = (id) => document.getElementById(id);
const stage = new Stage($('stage'));
const sound = new Sound();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, T(ms)));

let client = null;
let sessionId = '';
let booting = null;
let view = null;
let busy = false;
let actTitle = '第一幕 · 雾夜';
let poke = null;
let paused = false;          // 打开笔记时暂停字幕与转场计时
let seen = new Set();        // 已经播过描述的场景，回来时不再重播
let notes = { clues: [], resources: [], sceneTitle: '', sceneText: '' };
let checkpoint = null;       // 上一个选择之前的标准存档
let chances = CHANCES;       // 剩余的“回到上一个选择”次数
let mistakes = 0;            // 本局退回过几次

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// ---------- 输入：点击画面或按空格跳过当前字幕 ----------

function nudge() {
  const next = poke;
  poke = null;
  if (next) next();
}

document.addEventListener('keydown', (event) => {
  if (event.target.closest('select')) return;
  if (event.key === 'Escape' && !$('notebook').hidden) {
    closeNotebook();
  } else if (event.key === 'n' || event.key === 'N') {
    toggleNotebook();
  } else if (!$('notebook').hidden) {
    return;
  } else if (event.key === ' ' && !event.target.closest('button')) {
    event.preventDefault();
    nudge();
  } else if (/^[1-9]$/.test(event.key) && !$('choices').hidden) {
    $('choices').querySelectorAll('button.choice')[Number(event.key) - 1]?.click();
  }
});
$('frame').addEventListener('click', (event) => { if (!event.target.closest('button') && $('notebook').hidden) nudge(); });
$('skip').addEventListener('click', nudge);

/** 等待 ms 毫秒或玩家点击；打开笔记期间不计时。 */
function hold(ms) {
  return new Promise((resolve) => {
    let left = T(ms);
    const timer = setInterval(() => {
      if (!paused) left -= 50;
      if (left <= 0) done();
    }, FAST ? 10 : 50);
    function done() {
      clearInterval(timer);
      if (poke === done) poke = null;
      resolve();
    }
    poke = done;
  });
}

async function whilePaused() {
  while (paused) await new Promise((resolve) => setTimeout(resolve, 80));
}

/** 逐字显示一行字幕，然后停留一会儿；点击可跳过。 */
async function type(text, speaker = '') {
  const box = $('subtitle');
  box.replaceChildren();
  if (speaker) box.append(el('span', 'speaker', speaker));
  const line = el('span', 'line', '');
  box.append(line);
  box.hidden = false;
  let skipped = FAST;
  poke = () => { skipped = true; };
  for (const ch of text) {
    await whilePaused();
    if (skipped) break;
    line.textContent += ch;
    await new Promise((resolve) => setTimeout(resolve, /[，。！？…；：、”]/.test(ch) ? 150 : 42));
  }
  line.textContent = text;
  poke = null;
  await hold(Math.min(1500 + text.length * 60, 5600));
}

function clearSubtitle() {
  $('subtitle').hidden = true;
  $('subtitle').replaceChildren();
}

/** 把场景正文切成适合字幕的短句（按换行与句号，每段不超过约 44 字）。 */
function chunks(text) {
  const out = [];
  for (const paragraph of text.split('\n').map((p) => p.trim()).filter(Boolean)) {
    let current = '';
    for (const sentence of paragraph.split(/(?<=[。！？…])(?![”」])/)) {
      if (current && (current + sentence).length > 44) {
        out.push(current);
        current = sentence;
      } else {
        current += sentence;
      }
    }
    if (current) out.push(current);
  }
  return out;
}

// ---------- 卡片 ----------

function showCard(kicker, title, place) {
  const card = $('card');
  card.replaceChildren(el('p', 'card-kicker', kicker), el('h2', 'card-title', title), el('p', 'card-place', place));
  card.hidden = false;
  requestAnimationFrame(() => card.classList.add('show'));
}

function hideCard() {
  const card = $('card');
  card.classList.remove('show');
  setTimeout(() => { if (!card.classList.contains('show')) card.hidden = true; }, T(700));
}

/** 嫌疑人起了戒心：红色提示卡，配低沉的一声。 */
async function warnCard(text) {
  sound.thud();
  const card = $('clue');
  card.classList.add('warn');
  card.replaceChildren(el('p', 'clue-kicker', '戒备'), el('p', 'clue-text', text));
  card.hidden = false;
  requestAnimationFrame(() => card.classList.add('show'));
  await hold(2400 + text.length * 45);
  card.classList.remove('show');
  await sleep(500);
  card.hidden = true;
  card.classList.remove('warn');
}

async function clueCard(name, text) {
  sound.bell();
  stage.flash();
  const card = $('clue');
  card.replaceChildren(el('p', 'clue-kicker', '获得线索'), el('h3', 'clue-name', name), el('p', 'clue-text', text));
  card.hidden = false;
  requestAnimationFrame(() => card.classList.add('show'));
  await hold(2600 + text.length * 45);
  card.classList.remove('show');
  await sleep(500);
  card.hidden = true;
}

// ---------- 把会话反馈拆成“镜头” ----------

function beatsFrom(messages) {
  const beats = [];
  for (const raw of messages) {
    const text = raw.trim();
    if (!text) continue;
    let m;
    if ((m = text.match(/^【戒备】(.+)$/))) {
      beats.push({ kind: 'warn', text: m[1] });
    } else if ((m = text.match(/^【获得线索】(.+?)：([\s\S]*)$/)) || (m = text.match(/^【获得线索】(.+)$/))) {
      beats.push({ kind: 'clue', name: m[1], text: m[2] || '' });
    } else if ((m = text.match(/^【审问】(.+?) · (.+)$/))) {
      beats.push({ kind: 'ask', who: m[1], topic: m[2], lines: [] });
    } else if ((m = text.match(/^【深入调查】(.+)$/))) {
      beats.push({ kind: 'examine', name: m[1], lines: [] });
    } else if ((m = text.match(/^—— (.+) ——$/))) {
      beats.push({ kind: 'act', title: m[1], lines: [] });
    } else {
      const last = beats.at(-1);
      if (last && last.lines) last.lines.push(text);
      else beats.push({ kind: 'line', text });
    }
  }
  return beats;
}

function artFor(sceneId) {
  const [name, options = {}] = ART[sceneId] || ['generic'];
  return { name, options };
}

function setArt(sceneId) {
  const { name, options } = artFor(sceneId);
  stage.show(name, options);
  sound.setAmbience(AMBIENCE[name] || 'generic');
}

async function interrogate(beat) {
  clearSubtitle();
  await stage.fade(1, T(450));
  stage.show('portrait', { suspect: SUSPECTS[beat.who] || 'zhou', place: view.scene_id });
  sound.setAmbience('portrait');
  $('caption').textContent = `审问 · ${beat.topic}`;
  $('caption').hidden = false;
  await stage.fade(0, T(800));
  for (const line of beat.lines) await type(line, beat.who);
  $('caption').hidden = true;
  clearSubtitle();
  await stage.fade(1, T(450));
  setArt(view.scene_id);
  await stage.fade(0, T(700));
}

async function play(messages) {
  await playBeats(beatsFrom(messages));
}

async function playBeats(beats) {
  for (const beat of beats) {
    if (beat.kind === 'clue') await clueCard(beat.name, beat.text);
    else if (beat.kind === 'warn') await warnCard(beat.text);
    else if (beat.kind === 'ask') await interrogate(beat);
    else if (beat.kind === 'examine') {
      for (const line of beat.lines) await type(line, `深入调查 · ${beat.name}`);
    } else if (beat.kind === 'act') {
      clearSubtitle();
      actTitle = beat.title;
      await stage.fade(1, T(900));
      sound.thud();
      showCard('', beat.title, '');
      await hold(2200);
      hideCard();
      for (const line of beat.lines.flatMap(chunks)) await type(line);
      clearSubtitle();
      if (!beat.keepDark) await stage.fade(0, T(1000));
    } else {
      await type(beat.text);
    }
  }
  clearSubtitle();
}

/** 首次进入：标题卡加完整描述；再次回来：只闪一下场景名，不重播描述。 */
async function enterScene(next) {
  clearSubtitle();
  const revisit = seen.has(next.scene_id);
  seen.add(next.scene_id);
  await stage.fade(1, T(revisit ? 450 : 700));
  if (!revisit) sound.thud();
  setArt(next.scene_id);
  if (revisit) {
    showCard('', next.scene_title, '');
    await stage.fade(0, T(700));
    await hold(700);
    hideCard();
    return;
  }
  showCard(actTitle, next.scene_title, '一九三一年 · 雾港');
  await hold(1800);
  hideCard();
  await stage.fade(0, T(1300));
  const { speaker = '' } = artFor(next.scene_id).options;
  for (const line of chunks(next.text)) await type(line, line.includes('“') ? speaker : '');
  clearSubtitle();
}

function isFailure(current) {
  return Boolean(current.ending_id && current.ending_id.startsWith('fail_'));
}

async function ending(next) {
  clearSubtitle();
  const failed = isFailure(next);
  await stage.fade(1, T(1200));
  stage.show('ending', { dawn: ['truth', 'dawn'].includes(next.ending_id) });
  sound.setAmbience('ending');
  await stage.fade(0, T(1800));
  for (const line of chunks(next.text)) await type(line);
  clearSubtitle();
  if (failed) {
    showCard('失败', next.ending_title || next.ending_id, chances > 0 ? `还剩 ${chances} 次机会` : '机会已经用完');
  } else {
    showCard('结局', next.ending_title || next.ending_id,
      mistakes ? `第 ${next.turn} 回合 · 失误 ${mistakes} 次` : `第 ${next.turn} 回合`);
  }
  const items = [];
  if (failed && chances > 0 && checkpoint) {
    items.push({ label: `回到上一个选择（还剩 ${chances} 次机会）`, run: rewind });
  }
  items.push({ label: failed ? '从头再来' : '重新开始', run: restart });
  items.push({ label: '返回文字版', run: () => { location.href = '/'; } });
  showChoices(items);
}

/** 退回上一个选择：恢复检查点存档，扣一次机会、记一次失误，直接回到选项。 */
async function rewind() {
  if (busy || !checkpoint || chances <= 0) return;
  busy = true;
  hideChoices();
  hideCard();
  try {
    const result = await call({ method: 'restore', payload: checkpoint });
    if (result.error_code) throw new Error(result.messages.join(' ') || '存档无法恢复');
    chances -= 1;
    mistakes += 1;
    updateChances();
    clearSubtitle();
    await stage.fade(1, T(600));
    sound.thud();
    view = result.view;
    updateNotes(view);
    setArt(view.scene_id);
    showCard('回到上一个选择', view.scene_title, `还剩 ${chances} 次机会`);
    await stage.fade(0, T(900));
    await hold(1400);
    hideCard();
    showChoices();
  } catch (error) {
    await type(`没能回到上一步：${error.message}`);
    clearSubtitle();
    showChoices([{ label: '从头再来', run: restart }]);
  } finally {
    busy = false;
  }
}

function updateChances() {
  $('chances').textContent = `机会 ${'●'.repeat(chances)}${'○'.repeat(CHANCES - chances)}`;
  $('chances').title = `还可以退回上一个选择 ${chances} 次`;
}

/** 先在原场景演完反馈，再转场；结束时进入结局画面。 */
async function present(result, previous) {
  const next = result.view;
  updateNotes(next);
  if (result.error_code) {
    view = next;
    await type(result.messages.join(' ') || '这一步没能完成。');
    clearSubtitle();
    return showChoices();
  }
  const moved = !previous || next.scene_id !== previous.scene_id;
  if (next.ended || !moved) {
    await play(result.messages);
    view = next;
    return next.ended ? ending(next) : showChoices();
  }
  // 换场：先放幕间标题，再进入新场景播描述，最后才弹出在新场景里获得的线索。
  const beats = beatsFrom(result.messages);
  await playBeats(beats.filter((b) => b.kind === 'act').map((b) => ({ ...b, keepDark: true })));
  view = next;
  await enterScene(next);
  await playBeats(beats.filter((b) => b.kind !== 'act'));
  return showChoices();
}

// ---------- 画面上的选项 ----------

function optionsFor(current) {
  const items = current.choices.filter((c) => c.enabled).map((c) => ({ label: c.label, run: () => act(c.id, {}) }));
  for (const action of current.actions) {
    if (!action.enabled) continue;
    const [only] = action.parameters;
    if (action.parameters.length === 1 && only.kind === 'select') {
      for (const option of only.options) {
        items.push({
          label: `${VERBS[action.id] || action.label}：${option.label}`,
          note: option.description === '已问过' ? '已问过' : '',
          run: () => act(action.id, { [only.key]: option.id }),
        });
      }
    } else {
      items.push({ label: `${action.label}……`, run: () => openForm(action) });
    }
  }
  return items;
}

function showChoices(items = optionsFor(view)) {
  const box = $('choices');
  box.replaceChildren(el('p', 'prompt', '你要怎么做？'));
  const list = el('div', 'choice-list');
  items.forEach((item, index) => {
    const button = el('button', 'choice');
    button.type = 'button';
    button.append(el('span', 'num', String(index + 1)), el('span', 'label', item.label));
    if (item.note) button.append(el('span', 'note', item.note));
    button.addEventListener('click', item.run);
    list.append(button);
  });
  box.append(list);
  box.hidden = false;
  requestAnimationFrame(() => box.classList.add('show'));
  list.querySelector('button')?.focus({ preventScroll: true });
}

function hideChoices() {
  const box = $('choices');
  box.classList.remove('show');
  box.hidden = true;
}

/** 多参数动作（例如带理由的指认）：在画面上逐项选择。 */
function openForm(action) {
  const box = $('choices');
  box.replaceChildren(el('p', 'prompt', action.label));
  const form = el('form', 'action-form');
  const fields = {};
  for (const parameter of action.parameters) {
    const label = el('label', 'field');
    label.append(el('span', '', parameter.label));
    const select = el('select');
    for (const option of parameter.options) {
      const node = el('option', '', option.label);
      node.value = option.id;
      select.append(node);
    }
    fields[parameter.key] = select;
    label.append(select);
    form.append(label);
  }
  const row = el('div', 'form-actions');
  const confirm = el('button', 'choice primary', action.id === 'mystery:accuse' ? '确认指认（将决定结局）' : '确定');
  const back = el('button', 'choice', '返回');
  back.type = 'button';
  back.addEventListener('click', () => showChoices());
  row.append(confirm, back);
  form.append(row);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    act(action.id, Object.fromEntries(Object.entries(fields).map(([key, select]) => [key, select.value])));
  });
  box.append(form);
}

// ---------- 随身笔记：随时查看线索与当前场景，不推进剧情 ----------

function updateNotes(next) {
  const before = notes.clues.length;
  notes = { clues: next.clues, resources: next.resources, sceneTitle: next.scene_title, sceneText: next.text };
  $('notes-count').textContent = String(notes.clues.length);
  if (notes.clues.length > before) {
    for (const id of ['notes-toggle', 'notes-btn']) {
      $(id).classList.remove('fresh');
      void $(id).offsetWidth;
      $(id).classList.add('fresh');
    }
  }
  if (!$('notebook').hidden) renderNotebook();
}

function renderNotebook() {
  const body = $('notebook-body');
  body.replaceChildren();
  const scene = el('section', 'nb-section');
  scene.append(el('h3', 'nb-heading', `当前场景 · ${notes.sceneTitle || '—'}`));
  for (const line of notes.sceneText.split('\n').filter((x) => x.trim())) scene.append(el('p', 'nb-scene', line));
  const found = el('section', 'nb-section');
  found.append(el('h3', 'nb-heading', `已发现的线索（${notes.clues.length}）`));
  if (!notes.clues.length) found.append(el('p', 'nb-empty', '还没有发现线索。'));
  const list = el('ol', 'nb-clues');
  for (const clue of notes.clues) {
    const item = el('li', 'nb-clue');
    item.append(el('strong', '', clue.label), el('span', '', clue.description));
    list.append(item);
  }
  found.append(list);
  body.append(found);
  if (notes.resources.length) {
    const people = el('section', 'nb-section');
    people.append(el('h3', 'nb-heading', '人物状态'));
    const meters = el('ul', 'nb-meters');
    for (const resource of notes.resources) {
      const item = el('li', resource.value ? 'nb-meter raised' : 'nb-meter');
      const max = resource.maximum || resource.value;
      item.append(el('span', '', resource.label),
        el('span', 'dots', `${'●'.repeat(resource.value)}${'○'.repeat(Math.max(0, max - resource.value))}`));
      meters.append(item);
    }
    people.append(meters);
    body.append(people);
  }
  body.append(scene);
}

function openNotebook() {
  renderNotebook();
  paused = true;
  $('notebook').hidden = false;
  $('notes-toggle').setAttribute('aria-expanded', 'true');
  $('notebook-close').focus({ preventScroll: true });
}

function closeNotebook() {
  if ($('notebook').hidden) return;
  $('notebook').hidden = true;
  paused = false;
  $('notes-toggle').setAttribute('aria-expanded', 'false');
}

function toggleNotebook() {
  if (!view) return;
  if ($('notebook').hidden) openNotebook();
  else closeNotebook();
}

$('notes-toggle').addEventListener('click', toggleNotebook);
$('notes-btn').addEventListener('click', toggleNotebook);
$('notebook-close').addEventListener('click', closeNotebook);

// ---------- 与引擎通信 ----------

function call(request) {
  return client.call({ ...request, session_id: sessionId });
}

function boot() {
  if (!booting) {
    client = client || new GameClient();
    sessionId = crypto.randomUUID();
    booting = call({ method: 'start', story_id: STORY_ID }).catch((error) => {
      booting = null;
      throw error;
    });
  }
  return booting;
}

async function act(actionId, values) {
  if (busy) return;
  busy = true;
  hideChoices();
  hideCard();
  try {
    const previous = view;
    const save = await call({ method: 'export' });
    const result = await call({ method: 'action', action: { action_id: actionId, expected_revision: view.revision, values } });
    if (!result.error_code) checkpoint = save;
    await present(result, previous);
  } catch (error) {
    await type(`出了点问题：${error.message}`);
    clearSubtitle();
    showChoices();
  } finally {
    busy = false;
  }
}

async function restart() {
  if (busy) return;
  busy = true;
  hideChoices();
  hideCard();
  actTitle = '第一幕 · 雾夜';
  seen = new Set();
  checkpoint = null;
  chances = CHANCES;
  mistakes = 0;
  updateChances();
  closeNotebook();
  try {
    booting = null;
    const result = await boot();
    await present(result, null);
  } finally {
    busy = false;
  }
}

async function opening() {
  stage.show('harbor');
  sound.setAmbience('harbor');
  await stage.fade(0, T(2200));
  setTimeout(() => sound.foghorn(), T(600));
  showCard('TaleLoom 织境 · 影像模式', '雾港旧案', '一九三一年 · 雾港');
  await hold(4200);
  hideCard();
  await sleep(1400);
}

async function begin() {
  $('begin').disabled = true;
  await sound.start();
  $('intro').classList.add('gone');
  busy = true;
  try {
    const intro = opening();
    let result;
    try {
      result = await boot();
    } catch (error) {
      await intro;
      await type(`故事没能载入：${error.message}`);
      $('intro').classList.remove('gone');
      $('begin').disabled = false;
      $('begin').textContent = '重试';
      return;
    }
    await intro;
    await present(result, null);
  } finally {
    busy = false;
  }
}

$('begin').addEventListener('click', begin);
$('restart').addEventListener('click', restart);
$('mute').addEventListener('click', () => {
  const muted = !sound.muted;
  sound.setMuted(muted);
  $('mute').textContent = muted ? '声音：关' : '声音：开';
  $('mute').setAttribute('aria-pressed', String(muted));
});

// 胶片颗粒：生成一次噪声贴图（CSP 允许 data: 图片）。
(() => {
  const c = document.createElement('canvas');
  c.width = 160;
  c.height = 160;
  const g = c.getContext('2d');
  const img = g.createImageData(160, 160);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.random() * 255;
    img.data[i] = v;
    img.data[i + 1] = v;
    img.data[i + 2] = v;
    img.data[i + 3] = 22;
  }
  g.putImageData(img, 0, 0);
  $('grain').style.backgroundImage = `url(${c.toDataURL()})`;
})();

// 提前下载运行环境，开场动画期间完成加载。
boot().catch(() => {});
