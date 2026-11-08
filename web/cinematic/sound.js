/**
 * 影像模式的声音：全部由 WebAudio 实时合成，不加载音频文件。负责人：ZC（样片）。
 *
 * 浏览器要求用户点击后才能出声，所以 start() 必须在点击事件里调用。
 */

const AMBIENCE = {
  harbor: { cutoff: 520, level: 0.16, swell: 0.09, rate: 0.11 },
  lobby: { cutoff: 260, level: 0.06, tick: true },
  office: { cutoff: 900, level: 0.11, swell: 0.07, rate: 0.19 },
  kitchen: { cutoff: 320, level: 0.05, crackle: true },
  portrait: { cutoff: 200, level: 0.04, drone: [55, 82.4] },
  ending: { cutoff: 380, level: 0.1, swell: 0.05, rate: 0.08, drone: [65.4, 98] },
  generic: { cutoff: 420, level: 0.08, swell: 0.04, rate: 0.13 },
};

export class Sound {
  constructor() {
    this.ctx = null;
    this.muted = false;
    this.current = null;
    this.bed = null;
    this.timers = [];
  }

  /** 在用户点击时创建音频环境；不支持 WebAudio 的浏览器静默跳过。 */
  start() {
    if (this.ctx) return this.ctx.resume();
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return undefined;
    this.ctx = new Context();
    this.master = this.ctx.createGain();
    this.master.gain.value = this.muted ? 0 : 0.8;
    this.master.connect(this.ctx.destination);
    const rate = this.ctx.sampleRate;
    this.noise = this.ctx.createBuffer(1, rate * 3, rate);
    const data = this.noise.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
    return this.ctx.resume();
  }

  setMuted(muted) {
    this.muted = muted;
    if (this.master) this.master.gain.setTargetAtTime(muted ? 0 : 0.8, this.ctx.currentTime, 0.08);
  }

  /** 切换环境声：旧的淡出，新的淡入。 */
  setAmbience(name) {
    if (!this.ctx || name === this.current) return;
    this.current = name;
    const preset = AMBIENCE[name] || AMBIENCE.generic;
    const now = this.ctx.currentTime;
    this.timers.forEach(clearInterval);
    this.timers = [];
    if (this.bed) {
      const old = this.bed;
      old.gain.gain.setTargetAtTime(0, now, 0.5);
      setTimeout(() => old.stop(), 3000);
    }
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.setTargetAtTime(preset.level, now, 0.8);
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = preset.cutoff;
    const source = this.ctx.createBufferSource();
    source.buffer = this.noise;
    source.loop = true;
    source.connect(filter).connect(gain).connect(this.master);
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
    if (preset.tick) this.timers.push(setInterval(() => this.burst(0.012, 'highpass', 2600, 0.05), 1000));
    if (preset.crackle) {
      this.timers.push(setInterval(() => {
        if (Math.random() < 0.3) this.burst(0.008 + Math.random() * 0.02, 'bandpass', 1200 + Math.random() * 2800, 0.03 + Math.random() * 0.07);
      }, 90));
    }
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
    source.connect(filter).connect(gain).connect(this.master);
    source.start(now, Math.random() * 2, seconds + 0.02);
  }

  /** 港口的雾笛。 */
  foghorn() {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.28, now + 0.9);
    gain.gain.setValueAtTime(0.28, now + 2.3);
    gain.gain.linearRampToValueAtTime(0, now + 3.8);
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 380;
    filter.connect(gain).connect(this.master);
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
      osc.connect(gain).connect(this.master);
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
    osc.connect(gain).connect(this.master);
    osc.start(now);
    osc.stop(now + 0.55);
    this.burst(0.08, 'lowpass', 300, 0.12);
  }
}
