/**
 * 影像模式播放器。负责人：ZC。
 *
 * 剧情、选项与判定全部来自浏览器里运行的同一个 Python 引擎（GameClient →
 * Pyodide Worker → session_factory 会话）；本页只把快照与反馈演成画面：
 * 场景转场、配音跟随阅读、线索卡片、调查台和画面上的选项。不新增剧情文字。
 *
 * 默认播放《雾港旧案：未结的账》（stories/film/fog_harbor_ledger，线性分支，不上书架）；
 * ?story=<id> 可以换成其他剧本，例如旧样片 fog_harbor_film、深空影像版 deep_space_film。
 *
 * 影像版的画面是 MiniMax 生成的场景镜头（backdrops.js，按场景 ID 选用）；没有镜头的
 * 剧本或素材加载失败时，用 stage.js 的代码画面，按快照的 art 选（例如
 * portrait_zhou_cold：人物特写、周文、冷淡）。结局类型读
 * ending_kind。失败结局可以用会话的“回到上一个选择”（整局机会数由会话给出）；
 * 会话在进入带 checkpoint 的场景时记下存档点，本页把它们导出成标准存档，存进
 * web/storage/cinematic.js（LQ），刷新后可以从存档点继续；笔记里可以回到任一存档点。
 */
import './cinematic.css';
import { GameClient } from '../runtime/client.js';
import { CinematicSaveStore } from '../storage/cinematic.js';
import { Stage, hasScene } from './stage.js';
import { Sound } from './sound.js';
import { AudioTrack } from './audio-track.js';
import { AmbientTrack } from './ambient-track.js';
import { SCENE_AUDIO, SCENE_CUES, CHOICE_AUDIO, AMBIENCE_AUDIO, MUSIC_AUDIO } from './audio-assets.js';
import { Desk, unitFrom } from './units.js';
import { readingPages } from './narrative.js';
import { dropPrimedTransition, openingStill, playTransition, primeTransition, transitionFor } from './transitions.js';
import { Backdrop } from './backdrops.js';

const params = new URLSearchParams(location.search);
const STORY_ID = params.get('story') || 'fog_harbor_ledger';
const FAST = params.get('fast') === '1';
const UNIT_ACTIONS = new Set(['mystery:inspect', 'mystery:solve', 'mystery:hint']);
// rushing：演出途中要回到存档点时，把剩下的字幕与转场快速播完。
let rushing = false;
const T = (ms) => (FAST || rushing ? Math.min(ms, 40) : ms);

// 主题：雾港（旅馆）与深空（飞船）各有片名、开场与结局画面。
const SHIP = STORY_ID.startsWith('deep_space');
const THEMES = {
  ship: {
    title: '深空回声', place: '“回声号” · 深空', firstAct: '', opening: ['space', {}], fallback: 'corridor', chances: true,
    endings: {
      escape: ['space', { pod: true }], truth: ['space', { pod: true, dawn: true }],
      suffocate: ['bay', { dying: true }], blackout: ['corridor', { dark: true }],
    },
    failureEnding: ['bay', { dying: true }], defaultEnding: ['space', { pod: true }],
  },
  ledger: {
    title: '雾港旧案', subtitle: '未结的账', place: '一九三一年深秋 · 雾港', firstAct: '序章 · 最后一晚的饭桌',
    opening: ['harbor', {}], fallback: 'generic', chances: false,
    failureEnding: ['harbor', { storm: true, focus: [760, 600] }], defaultEnding: ['harbor', {}],
  },
  fog: {
    title: '雾港旧案', place: '一九三一年 · 雾港', firstAct: '第一幕 · 雾夜', opening: ['harbor', {}], fallback: 'generic', chances: true,
    failureEnding: ['harbor', { storm: true, focus: [760, 600] }], defaultEnding: ['harbor', {}],
  },
};
const THEME = SHIP ? THEMES.ship : STORY_ID === 'fog_harbor_ledger' ? THEMES.ledger : THEMES.fog;
// 开场画面用首个场景的镜头。
const START_SCENE = SHIP ? 'bay_wake' : STORY_ID === 'fog_harbor_ledger' ? 'p01_dock' : 'lobby';
// 结局 → 画面：失败结局各有专门的画面，其余在港口（天亮或夜里有船离开）。
THEME.endings ||= {
  truth: ['harbor', { dawn: true, boat: 'arrive', focus: [980, 470] }],
  dawn: ['harbor', { dawn: true, boat: 'arrive', focus: [980, 470] }],
  scapegoat: ['harbor', { boat: 'leave', focus: [1000, 470] }],
  wrong: ['harbor', { boat: 'leave', focus: [1000, 470] }],
  insufficient: ['harbor', {}],
  fail_tide: ['harbor', { storm: true, focus: [760, 600] }],
  fail_caught: ['doorway', {}],
  fail_attacked: ['storeroom', {}],
};
const AMBIENCE = {
  lobby: 'lobby', office: 'office', kitchen: 'kitchen', portrait: 'portrait', harbor: 'harbor',
  guestroom: 'rain', backyard: 'harbor', zhouroom: 'lobby', attic: 'attic',
  doorway: 'tension', storeroom: 'tension', dinner: 'dinner', dutyroom: 'dutyroom', ledger: 'ledger',
  bay: 'alarm', corridor: 'ship', toolroom: 'workshop', airlock: 'ship', energy: 'reactor',
  comms: 'ship', observatory: 'space', space: 'space',
};
// 旧剧本里不是画面键开头的场景 id。
const ALIAS = { cryo: 'bay' };
const SUSPECTS = new Set(['gu', 'zhou', 'ayun']);
const MOODS = new Set(['nervous', 'tears', 'cold']);
const PLACES = new Set(['kitchen', 'lobby']);
const VERBS = { 'mystery:ask': '审问', 'mystery:examine': '深入调查', 'puzzle:use': '使用' };

const $ = (id) => document.getElementById(id);
const stage = new Stage($('stage'));
const sound = new Sound();
const audioTrack = new AudioTrack({ map: SCENE_AUDIO, onProgress: detail => {
  document.dispatchEvent(new CustomEvent('taleloom:audio-progress', { detail }));
} });
const ambientTrack = new AmbientTrack({ map: AMBIENCE_AUDIO });
ambientTrack.onError = (name) => sound.setAmbience(name);
// 录制的配乐循环；没有素材或加载失败时用 sound.js 合成的配乐。
const musicTrack = new AmbientTrack({ map: MUSIC_AUDIO });
musicTrack.onError = (name) => sound.setMusic(name);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, T(ms)));
const motionAllowed = () => !FAST && !paused && !matchMedia('(prefers-reduced-motion: reduce)').matches;
const backdrop = new Backdrop($('backdrop'), { motion: motionAllowed });
// 黑场淡入淡出同时盖住场景镜头：幕布与画布用同一时长。
const fadeCanvas = stage.fade.bind(stage);
stage.fade = (to, ms) => {
  const curtain = $('curtain');
  curtain.style.transitionDuration = `${Math.max(1, ms)}ms`;
  curtain.style.opacity = String(to);
  return fadeCanvas(to, ms);
};
const desk = new Desk($('desk'), { send: sendUnit, sound, speed: T, onClose: () => { deskClosedFor = unitKey(view); showChoices(); } });

let client = null;
let sessionId = '';
let booting = null;
let view = null;
let busy = false;
let actTitle = THEME.firstAct;
let poke = null;
let stopTransition = null;
let paused = false;          // 打开笔记时暂停字幕与转场计时
let seen = new Set();        // 已经播过描述的场景，回来时不再重播
let notes = { clues: [], resources: [], sceneTitle: '', sceneText: '' };
let saves = loadSaves();     // 关键节点的标准存档（LQ 的存储），刷新后可以继续
let lastPoint = null;        // 最近一次记下的存档点 id，用来发现新到达的存档点
let pendingRollback = null;  // 演出结束后要回到的存档点
let pendingRestart = false;
let deskClosedFor = '';      // 玩家暂离的调查单元：同一单元不再自动打开
let sceneReading = null;     // 当前正在跟随整段场景配音的字幕

function syncDucking() {
  const speaking = Boolean(sceneReading && audioTrack.el && audioTrack.enabled && !audioTrack.muted && !paused);
  ambientTrack.setDucked(speaking);
  musicTrack.setDucked(speaking);
  sound.setDucked(speaking);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// ---------- 输入：点击画面或按空格跳过当前页；有配音时也按时间戳翻页 ----------

function nudge() {
  if (paused || desk.open) return;
  const next = poke;
  poke = null;
  if (next) next();
}

document.addEventListener('keydown', (event) => {
  if (event.target.closest('select, input')) return;
  if (event.key === 'Escape' && !$('notebook').hidden) {
    closeNotebook();
  } else if (event.key === 'n' || event.key === 'N') {
    toggleNotebook();
  } else if (!$('notebook').hidden || desk.open) {
    return;
  } else if (event.key === ' ' && !event.target.closest('button')) {
    event.preventDefault();
    if (!event.repeat) nudge();
  } else if (/^[1-9]$/.test(event.key) && !$('choices').hidden) {
    $('choices').querySelectorAll('button.choice')[Number(event.key) - 1]?.click();
  }
});
$('frame').addEventListener('click', (event) => {
  if (!event.target.closest('button, .desk') && $('notebook').hidden && !getSelection()?.toString()) nudge();
});
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

/** 显示完整段落与说话人；旁白没有人物署名。 */
function renderText({ text, speaker = '' }, waiting = false) {
  const box = $('subtitle');
  box.replaceChildren();
  if (view) box.append(el('span', 'scene-label', view.scene_title));
  if (speaker) box.append(el('span', 'speaker', speaker));
  box.append(el('span', 'line', text));
  if (waiting) box.append(el('span', 'reading-hint', sceneReading && audioTrack.el && audioTrack.enabled && !audioTrack.muted ? '配音播放中 · 点击可跳过 ▾' : '点击画面或按空格继续 ▾'));
  box.hidden = false;
  box.scrollTop = 0;
  document.dispatchEvent(new CustomEvent('taleloom:reading-page', {
    detail: { sceneId: view?.scene_id || '', text, speaker, audioId: sceneReading?.sceneId || null },
  }));
}

/** 允许玩家跳页；配音可按进度自动翻页，fast 只加速画面转场。 */
function waitForAdvance(audioFraction = null) {
  if (rushing) return Promise.resolve();
  $('frame').dataset.awaitingAdvance = 'true';
  if (document.activeElement === document.body || document.activeElement.closest('#choices, #intro')) {
    $('frame').focus({ preventScroll: true });
  }
  return new Promise(resolve => {
    let unwatch = () => {};
    const done = (manual) => {
      unwatch();
      if (manual && audioFraction !== null) audioTrack.seekFraction(audioFraction);
      if (sceneReading) sceneReading.rebind = null;
      delete $('frame').dataset.awaitingAdvance;
      poke = null;
      resolve();
    };
    poke = () => done(true);
    if (audioFraction !== null) {
      sceneReading.rebind = () => {
        unwatch();
        unwatch = audioTrack.watchFraction(audioFraction, () => done(false));
      };
      sceneReading.rebind();
    }
  });
}

/** 素材时间点与当前字幕页一一对应；剧本改动时按字数安全回退。 */
function pageEndFractions(pages, cue) {
  if (cue && Array.isArray(cue.cues) && cue.cues.length === pages.length && Number.isFinite(cue.duration) && cue.duration > 0
      && cue.cues.every(time => Number.isFinite(time))) {
    return cue.cues.map(time => Math.min(1, Math.max(0, time / cue.duration)));
  }
  const total = pages.reduce((sum, page) => sum + page.text.length, 0);
  let read = 0;
  return pages.map(page => {
    read += page.text.length;
    return total ? read / total : 1;
  });
}

async function type(text, speaker = '') {
  const pages = readingPages(text, { storyId: STORY_ID, sceneId: view?.scene_id, fallbackSpeaker: speaker });
  const clip = CHOICE_AUDIO[JSON.stringify([view?.scene_id, text.trim()])];
  const fractions = pageEndFractions(pages, clip);
  if (clip) {
    sceneReading = { sceneId: clip.id, fraction: 0 };
    audioTrack.play(clip.id);
    syncDucking();
  }
  try {
    for (const [index, page] of pages.entries()) {
      if (clip) sceneReading.fraction = index ? fractions[index - 1] : 0;
      renderText(page, true);
      await waitForAdvance(clip ? fractions[index] : null);
    }
  } finally {
    if (clip) {
      audioTrack.stop();
      sceneReading = null;
      syncDucking();
    }
  }
}

function clearSubtitle() {
  $('subtitle').hidden = true;
  $('subtitle').replaceChildren();
}

/** 按剧本原有段落阅读，不再切成逐字或短句动画。 */
function chunks(text) {
  return text.split('\n').map(p => p.trim()).filter(Boolean);
}

// ---------- 卡片与声音说明 ----------

// 转场卡的淡入帧与隐藏定时器各只留一份：fast／快进时停留不到一帧，
// 上一次 showCard 排的淡入帧可能晚于 hideCard 才执行，把卡片重新点亮并挡住隐藏。
let cardFrame = 0;
let cardTimer = 0;

function showCard(kicker, title, place) {
  const card = $('card');
  cancelAnimationFrame(cardFrame);
  clearTimeout(cardTimer);
  card.replaceChildren(el('p', 'card-kicker', kicker), el('h2', 'card-title', title), el('p', 'card-place', place));
  card.hidden = false;
  cardFrame = requestAnimationFrame(() => card.classList.add('show'));
}

function hideCard() {
  const card = $('card');
  cancelAnimationFrame(cardFrame);
  clearTimeout(cardTimer);
  card.classList.remove('show');
  cardTimer = setTimeout(() => { card.hidden = true; }, T(700));
}

/** 嫌疑人起了戒心：红色提示卡，配低沉的一声。 */
async function warnCard(text) {
  sound.thud();
  const card = $('clue');
  card.classList.add('warn');
  card.replaceChildren(el('p', 'clue-kicker', '戒备'), el('p', 'clue-text', text));
  card.hidden = false;
  requestAnimationFrame(() => card.classList.add('show'));
  await waitForAdvance();
  card.classList.remove('show');
  await sleep(500);
  card.hidden = true;
  card.classList.remove('warn');
}

async function clueCard(name, text) {
  sound.bell();
  stage.flash();
  $('backdrop').classList.remove('flash');
  void $('backdrop').offsetWidth;
  $('backdrop').classList.add('flash');
  const card = $('clue');
  card.replaceChildren(el('p', 'clue-kicker', '获得线索'), el('h3', 'clue-name', name), el('p', 'clue-text', text));
  card.hidden = false;
  requestAnimationFrame(() => card.classList.add('show'));
  await waitForAdvance();
  card.classList.remove('show');
  await sleep(500);
  card.hidden = true;
}

/** 重要声音的文字说明：静音或听不见时也知道发生了什么。 */
let soundCaptions = [];
const shownAmbienceCaptions = new Set();
sound.onCaption = (text) => {
  if (text.startsWith('环境声：')) {
    if (shownAmbienceCaptions.has(text)) return;
    shownAmbienceCaptions.add(text);
  }
  const node = $('sound-caption');
  // 同一镜头的环境声与配乐可能同时开始，两条说明都应可读。
  if (node.hidden || text.startsWith('环境声：')) soundCaptions = [];
  soundCaptions = [...soundCaptions.filter((line) => line !== text), text].slice(-3);
  node.textContent = soundCaptions.map((line) => `〔${line}〕`).join(' ');
  node.hidden = false;
  clearTimeout(sound.captionTimer);
  sound.captionTimer = setTimeout(() => { node.hidden = true; }, FAST ? 400 : 2600);
};

// ---------- 把会话反馈拆成“镜头” ----------

function beatsFrom(messages) {
  const beats = [];
  for (const raw of messages) {
    const text = raw.trim();
    // 存档点由快照的 checkpoint 给出，旧剧本的“【存档点】”提示和核对标记不再单独播放。
    if (!text || text.startsWith('【存档点】') || text.startsWith('【核对完成】')) continue;
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

/**
 * 画面键 → 画面与选项：键以画面名开头，其后的词是选项。
 * 例如 portrait_zhou_cold_kitchen → 人物特写（周文、冷淡、后厨的火光），harbor_dawn → 天亮的港口。
 * 没有 art 的旧剧本用场景 id 推断；都认不出时用主题的通用画面。
 */
function artFor(current) {
  const key = current.art || current.scene_id;
  const [head, ...words] = key.split('_');
  const name = ALIAS[head] || head;
  if (!hasScene(name)) return { name: THEME.fallback, options: {} };
  const options = {};
  for (const word of words) {
    if (SUSPECTS.has(word)) options.suspect = word;
    else if (MOODS.has(word)) options.mood = word;
    else if (PLACES.has(word)) options.place = word;
    else options[word] = true;
  }
  if (name === 'harbor' && options.dawn) Object.assign(options, { boat: 'arrive', focus: [980, 470] });
  return { name, options };
}

/** 画面 → 配乐（雾港两部）：饭桌与大堂舒缓，账房与后厨紧张，账桌思索，冷淡或落泪的特写沉郁。 */
function musicFor(name, options) {
  if (SHIP) return null;
  if (name === 'portrait') return options.mood === 'cold' || options.mood === 'tears' ? 'dark' : 'tense';
  if (options.dawn) return 'dawn';
  if (name === 'office') return options.alive ? 'calm' : 'tense';
  return { harbor: 'calm', dinner: 'calm', lobby: 'calm', ledger: 'study', dutyroom: 'study', kitchen: 'tense', doorway: 'tense' }[name] || 'study';
}

function setAmbience(name) {
  sound.setAmbience(ambientTrack.set(name) ? null : name);
}

function setMusic(name) {
  sound.setMusic(musicTrack.set(name) ? null : name);
}

/** 有场景镜头时显示镜头并让画布停在黑场；没有或加载失败时用代码画面。 */
function showPicture(sceneId, name, options) {
  const drawn = () => stage.show(name, options);
  if (backdrop.show(STORY_ID, sceneId, drawn)) stage.show('black');
  else drawn();
}

function setArt(current) {
  const { name, options } = artFor(current);
  showPicture(current.scene_id, name, options);
  setAmbience(AMBIENCE[name] || 'generic');
  setMusic(musicFor(name, options));
}

async function interrogate(beat) {
  clearSubtitle();
  await stage.fade(1, T(450));
  const who = { 顾先生: 'gu', 周文: 'zhou', 阿芸: 'ayun' }[beat.who] || 'zhou';
  backdrop.hide();
  stage.show('portrait', { suspect: who, place: view.scene_id });
  setAmbience('portrait');
  $('caption').textContent = `审问 · ${beat.topic}`;
  $('caption').hidden = false;
  await stage.fade(0, T(800));
  for (const line of beat.lines) await type(line, beat.who);
  $('caption').hidden = true;
  clearSubtitle();
  await stage.fade(1, T(450));
  setArt(view);
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
      for (const line of beat.lines) await type(line);
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

/** 转场视频的跳过与淡出设置；点击画面或按空格可以跳过。 */
function transitionHooks(onPlaying = () => {}) {
  return {
    onPlaying,
    setSkip: (stop) => {
      if (poke === stopTransition) poke = stop;
      stopTransition = stop;
    },
    fadeTime: T(430),
  };
}

function sceneVideosEnabled() {
  return (!FAST || params.get('transitions') === '1')
    && !rushing && !paused && !matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** 首次进入：标题卡加完整描述；再次回来：只闪一下场景名，不重播描述。 */
async function enterScene(next) {
  $('frame').classList.remove('ended');
  clearSubtitle();
  const revisit = seen.has(next.scene_id);
  seen.add(next.scene_id);
  await stage.fade(1, T(revisit ? 450 : 700));
  if (!revisit) sound.thud();
  setArt(next);
  if (revisit) {
    showCard('', next.scene_title, '');
    await stage.fade(0, T(700));
    await hold(700);
    hideCard();
    return;
  }
  const clip = transitionFor(STORY_ID, next.scene_id);
  let played = false;
  if (openingPlay) {
    // 开场视频在点击「开始」时已经从开始页的定格画面接着播放，这里等它播完。
    const running = openingPlay;
    openingPlay = null;
    stage.fade(0, T(650));
    played = await running;
  } else if (clip && sceneVideosEnabled()) {
    played = await playTransition($('scene-transition'), clip, transitionHooks(() => stage.fade(0, T(650))));
  }
  showCard(actTitle, next.scene_title, THEME.place);
  await hold(played ? 400 : 1800);
  hideCard();
  if (!played) await stage.fade(0, T(1300));
  const pages = chunks(next.text).flatMap(line => readingPages(line, { storyId: STORY_ID, sceneId: next.scene_id }));
  const cue = SCENE_CUES[next.scene_id];
  const fractions = pageEndFractions(pages, cue);
  sceneReading = { sceneId: next.scene_id, fraction: 0 };
  audioTrack.play(next.scene_id);
  syncDucking();
  try {
    for (const [index, page] of pages.entries()) {
      sceneReading.fraction = index ? fractions[index - 1] : 0;
      renderText(page, true);
      await waitForAdvance(fractions[index] ?? null);
    }
  } finally {
    sceneReading = null;
    audioTrack.stop();
    syncDucking();
    clearSubtitle();
  }
}

function isFailure(current) {
  return current.ending_kind === 'failure';
}

document.title = `${THEME.title}${THEME.subtitle ? `：${THEME.subtitle}` : ''} · 影像模式`;
document.querySelector('#intro h1').textContent = THEME.title;
document.querySelector('#intro .intro-sub').textContent = THEME.subtitle ? `${THEME.subtitle} · ${THEME.place}` : THEME.place;
$('chances').hidden = !THEME.chances;
updateChances(null);

// 开始页停在开场视频的第一帧；能播视频时把视频本身垫在下面，点击开始后原地接着播放。
const OPENING_CLIP = transitionFor(STORY_ID, START_SCENE);
const OPENING_STILL = openingStill(STORY_ID);
let openingPlay = null;
if (OPENING_STILL) {
  $('intro').style.setProperty('--intro-still', `url("${OPENING_STILL}")`);
  $('intro').classList.add('with-still');
  if (OPENING_CLIP && sceneVideosEnabled()) {
    primeTransition($('scene-transition'), OPENING_CLIP, OPENING_STILL);
    $('intro').classList.add('over-clip');
  }
}

// ---------- 画面内的数值资源（氧气、电量等）；0/1 的状态（如戒心）只放在笔记里 ----------

let lastMeters = {};
function renderMeters(resources) {
  const box = $('meters');
  const shown = resources.filter((r) => r.maximum === null || r.maximum === undefined || r.maximum > 1);
  box.hidden = !shown.length;
  box.replaceChildren();
  for (const r of shown) {
    const chip = el('span', 'meter', `${r.label} ${r.value}${r.maximum ? `/${r.maximum}` : ''}`);
    if (r.value <= 3 || (r.maximum && r.value / r.maximum <= 0.25)) chip.classList.add('low');
    if (lastMeters[r.id] !== undefined && r.value < lastMeters[r.id]) chip.classList.add('drop');
    box.append(chip);
  }
  lastMeters = Object.fromEntries(resources.map((r) => [r.id, r.value]));
}

function latestSave() {
  return saves.reduce((best, entry) => (!best || entry.at > best.at ? entry : best), null);
}

async function ending(next) {
  $('frame').classList.add('ended');
  clearSubtitle();
  audioTrack.stop();
  const failed = isFailure(next);
  await stage.fade(1, T(1200));
  const [art, options] = THEME.endings[next.ending_id] || (failed ? THEME.failureEnding : THEME.defaultEnding);
  showPicture(next.scene_id, art, options);
  setAmbience(options.storm ? 'storm' : art === 'harbor' ? 'ending' : failed ? 'tension' : AMBIENCE[art] || 'ending');
  setMusic(SHIP ? null : ['truth', 'dawn'].includes(next.ending_id) ? 'dawn' : 'dark');
  if (failed) stage.shake(900, 14);
  await stage.fade(0, T(1800));
  for (const line of chunks(next.text)) await type(line);
  clearSubtitle();
  const record = [`第 ${next.turn} 回合`];
  if (next.mistakes) record.push(`失误 ${next.mistakes} 次`);
  if (next.rewinds) record.push(`回到存档点 ${next.rewinds} 次`);
  const left = next.rewinds_remaining;
  if (failed) {
    showCard('任务失败', next.ending_title || next.ending_id, left > 0 ? `还剩 ${left} 次机会` : '机会已经用完');
  } else {
    showCard('结局', next.ending_title || next.ending_id, record.join(' · '));
  }
  const items = [];
  if (failed && left > 0) items.push({ label: `回到上一个选择（还剩 ${left} 次机会）`, run: rewind });
  const saved = latestSave();
  if (saved && next.ending_id !== 'truth') {
    items.push({ label: `回到存档点「${saved.label}」`, run: () => rollbackTo(saved) });
  }
  items.push({ label: failed ? '从头再来' : '重新开始', run: restart });
  items.push({ label: '返回文字版', run: () => { location.href = '/'; } });
  showChoices(items);
}

/** 换上一份会话结果的画面并直接回到选项；kicker/place 用于转场卡片。 */
async function arrive(result, kicker, place) {
  $('frame').classList.remove('ended');
  clearSubtitle();
  audioTrack.stop();
  closeNotebook();
  desk.reset();
  deskClosedFor = '';
  await stage.fade(1, T(600));
  sound.thud();
  view = result.view;
  updateNotes(view);
  updateChances(view);
  seen.add(view.scene_id);
  setArt(view);
  showCard(kicker, view.scene_title, place);
  await stage.fade(0, T(900));
  await hold(1400);
  hideCard();
  showChoices();
}

/** 失败后回到上一个选择：会话扣一次机会、记一次失误；之后记下的存档点作废。 */
async function rewind() {
  if (busy) return;
  busy = true;
  hideChoices();
  hideCard();
  try {
    const result = await call({ method: 'rewind', expected_revision: view.revision });
    if (result.error_code) throw new Error(result.messages.join(' '));
    await syncSaves(result.view);
    await arrive(result, '回到上一个选择', `还剩 ${result.view.rewinds_remaining} 次机会`);
  } catch (error) {
    await type(`没能回到上一步：${error.message}`);
    clearSubtitle();
    showChoices([{ label: '从头再来', run: restart }]);
  } finally {
    busy = false;
    runPendingRollback();
  }
}

/**
 * 回到某个存档点：先用会话的 restore_checkpoint（计一次回退，之后的存档点作废）；
 * 会话里没有这个存档点时（例如刚刷新、旧存档），读入那份标准存档。
 */
async function rollbackTo(entry, { resume = false } = {}) {
  if (busy) return;
  busy = true;
  hideChoices();
  hideCard();
  try {
    let result = resume ? null : await call({
      method: 'restore_checkpoint', checkpoint_id: entry.save.state.scene, expected_revision: view.revision,
    });
    if (!result || result.error_code === 'invalid_checkpoint') result = await call({ method: 'restore', payload: entry.save });
    if (result.error_code) throw new Error(result.messages.join(' ') || '存档无法恢复');
    await syncSaves(result.view);
    await arrive(result, resume ? '从存档点继续' : '回到存档点', entry.label);
  } catch (error) {
    await type(`没能回到存档点：${error.message}`);
    clearSubtitle();
    showChoices([{ label: '从头再来', run: restart }]);
  } finally {
    busy = false;
    runPendingRollback();
  }
}

// ---------- 关键节点自动存档（LQ 的影像存档存储；读写失败时只在本页保留） ----------

function store() {
  return new CinematicSaveStore(STORY_ID);
}

function loadSaves() {
  try {
    return store().readEntries();
  } catch {
    return [];
  }
}

function writeSaves() {
  try {
    store().writeEntries(saves);
  } catch {
    /* 隐私模式或空间不足：自动存档只在本页有效 */
  }
  if (!$('notebook').hidden) renderNotebook();
}

/**
 * 与会话的存档点对齐：到达新的存档点时导出标准存档记下；会话作废的存档点同时删掉。
 */
async function syncSaves(current) {
  const point = current.checkpoint;
  const points = (await call({ method: 'checkpoints' })).checkpoints;
  const alive = new Set(points.map((p) => p.id));
  const before = saves.length;
  let added = false;
  saves = saves.filter((entry) => alive.has(entry.save.state.scene));
  if (point && point.id !== lastPoint && !current.ended && !saves.some((e) => e.save.state.scene === point.id
      && e.save.state.turn === point.turn)) {
    const save = await call({ method: 'export' });
    // 只在刚进入存档点时记下（会话在进入场景时拍下这一刻）。
    if (save.state.scene === point.id && save.state.turn === point.turn) {
      saves = saves.filter((entry) => entry.label !== point.label);
      saves.push({ label: point.label, scene: current.scene_title, turn: point.turn, at: Date.now(), save });
      added = true;
      toast(`已自动存档 · ${point.label}`);
    }
  }
  lastPoint = point ? point.id : null;
  if (added || saves.length !== before) writeSaves();
}

function toast(text) {
  const node = $('toast');
  node.textContent = text;
  node.hidden = false;
  node.classList.remove('show');
  void node.offsetWidth;
  node.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.classList.remove('show'); node.hidden = true; }, FAST ? 300 : 2600);
}

function updateChances(current) {
  const limit = current?.rewind_limit ?? 3;
  const left = current?.rewinds_remaining ?? limit;
  $('chances').textContent = `机会 ${'●'.repeat(left)}${'○'.repeat(Math.max(0, limit - left))}`;
  $('chances').title = `还可以退回上一个选择 ${left} 次`;
}

/** 先在原场景演完反馈，再转场；结束时进入结局画面。 */
async function present(result, previous) {
  const next = result.view;
  updateNotes(next);
  updateChances(next);
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

// ---------- 画面上的选项与调查台 ----------

function unitKey(current) {
  const unit = current && unitFrom(current);
  return unit ? `${current.scene_id}/${unit.id}` : '';
}

function optionsFor(current) {
  const items = [];
  const unit = unitFrom(current);
  if (unit) items.push({ id: 'desk', label: `${unit.solvable ? '核对' : '细看'}：${unit.name}`, note: unit.tries, primary: true, run: openDesk });
  items.push(...current.choices.filter((c) => c.enabled).map((c) => ({ id: c.id, label: c.label, run: () => act(c.id, {}) })));
  for (const action of current.actions) {
    if (!action.enabled || UNIT_ACTIONS.has(action.id)) continue;
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

function openDesk() {
  if (busy || !view) return;
  deskClosedFor = '';
  hideChoices();
  desk.show(view);
}

function showChoices(items) {
  // 选项居中时，底部继续保留当前剧情，供玩家对照作决定。
  const context = view && readingPages(view.text, { storyId: STORY_ID, sceneId: view.scene_id }).at(-1);
  if (context) renderText(context);
  if (!items && view && !view.ended && unitKey(view) && unitKey(view) !== deskClosedFor) {
    // 场景里有尚未完成的调查：直接打开调查台（暂离后改为选项里的入口）。
    hideChoices();
    desk.show(view);
    return;
  }
  const list = el('div', 'choice-list');
  (items || optionsFor(view)).forEach((item, index) => {
    const button = el('button', `choice${item.primary ? ' primary' : ''}`);
    button.type = 'button';
    if (item.id) button.dataset.action = item.id;
    button.append(el('span', 'num', String(index + 1)), el('span', 'label', item.label));
    if (item.note) button.append(el('span', 'note', item.note));
    button.addEventListener('click', item.run);
    list.append(button);
  });
  const box = $('choices');
  box.replaceChildren(el('p', 'prompt', '你要怎么做？'), list);
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

/**
 * 调查台的操作：查看、核对、提示。结果先由会话判定；核对通过或剧情换场时，
 * 先播落章动画，再按普通结果演出反馈；其余情况把结果交回调查台显示。
 */
async function sendUnit(actionId, values) {
  if (busy) return null;
  const previous = view;
  const result = await call({ method: 'action', action: { action_id: actionId, expected_revision: view.revision, values } });
  updateNotes(result.view);
  if (!result.error_code) await syncSaves(result.view);
  view = result.view;
  const solved = !result.error_code && result.messages.some((m) => m.startsWith('【核对完成】'));
  const moved = result.view.scene_id !== previous.scene_id || result.view.ended;
  if (!solved && !moved) return result;
  busy = true;
  try {
    if (solved) await desk.celebrate();
    else desk.close(true);
    await present(result, previous);
  } finally {
    busy = false;
    runPendingRollback();
  }
  return null;
}

// ---------- 随身笔记：随时查看线索与当前场景，不推进剧情 ----------

function updateNotes(next) {
  const before = notes.clues.length;
  notes = { clues: next.clues, resources: next.resources, sceneTitle: next.scene_title, sceneText: next.text };
  renderMeters(next.resources);
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
  if (saves.length) {
    const section = el('section', 'nb-section');
    section.append(el('h3', 'nb-heading', '自动存档（回到存档点不消耗机会，之后的进度会作废）'));
    const list = el('ul', 'nb-saves');
    for (const entry of [...saves].sort((a, b) => b.at - a.at)) {
      const item = el('li', 'nb-save');
      const info = el('span', 'nb-save-info');
      info.append(el('strong', '', entry.label), el('span', '', ` ${entry.scene} · 第 ${entry.turn} 回合`));
      const go = el('button', 'nb-go', '回到这里');
      go.type = 'button';
      go.addEventListener('click', () => {
        if (go.dataset.armed !== '1') {
          go.dataset.armed = '1';
          go.textContent = '确定回到这里？';
          return;
        }
        if (busy) {
          // 正在演出：快速播完这一段，结束后立即回到存档点
          pendingRollback = entry;
          rushing = true;
          audioTrack.stop();
          closeNotebook();
          nudge();
          toast(`正在回到存档点 · ${entry.label}`);
          return;
        }
        closeNotebook();
        rollbackTo(entry);
      });
      item.append(info, go);
      list.append(item);
    }
    section.append(list);
    body.append(section);
  }
  body.append(scene);
}

function openNotebook() {
  renderNotebook();
  paused = true;
  stopTransition?.();
  backdrop.pause();
  audioTrack.suspend();
  syncDucking();
  $('notebook').hidden = false;
  $('notes-toggle').setAttribute('aria-expanded', 'true');
  $('notebook-close').focus({ preventScroll: true });
}

function closeNotebook() {
  if ($('notebook').hidden) return;
  $('notebook').hidden = true;
  paused = false;
  backdrop.resume();
  $('notes-toggle').setAttribute('aria-expanded', 'false');
  // 合上笔记后重新播放当前场景的配音。
  audioTrack.resume();
  syncDucking();
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

/** 演出结束后，如果玩家在演出途中选择了回到存档点，现在执行。 */
function runPendingRollback() {
  rushing = false;
  if (pendingRestart) {
    pendingRestart = false;
    pendingRollback = null;
    restart();
    return;
  }
  if (!pendingRollback) return;
  const entry = pendingRollback;
  pendingRollback = null;
  rollbackTo(entry);
}

async function act(actionId, values) {
  if (busy) return;
  busy = true;
  hideChoices();
  hideCard();
  try {
    const previous = view;
    const result = await call({ method: 'action', action: { action_id: actionId, expected_revision: view.revision, values } });
    if (!result.error_code) await syncSaves(result.view);
    await present(result, previous);
  } catch (error) {
    await type(`出了点问题：${error.message}`);
    clearSubtitle();
    showChoices();
  } finally {
    busy = false;
    runPendingRollback();
  }
}

async function restart() {
  if (desk.busy) return;
  audioTrack.stop();
  if (busy) {
    pendingRestart = true;
    rushing = true;
    closeNotebook();
    nudge();
    return;
  }
  busy = true;
  hideChoices();
  hideCard();
  desk.reset();
  actTitle = THEME.firstAct;
  seen = new Set();
  saves = [];
  lastPoint = null;
  deskClosedFor = '';
  writeSaves();
  closeNotebook();
  try {
    booting = null;
    const result = await boot();
    await syncSaves(result.view);
    await present(result, null);
  } finally {
    busy = false;
    runPendingRollback();
  }
}

async function opening() {
  audioTrack.stop();
  showPicture(START_SCENE, ...THEME.opening);
  setAmbience(AMBIENCE[THEME.opening[0]] || 'harbor');
  setMusic(musicFor(...THEME.opening));
  // 有开场视频的剧本直接进入首个场景。
  if (transitionFor(STORY_ID, START_SCENE) && sceneVideosEnabled()) {
    await stage.fade(0, T(450));
    return;
  }
  await stage.fade(0, T(2200));
  setTimeout(() => (SHIP ? sound.beep() : sound.foghorn()), T(600));
  showCard('TaleLoom 织境 · 影像模式', THEME.title, THEME.subtitle ? `${THEME.subtitle} · ${THEME.place}` : THEME.place);
  await hold(4200);
  hideCard();
  await sleep(1400);
}

async function begin(resume = null) {
  $('begin').disabled = true;
  $('resume').disabled = true;
  await sound.start();
  $('intro').classList.add('gone');
  try {
    if (resume) {
      dropPrimedTransition($('scene-transition'));
      const result = await boot();
      view = result.view;
      return await rollbackTo(resume, { resume: true });
    }
    busy = true;
    saves = [];
    writeSaves();
    if ($('scene-transition').dataset.primed) {
      openingPlay = playTransition($('scene-transition'), OPENING_CLIP, transitionHooks());
    }
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
    await syncSaves(result.view);
    await present(result, null);
  } finally {
    busy = false;
    runPendingRollback();
  }
}

$('begin').addEventListener('click', () => begin());
(() => {
  const saved = latestSave();
  if (!saved) return;
  $('resume').hidden = false;
  $('resume').textContent = `从存档点继续：${saved.label}`;
  $('resume').addEventListener('click', () => begin(saved));
})();
$('restart').addEventListener('click', restart);

// ---------- 声音：静音与音量（只记在本机，读不到时用默认值） ----------

function remember(key, value) {
  try { localStorage.setItem(`taleloom:cinematic:${key}`, value); } catch { /* 本页有效 */ }
}
function recall(key) {
  try { return localStorage.getItem(`taleloom:cinematic:${key}`); } catch { return null; }
}
function showMute() {
  $('mute').textContent = sound.muted ? '声音：关' : '声音：开';
  $('mute').setAttribute('aria-pressed', String(sound.muted));
}
$('mute').addEventListener('click', () => {
  sound.setMuted(!sound.muted);
  audioTrack.setMuted(sound.muted);
  ambientTrack.setMuted(sound.muted);
  musicTrack.setMuted(sound.muted);
  if (!sound.muted && sceneReading && !audioTrack.el) {
    audioTrack.play(sceneReading.sceneId);
    audioTrack.seekFraction(sceneReading.fraction);
    sceneReading.rebind?.();
  }
  syncDucking();
  remember('muted', sound.muted ? '1' : '0');
  showMute();
});

function showVoice() {
  $('voice').textContent = audioTrack.enabled ? '配音：开' : '配音：关';
  $('voice').setAttribute('aria-pressed', String(!audioTrack.enabled));
}
$('voice').addEventListener('click', () => {
  audioTrack.setEnabled(!audioTrack.enabled);
  remember('voice', audioTrack.enabled ? '1' : '0');
  if (audioTrack.enabled && sceneReading) {
    if (!audioTrack.el) {
      audioTrack.play(sceneReading.sceneId);
      audioTrack.seekFraction(sceneReading.fraction);
    }
    sceneReading.rebind?.();
  }
  syncDucking();
  showVoice();
});
$('volume').addEventListener('input', () => {
  const volume = Number($('volume').value) / 100;
  sound.setVolume(volume);
  audioTrack.setVolume(volume);
  ambientTrack.setVolume(volume);
  musicTrack.setVolume(volume);
  remember('volume', $('volume').value);
});
(() => {
  const volume = Number(recall('volume'));
  if (recall('volume') !== null && Number.isFinite(volume)) {
    $('volume').value = String(volume);
    sound.setVolume(volume / 100);
    audioTrack.setVolume(volume / 100);
    ambientTrack.setVolume(volume / 100);
    musicTrack.setVolume(volume / 100);
  }
  sound.setMuted(recall('muted') === '1');
  audioTrack.setMuted(sound.muted);
  ambientTrack.setMuted(sound.muted);
  musicTrack.setMuted(sound.muted);
  if (recall('voice') === '0') audioTrack.setEnabled(false);
  showMute();
  showVoice();
})();

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

// 浏览器测试用的只读状态：是否在等待玩家操作（不影响游戏）。
window.__cinematic = {
  ready: () => Boolean(view) && !busy && !desk.busy && (desk.open || !$('choices').hidden),
  sound,
};

// 提前下载运行环境，开场动画期间完成加载。
boot().catch(() => {});
