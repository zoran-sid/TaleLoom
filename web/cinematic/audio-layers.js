/** 独立的录音素材播放层。URL 只来自受控 manifest，不接收剧情或用户输入。 */
export class SampledLayers {
  constructor(ctx, master, manifest, fetcher = (url) => fetch(url)) {
    this.ctx = ctx;
    this.manifest = manifest;
    this.fetcher = fetcher;
    this.cache = new Map();
    this.active = { bgm: null, ambience: null };
    this.versions = { bgm: 0, ambience: 0 };
    this.voice = null;
    this.voiceVersion = 0;
    this.duckTargets = [];
    this.buses = {};
    for (const layer of ['bgm', 'ambience', 'sfx', 'voice']) {
      const bus = ctx.createGain();
      bus.gain.value = 1;
      bus.connect(master);
      this.buses[layer] = bus;
    }
  }

  /** 下载与解码只做一次；失败从缓存移除，允许下次重试。 */
  async load(id) {
    const asset = this.manifest[id];
    if (!asset?.url) return null;
    if (!this.cache.has(id)) {
      const pending = Promise.resolve().then(() => this.fetcher(asset.url))
        .then((response) => { if (!response.ok) throw new Error(`Audio HTTP ${response.status}`); return response.arrayBuffer(); })
        .then((bytes) => this.ctx.decodeAudioData(bytes));
      this.cache.set(id, pending);
      pending.catch(() => this.cache.delete(id));
    }
    try { return await this.cache.get(id); } catch { return null; }
  }

  /** 在玩家阅读上一场景时预取，失败不影响剧情。 */
  async preload(ids) {
    await Promise.all(ids.map((id) => this.load(id)));
  }

  /** 同轨不重播；旧轨渐退，新轨渐入；旧请求在切场后作废。 */
  async setBed(layer, id) {
    if (!['bgm', 'ambience'].includes(layer)) return false;
    const version = ++this.versions[layer];
    const current = this.active[layer];
    if (current?.id === id) return true;
    if (id && this.manifest[id]?.layer !== layer) return false;
    const buffer = id ? await this.load(id) : null;
    if (version !== this.versions[layer]) return false;
    if (id && !buffer) {
      if (current) {
        current.gain.gain.setValueAtTime(current.gain.gain.value, this.ctx.currentTime);
        current.gain.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 0.5);
        current.source.stop(this.ctx.currentTime + 0.55);
        this.active[layer] = null;
      }
      return false;
    }
    const now = this.ctx.currentTime;
    const fade = layer === 'bgm' ? 2.5 : 1.5;
    if (current) {
      current.gain.gain.cancelScheduledValues(now);
      current.gain.gain.setValueAtTime(current.gain.gain.value, now);
      current.gain.gain.linearRampToValueAtTime(0, now + fade);
      current.source.stop(now + fade + 0.05);
      this.active[layer] = null;
    }
    if (!id) return true;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(this.manifest[id].gain ?? 0.5, now + fade);
    gain.connect(this.buses[layer]);
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.connect(gain);
    source.start(now);
    source.onended = () => { source.disconnect(); gain.disconnect(); };
    this.active[layer] = { id, source, gain };
    return true;
  }

  /** 重要拟音短时压低配乐，随后平滑恢复。 */
  async playSfx(id) {
    if (this.manifest[id]?.layer !== 'sfx') return false;
    const buffer = await this.load(id);
    if (!buffer) return false;
    const now = this.ctx.currentTime;
    const music = this.buses.bgm.gain;
    music.cancelScheduledValues(now);
    music.setValueAtTime(music.value, now);
    music.linearRampToValueAtTime(0.55, now + 0.08);
    music.linearRampToValueAtTime(1, now + Math.min(buffer.duration + 0.6, 4));
    const source = this.ctx.createBufferSource();
    const gain = this.ctx.createGain();
    gain.gain.value = this.manifest[id].gain ?? 0.7;
    source.buffer = buffer;
    source.connect(gain).connect(this.buses.sfx);
    source.onended = () => { source.disconnect(); gain.disconnect(); };
    source.start(now);
    return true;
  }

  /** 单句对白与玩家当前阅读段落绑定；过期下载和连续点击不会串音。 */
  async playVoice(id) {
    this.stopVoice();
    const version = this.voiceVersion;
    if (this.manifest[id]?.layer !== 'voice') return false;
    const buffer = await this.load(id);
    if (!buffer || version !== this.voiceVersion) return false;
    const now = this.ctx.currentTime;
    const source = this.ctx.createBufferSource();
    const gain = this.ctx.createGain();
    gain.gain.value = this.manifest[id].gain ?? 1;
    source.buffer = buffer;
    source.connect(gain).connect(this.buses.voice);
    const voice = { id, source, gain };
    source.onended = () => {
      source.disconnect();
      gain.disconnect();
      if (this.voice === voice) { this.voice = null; this.restoreDucking(); }
    };
    this.voice = voice;
    for (const control of [this.buses.bgm.gain, this.buses.ambience.gain, ...this.duckTargets]) {
      control.cancelScheduledValues(now);
      control.setValueAtTime(control.value, now);
      control.linearRampToValueAtTime(0.45, now + 0.12);
    }
    source.start(now);
    return true;
  }

  /** 用户切换段落时立刻停句并恢复音乐和环境声。 */
  stopVoice() {
    this.voiceVersion += 1;
    const voice = this.voice;
    this.voice = null;
    if (voice) voice.source.stop();
    this.restoreDucking();
  }

  restoreDucking() {
    const now = this.ctx.currentTime;
    for (const control of [this.buses.bgm.gain, this.buses.ambience.gain, ...this.duckTargets]) {
      control.cancelScheduledValues(now);
      control.setValueAtTime(control.value, now);
      control.linearRampToValueAtTime(1, now + 0.2);
    }
  }

  /** 清理录音轨道；暂停与静音由共享 AudioContext 和总音量处理。 */
  dispose() {
    this.stopVoice();
    for (const layer of ['bgm', 'ambience']) {
      this.versions[layer] += 1;
      if (this.active[layer]) this.active[layer].source.stop();
      this.active[layer] = null;
    }
    this.cache.clear();
  }
}
