/**
 * 影像模式声音：现有 Web Audio 合成音作为降级层，审核过的录音素材可按剧情叠加。负责人：ZC。
 *
 * 浏览器要求用户点击后才能出声，所以 start() 必须在点击事件里调用。
 * 页面转入后台时暂停整个音频环境并停掉周期性的拟音，回来时再接上，避免积压后叠加播放。
 * 重要的声音通过 onCaption 回调给出文字说明，听不见时线索仍然完整。
 */
import { SampledLayers } from './audio-layers.js';
import { AUDIO_ASSETS } from './audio-assets.js';
import { ambienceLabel, musicLabel, PROCEDURAL_AMBIENCE, PROCEDURAL_MUSIC, preloadFor } from './audio-cues.js';
import { voiceFor, voicesForScene } from './voice-cues.js';

// 环境声的文字说明，切换时显示一次。
const AMBIENCE_TEXT = {
  harbor: '港口的风浪', lobby: '座钟的嘀嗒与炉火', office: '窗外的风', kitchen: '灶火噼啪', portrait: '低沉的嗡鸣',
  ending: '清晨的海浪', rain: '雨声', storm: '风暴', tension: '紧张的低鸣', dinner: '碗筷与炉火', dutyroom: '挂钟与远处的水声',
  ledger: '灯芯的轻响',
};

// 场景配乐：慢速和弦铺底，偶尔一个五声音阶的单音。root 为根音频率，chords 为相对半音。
const MUSIC = {
  calm: { text: '舒缓的弦乐', root: 220, chords: [[0, 4, 7], [5, 9, 12], [-3, 0, 4], [7, 11, 14]], every: 7, level: 0.05, melody: 0.5 },
  study: { text: '低回的思索', root: 196, chords: [[0, 3, 7], [-4, 0, 3], [5, 8, 12], [3, 7, 10]], every: 8, level: 0.04, melody: 0.35 },
  tense: { text: '紧张的低音', root: 146.8, chords: [[0, 3, 7], [1, 4, 8], [0, 3, 6]], every: 9, level: 0.04, melody: 0 },
  dark: { text: '沉郁的和声', root: 110, chords: [[0, 3, 7], [-2, 1, 5]], every: 10, level: 0.045, melody: 0.15 },
  dawn: { text: '天亮的旋律', root: 261.6, chords: [[0, 4, 7], [-5, -1, 2], [-3, 0, 4], [5, 9, 12]], every: 6, level: 0.05, melody: 0.6 },
};
const PENTATONIC = [0, 2, 4, 7, 9, 12, 14];

const AMBIENCE = {
  harbor: { cutoff: 520, level: 0.16, swell: 0.09, rate: 0.11 },
  lobby: { cutoff: 260, level: 0.06, tick: true },
  office: { cutoff: 900, level: 0.11, swell: 0.07, rate: 0.19 },
  kitchen: { cutoff: 320, level: 0.05, crackle: true },
  portrait: { cutoff: 200, level: 0.04, drone: [55, 82.4] },
  ending: { cutoff: 380, level: 0.1, swell: 0.05, rate: 0.08, drone: [65.4, 98] },
  generic: { cutoff: 420, level: 0.08, swell: 0.04, rate: 0.13 },
  rain: { cutoff: 2400, level: 0.04, drips: true },
  attic: { cutoff: 260, level: 0.04, drone: [73.4] },
  storm: { cutoff: 1100, level: 0.26, swell: 0.18, rate: 0.3 },
  tension: { cutoff: 160, level: 0.05, drone: [49, 51.5] },
  ship: { cutoff: 240, level: 0.05, drone: [55, 110] },
  alarm: { cutoff: 240, level: 0.05, drone: [55, 110], beep: true },
  reactor: { cutoff: 200, level: 0.06, drone: [41.2, 82.4], swell: 0.04, rate: 0.5 },
  workshop: { cutoff: 260, level: 0.05, drone: [55], crackle: true },
  space: { cutoff: 120, level: 0.02, drone: [36.7] },
  dinner: { cutoff: 300, level: 0.05, crackle: true, tick: true },
  dutyroom: { cutoff: 600, level: 0.07, swell: 0.04, rate: 0.12, tick: true },
  ledger: { cutoff: 220, level: 0.03, drone: [61.7] },
};

export class Sound {
  constructor() {
    this.ctx = null;
    this.muted = false;
    this.volume = 0.8;
    this.current = null;
    this.preset = null;
    this.bed = null;
    this.timers = [];
    this.hidden = false;
    this.onCaption = null;
    this.music = null;          // 当前配乐 { name, gain, timer, step }
    this.samples = null;
    this.narrativeVersion = 0;
    document.addEventListener('visibilitychange', () => (document.hidden ? this.suspend() : this.resume()));
  }

  level() {
    return this.muted ? 0 : this.volume;
  }

  caption(text) {
    if (this.ctx && this.onCaption) this.onCaption(text);
  }

  /** 在用户点击时创建音频环境；不支持 WebAudio 的浏览器静默跳过。 */
  start() {
    if (this.ctx) return this.ctx.resume();
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return undefined;
    this.ctx = new Context();
    this.master = this.ctx.createGain();
    this.master.gain.value = this.level();
    this.master.connect(this.ctx.destination);
    this.procedural = this.ctx.createGain();
    this.procedural.gain.value = 1;
    this.procedural.connect(this.master);
    this.samples = new SampledLayers(this.ctx, this.master, AUDIO_ASSETS);
    this.samples.duckTargets = [this.procedural.gain];
    const rate = this.ctx.sampleRate;
    this.noise = this.ctx.createBuffer(1, rate * 3, rate);
    const data = this.noise.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
    return this.ctx.resume();
  }

  setMuted(muted) {
    this.muted = muted;
    if (this.master) this.master.gain.setTargetAtTime(this.level(), this.ctx.currentTime, 0.08);
  }

  /** 音量 0–1；静音时只记下，取消静音后生效。 */
  setVolume(volume) {
    this.volume = Math.min(1, Math.max(0, volume));
    if (this.master) this.master.gain.setTargetAtTime(this.level(), this.ctx.currentTime, 0.08);
  }

  /** 页面转入后台：停掉周期拟音并暂停音频环境。 */
  suspend() {
    this.hidden = true;
    this.timers.forEach(clearInterval);
    this.timers = [];
    if (this.music) clearInterval(this.music.timer);
    if (this.ctx) this.ctx.suspend();
  }

  /** 回到前台：恢复音频环境，重新接上当前环境声的周期拟音（不重播错过的部分）。 */
  resume() {
    this.hidden = false;
    if (!this.ctx) return;
    this.ctx.resume();
    if (!this.timers.length && this.preset) this.startTimers(this.preset);
    if (this.music) this.playMusic(this.music);
  }

  startTimers(preset) {
    if (this.hidden) return;
    if (preset.tick) this.timers.push(setInterval(() => this.burst(0.012, 'highpass', 2600, 0.05), 1000));
    if (preset.beep) this.timers.push(setInterval(() => this.beep(), 1400));
    if (preset.drips) {
      this.timers.push(setInterval(() => {
        if (Math.random() < 0.45) this.burst(0.006, 'highpass', 3200 + Math.random() * 2000, 0.05 + Math.random() * 0.05);
      }, 160));
    }
    if (preset.crackle) {
      this.timers.push(setInterval(() => {
        if (Math.random() < 0.3) this.burst(0.008 + Math.random() * 0.02, 'bandpass', 1200 + Math.random() * 2800, 0.03 + Math.random() * 0.07);
      }, 90));
    }
  }

  /** 切换环境声：旧的淡出，新的淡入。 */
  setAmbience(name) {
    if (!this.ctx || name === this.current) return;
    this.current = name;
    const preset = name ? AMBIENCE[name] || AMBIENCE.generic : null;
    this.preset = preset;
    if (AMBIENCE_TEXT[name]) this.caption(`环境声：${AMBIENCE_TEXT[name]}`);
    const now = this.ctx.currentTime;
    this.timers.forEach(clearInterval);
    this.timers = [];
    if (this.bed) {
      const old = this.bed;
      old.gain.gain.setTargetAtTime(0, now, 0.5);
      setTimeout(() => old.stop(), 3000);
      this.bed = null;
    }
    if (!preset) return;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.setTargetAtTime(preset.level, now, 0.8);
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = preset.cutoff;
    const source = this.ctx.createBufferSource();
    source.buffer = this.noise;
    source.loop = true;
    source.connect(filter).connect(gain).connect(this.procedural);
    source.start();
    const nodes = [source];
    if (preset.swell) {
      const lfo = this.ctx.createOscillator();
      const depth = this.ctx.createGain();
      lfo.frequency.value = preset.rate;
      depth.gain.value = preset.swell;
      lfo.connect(depth).connect(gain.gain);
      lfo.start();
      nodes.push(lfo);
    }
    for (const hz of preset.drone || []) {
      const osc = this.ctx.createOscillator();
      const level = this.ctx.createGain();
      osc.frequency.value = hz;
      level.gain.value = 0.35;
      osc.connect(level).connect(gain);
      osc.start();
      nodes.push(osc);
    }
    this.bed = { gain, stop: () => nodes.forEach((node) => { try { node.stop(); } catch { /* 已停止 */ } }) };
    this.startTimers(preset);
  }

  /** 一小段过滤后的噪声：钟摆、柴火、脚步都用它。 */
  burst(seconds, type, frequency, level) {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const source = this.ctx.createBufferSource();
    source.buffer = this.noise;
    const filter = this.ctx.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = frequency;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(level, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + seconds);
    source.connect(filter).connect(gain).connect(this.procedural);
    source.start(now, Math.random() * 2, seconds + 0.02);
  }

  /** 飞船警报的短促提示音。 */
  beep() {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'square';
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.setValueAtTime(660, now + 0.18);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.035, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.36);
    osc.connect(gain).connect(this.procedural);
    osc.start(now);
    osc.stop(now + 0.4);
  }

  /** 港口的雾笛。 */
  foghorn() {
    if (!this.ctx) return;
    this.caption('远处传来雾笛');
    const now = this.ctx.currentTime;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.28, now + 0.9);
    gain.gain.setValueAtTime(0.28, now + 2.3);
    gain.gain.linearRampToValueAtTime(0, now + 3.8);
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 380;
    filter.connect(gain).connect(this.procedural);
    for (const [hz, level] of [[61.7, 1], [62.4, 1], [123.5, 0.3]]) {
      const osc = this.ctx.createOscillator();
      const part = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.value = hz;
      part.gain.value = level;
      osc.connect(part).connect(filter);
      osc.start(now);
      osc.stop(now + 4);
    }
  }

  /** 获得线索时的轻响。 */
  bell() {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    for (const [hz, level] of [[1318.5, 0.06], [1975.5, 0.035]]) {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.frequency.value = hz;
      gain.gain.setValueAtTime(level, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 2.2);
      osc.connect(gain).connect(this.procedural);
      osc.start(now);
      osc.stop(now + 2.3);
    }
  }

  /** 转场时的低沉一声（关门）。 */
  thud() {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.frequency.setValueAtTime(70, now);
    osc.frequency.exponentialRampToValueAtTime(38, now + 0.4);
    gain.gain.setValueAtTime(0.22, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.5);
    osc.connect(gain).connect(this.procedural);
    osc.start(now);
    osc.stop(now + 0.55);
    this.burst(0.08, 'lowpass', 300, 0.12);
  }

  // ---------- 调查台的拟音 ----------

  tone(hz, seconds, level, type = 'sine', endHz = hz) {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(hz, now);
    osc.frequency.exponentialRampToValueAtTime(endHz, now + seconds);
    gain.gain.setValueAtTime(level, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + seconds);
    osc.connect(gain).connect(this.procedural);
    osc.start(now);
    osc.stop(now + seconds + 0.05);
  }

  /** 翻纸。 */
  paper() {
    this.burst(0.16, 'bandpass', 2400, 0.08);
    setTimeout(() => this.burst(0.09, 'bandpass', 3600, 0.05), 90);
  }

  /** 笔尖落在册子上。 */
  pen() {
    for (let i = 0; i < 3; i += 1) setTimeout(() => this.burst(0.025, 'highpass', 4200 + i * 400, 0.035), i * 45);
  }

  /** 核对无误，落章。 */
  stamp() {
    if (!this.ctx) return;
    this.caption('落章：核对无误');
    this.tone(150, 0.22, 0.25, 'sine', 55);
    this.burst(0.07, 'lowpass', 900, 0.14);
  }

  /** 核对没有通过：两声低沉的轻响。 */
  wrong() {
    if (!this.ctx) return;
    this.caption('核对没有通过');
    this.tone(233, 0.18, 0.06, 'triangle', 220);
    setTimeout(() => this.tone(185, 0.26, 0.06, 'triangle', 174), 150);
  }

  /** 缸里的水声。 */
  water() {
    if (!this.ctx) return;
    this.caption('水声');
    this.burst(0.5, 'lowpass', 500, 0.08);
    for (let i = 0; i < 3; i += 1) setTimeout(() => this.tone(900 + Math.random() * 600, 0.08, 0.03, 'sine', 500), 120 + i * 140);
  }

  // ---------- 场景配乐 ----------

  /** 切换配乐：旧的淡出，新的淡入；同名不重启。name 为空时停止配乐。 */
  setMusic(name) {
    if (!this.ctx || (this.music?.name || null) === (name || null)) return;
    const now = this.ctx.currentTime;
    if (this.music) {
      const old = this.music;
      clearInterval(old.timer);
      old.gain.gain.setTargetAtTime(0, now, 1.2);
      setTimeout(() => old.gain.disconnect(), 6000);
    }
    this.music = null;
    const preset = MUSIC[name];
    if (!preset) return;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.setTargetAtTime(preset.level, now, 1.5);
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 1400;
    gain.connect(filter).connect(this.procedural);
    this.music = { name, preset, gain, timer: null, step: 0 };
    this.caption(`配乐：${preset.text}`);
    this.playMusic(this.music);
  }

  /** 按引擎快照选定的声音意图播放；录音失败时继续使用现有合成声。 */
  setNarrativeCue(cue) {
    if (!this.ctx || !cue) return;
    const version = ++this.narrativeVersion;
    const music = cue.music;
    const ambience = cue.ambience;
    if (this.samples.active.bgm?.id !== music) this.setMusic(PROCEDURAL_MUSIC[music] || 'study');
    if (this.samples.active.ambience?.id !== ambience) this.setAmbience(PROCEDURAL_AMBIENCE[ambience] || ambience);
    for (const [layer, id] of [['bgm', music], ['ambience', ambience]]) {
      const available = AUDIO_ASSETS[id]?.layer === layer ? id : null;
      const already = this.samples.active[layer]?.id === available;
      this.samples.setBed(layer, available).then((played) => {
        if (version !== this.narrativeVersion || !played || !available || already) return;
        if (layer === 'bgm') {
          this.setMusic(null);
          this.caption(`配乐：${musicLabel(music)}`);
        } else {
          this.setAmbience(null);
          this.caption(`环境声：${ambienceLabel(ambience)}`);
        }
      });
    }
  }

  /** 玩家阅读前一场景时，后台准备下一场景会用到的素材。 */
  preloadNarrativeFor(view) {
    if (!this.samples) return;
    const ids = [...preloadFor(view), ...voicesForScene(view)].filter((id) => AUDIO_ASSETS[id]);
    if (ids.length) void this.samples.preload(ids);
  }

  /** 当前文字段落若有对应的原句录音，播放该角色一句。 */
  playVoiceFor(view, page) {
    const id = voiceFor(view, page);
    if (id && this.samples) void this.samples.playVoice(id);
  }

  stopVoice() {
    this.samples?.stopVoice();
  }

  /** 引擎场景事件的拟音；录音不可用时使用已有翻纸声。 */
  playNarrativeSfx(id) {
    if (!this.ctx || !id) return;
    if (id === 'ledger_paper') this.caption('翻开账页');
    if (AUDIO_ASSETS[id]) this.samples.playSfx(id).then((played) => { if (!played && id === 'ledger_paper') this.paper(); });
    else if (id === 'ledger_paper') this.paper();
  }

  playMusic(music) {
    if (this.hidden) return;
    clearInterval(music.timer);
    const bar = () => this.chord(music);
    bar();
    music.timer = setInterval(bar, music.preset.every * 1000);
  }

  /** 一个和弦：三个慢起慢落的音，偶尔加一个高处的单音。 */
  chord(music) {
    if (!this.ctx || this.music !== music) return;
    const { root, chords, every, melody } = music.preset;
    const notes = chords[music.step % chords.length];
    music.step += 1;
    const now = this.ctx.currentTime;
    const hz = (semi) => root * 2 ** (semi / 12);
    for (const semi of notes) {
      for (const [type, detune, level] of [['triangle', -4, 0.5], ['sine', 5, 0.35]]) {
        const osc = this.ctx.createOscillator();
        const env = this.ctx.createGain();
        osc.type = type;
        osc.frequency.value = hz(semi);
        osc.detune.value = detune;
        env.gain.setValueAtTime(0.0001, now);
        env.gain.exponentialRampToValueAtTime(level, now + 1.6);
        env.gain.setValueAtTime(level, now + every - 1.2);
        env.gain.exponentialRampToValueAtTime(0.0001, now + every + 1.4);
        osc.connect(env).connect(music.gain);
        osc.start(now);
        osc.stop(now + every + 1.5);
      }
    }
    if (Math.random() < melody) {
      const at = now + 1 + Math.random() * (every - 2);
      const osc = this.ctx.createOscillator();
      const env = this.ctx.createGain();
      osc.frequency.value = hz(12 + PENTATONIC[Math.floor(Math.random() * PENTATONIC.length)] + notes[0]);
      env.gain.setValueAtTime(0.0001, at);
      env.gain.exponentialRampToValueAtTime(0.4, at + 0.08);
      env.gain.exponentialRampToValueAtTime(0.0001, at + 2.2);
      osc.connect(env).connect(music.gain);
      osc.start(at);
      osc.stop(at + 2.3);
    }
  }
}
