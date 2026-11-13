import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  Voice, ROLES, SCENE_MOOD, cleanText, splitSegments, resolveVoice, voiceParams,
} from '../../web/cinematic/voice.js';

class MockUtterance {
  constructor(text) { this.text = text; }
}

function makeSynth(voices = []) {
  const spoken = [];
  const synth = {
    getVoices: () => voices,
    speak: (u) => spoken.push(u),
    cancel: () => { spoken.length = 0; },
    onvoiceschanged: null,
  };
  return { synth, spoken };
}

const SAMPLE_VOICES = [
  { name: 'Google 普通话', lang: 'zh-CN' },
  { name: 'Sinji', lang: 'zh-HK' },
  { name: 'Ting-Ting', lang: 'zh-CN' },
  { name: 'Kang', lang: 'zh-CN' },
];

// ---------- 文本清洗 ----------

test('cleanText 去掉引号，破折号与省略号转停顿标记，空白归一', () => {
  const out = cleanText('“去旅馆——别图近。”他说……');
  assert.equal(out, '去旅馆\u001f别图近。他说\u001f');
  assert.equal(cleanText('  多个   空格 '), '多个 空格');
});

test('splitSegments 按句拆段并去除引号', () => {
  const segs = splitSegments('“你还怕我少你？”周文说。');
  assert.equal(segs.length, 2);
  assert.equal(segs[0].text, '你还怕我少你？');
  assert.equal(segs[1].text, '周文说。');
  assert.ok(segs.every((s) => !s.text.includes('“')));
});

test('破折号与省略号处给更长停顿', () => {
  const segs = splitSegments('他看见地上的血，话停了——那张纸……');
  const longPauses = segs.filter((s) => s.gap >= 300);
  assert.ok(longPauses.length >= 2);
});

test('超过 70 字的长句按逗号再拆', () => {
  const long = '他从寄存簿里找出你的行李号，左手压着纸，右手写字，又翻到上一行，把两张签摊开，请你自己对一下，明早换了掌柜，这样的小错就说不清了，必须现在核对清楚每一件货物的数目。';
  assert.ok(long.length > 70);
  const segs = splitSegments(long);
  assert.ok(segs.length > 1);
  assert.ok(segs.every((s) => s.text.length <= 70));
});

test('空文本返回空数组', () => {
  assert.deepEqual(splitSegments('“”'), []);
});

test('没有破折号或省略号时，句末保持普通停顿', () => {
  const segs = splitSegments('雨已经停了。雾涨起来。');
  assert.equal(segs.length, 2);
  assert.ok(segs.every((s) => s.gap < 300));
});

// ---------- 选声 ----------

test('resolveVoice 在无语音时返回 null', () => {
  assert.equal(resolveVoice([], ROLES['阿芸']), null);
});

test('国语优先于粤语语音', () => {
  const hit = resolveVoice(
    [{ name: 'Sinji', lang: 'zh-HK' }, { name: 'Google 普通话', lang: 'zh-CN' }], ROLES['阿芸']);
  assert.equal(hit.name, 'Google 普通话');
});

test('按角色名字偏好与性别分配不同语音', () => {
  assert.equal(resolveVoice(SAMPLE_VOICES, ROLES['阿芸']).name, 'Ting-Ting');
  assert.equal(resolveVoice(SAMPLE_VOICES, ROLES['陈掌柜']).name, 'Kang');
});

test('只有粤语语音时回退使用，不返回空', () => {
  const hit = resolveVoice([{ name: 'Sinji', lang: 'zh-HK' }], ROLES['周文']);
  assert.equal(hit.name, 'Sinji');
});

// ---------- 情绪参数 ----------

test('旁白在发现尸体场景低沉缓慢', () => {
  const normal = voiceParams('', 'p02_lobby');
  const shock = voiceParams('', 'a01_found');
  assert.ok(shock.rate < normal.rate);
  assert.ok(shock.pitch < normal.pitch);
  assert.ok(Math.abs(shock.rate - 0.92 * SCENE_MOOD.a01_found.rate) < 1e-9);
});

test('角色在特定场景的情绪覆盖生效', () => {
  const base = voiceParams('陈掌柜', 'p02_lobby');
  const stern = voiceParams('陈掌柜', 'p04_office');
  assert.ok(stern.rate < base.rate);
});

test('pitch 与 rate 被限制在合法区间', () => {
  const p = voiceParams('阿芸', 'a02_door');
  assert.ok(p.pitch >= 0 && p.pitch <= 2);
  assert.ok(p.rate >= 0.1 && p.rate <= 10);
});

// ---------- Voice 类 ----------

test('环境不支持时 supported=false，各方法静默不报错', () => {
  const v = new Voice();
  assert.equal(v.supported, false);
  v.speak('一句话');
  v.stop();
  v.init();
  v.resume();
});

test('speak 为每段创建 utterance 并带上角色音高与语言', () => {
  const { synth, spoken } = makeSynth(SAMPLE_VOICES);
  const v = new Voice({ synth, utteranceCtor: MockUtterance });
  v.init();
  v.speak('“你还怕我少你？”周文说。', { speaker: '陈掌柜', sceneId: 'p03_dinner' });
  assert.ok(spoken.length >= 1);
  const first = spoken[0];
  assert.equal(first.text, '你还怕我少你？');
  assert.equal(first.voice.name, 'Kang');
  assert.equal(first.lang, 'zh-CN');
  assert.ok(first.pitch > 0 && first.rate > 0);
});

test('没有中文语音时 lang 回退 zh-CN，仍尝试朗读', () => {
  const { synth, spoken } = makeSynth([]);
  const v = new Voice({ synth, utteranceCtor: MockUtterance });
  v.speak('雾从水面涨起来。', { speaker: '', sceneId: 'p01_dock' });
  assert.equal(spoken[0].lang, 'zh-CN');
  assert.equal(spoken[0].voice, undefined);
});

test('stop 调用 cancel 并阻止后续段落', async () => {
  const { synth, spoken } = makeSynth(SAMPLE_VOICES);
  const v = new Voice({ synth, utteranceCtor: MockUtterance });
  v.speak('第一句。第二句。第三句。', { speaker: '周文' });
  const before = spoken.length;
  v.stop();
  await new Promise((r) => setTimeout(r, 300));
  assert.equal(spoken.length, before === 0 ? 0 : 0); // cancel 清空，且旧 onend 不会再入队
});

test('配音关闭或主静音后不发声', () => {
  const { synth, spoken } = makeSynth(SAMPLE_VOICES);
  const v = new Voice({ synth, utteranceCtor: MockUtterance });
  v.setEnabled(false);
  v.speak('听不到的一句。');
  assert.equal(spoken.length, 0);

  const other = makeSynth(SAMPLE_VOICES);
  const v2 = new Voice({ synth: other.synth, utteranceCtor: MockUtterance });
  v2.setMuted(true);
  v2.speak('也听不到。');
  assert.equal(other.spoken.length, 0);
});

test('onend 后按停顿依次播放下一段', async () => {
  const { synth, spoken } = makeSynth(SAMPLE_VOICES);
  const v = new Voice({ synth, utteranceCtor: MockUtterance });
  v.speak('第一句。第二句。', { speaker: '阿芸' });
  assert.equal(spoken.length, 1);
  spoken[0].onend();
  await new Promise((r) => setTimeout(r, 400));
  assert.equal(spoken.length, 2);
  assert.equal(spoken[1].text, '第二句。');
});

test('旧队列的 onend 在重新 speak 后不会串入新队列', async () => {
  const { synth, spoken } = makeSynth(SAMPLE_VOICES);
  const v = new Voice({ synth, utteranceCtor: MockUtterance });
  v.speak('第一句。第二句。', { speaker: '周文' });
  const stale = spoken[0];
  v.speak('新的一句。', { speaker: '阿水' });
  stale.onend(); // 旧 token，应被忽略
  await new Promise((r) => setTimeout(r, 300));
  assert.equal(spoken.at(-1).text, '新的一句。');
});
