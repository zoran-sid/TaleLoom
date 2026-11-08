/**
 * 影像模式样片（《雾港旧案》）。负责人：ZC。
 *
 * 剧情、选项与判定全部来自浏览器里运行的同一个 Python 引擎（GameClient →
 * Pyodide Worker → session_factory 会话）；本页只把快照与反馈演成画面：
 * 场景转场、逐字字幕、审问特写、线索卡片和画面上的选项。不新增剧情文字。
 */
import './cinematic.css';
import { GameClient } from '../runtime/client.js';
import { Stage } from './stage.js';
import { Sound } from './sound.js';

const STORY_ID = 'fog_harbor';
const FAST = new URLSearchParams(location.search).get('fast') === '1';
const T = (ms) => (FAST ? Math.min(ms, 40) : ms);
const ART = { lobby: 'lobby', gathering: 'lobby', office: 'office', kitchen: 'kitchen' };
const AMBIENCE = { lobby: 'lobby', gathering: 'lobby', office: 'office', kitchen: 'kitchen' };
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
  if (event.key === ' ' && !event.target.closest('button')) {
    event.preventDefault();
    nudge();
  } else if (/^[1-9]$/.test(event.key) && !$('choices').hidden) {
    $('choices').querySelectorAll('button.choice')[Number(event.key) - 1]?.click();
  }
});
$('frame').addEventListener('click', (event) => { if (!event.target.closest('button')) nudge(); });
$('skip').addEventListener('click', nudge);

function hold(ms) {
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      if (poke === done) poke = null;
      resolve();
    };
    const timer = setTimeout(done, T(ms));
    poke = done;
  });
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
    if ((m = text.match(/^【获得线索】(.+?)：([\s\S]*)$/)) || (m = text.match(/^【获得线索】(.+)$/))) {
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

async function setArt(sceneId, extra = {}) {
  stage.show(ART[sceneId] || 'generic', { gathering: sceneId === 'gathering', ...extra });
  sound.setAmbience(AMBIENCE[sceneId] || 'generic');
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
  for (const beat of beatsFrom(messages)) {
    if (beat.kind === 'clue') await clueCard(beat.name, beat.text);
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
      await stage.fade(0, T(1000));
    } else {
      await type(beat.text);
    }
  }
  clearSubtitle();
}

async function enterScene(next) {
  clearSubtitle();
  await stage.fade(1, T(700));
  sound.thud();
  setArt(next.scene_id);
  showCard(actTitle, next.scene_title, '一九三一年 · 雾港');
  await hold(1800);
  hideCard();
  await stage.fade(0, T(1300));
  for (const line of chunks(next.text)) await type(line);
  clearSubtitle();
}

async function ending(next) {
  clearSubtitle();
  await stage.fade(1, T(1200));
  stage.show('ending', { dawn: ['truth', 'dawn'].includes(next.ending_id) });
  sound.setAmbience('ending');
  await stage.fade(0, T(1800));
  for (const line of chunks(next.text)) await type(line);
  clearSubtitle();
  showCard('结局', next.ending_title || next.ending_id, `第 ${next.turn} 回合`);
  showChoices([
    { label: '重新开始', run: restart },
    { label: '返回文字版', run: () => { location.href = '/'; } },
  ]);
}

/** 先在原场景演完反馈，再转场；结束时进入结局画面。 */
async function present(result, previous) {
  const next = result.view;
  if (result.error_code) {
    view = next;
    await type(result.messages.join(' ') || '这一步没能完成。');
    clearSubtitle();
    return showChoices();
  }
  await play(result.messages);
  view = next;
  if (next.ended) return ending(next);
  if (!previous || next.scene_id !== previous.scene_id) await enterScene(next);
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
    const result = await call({ method: 'action', action: { action_id: actionId, expected_revision: view.revision, values } });
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
