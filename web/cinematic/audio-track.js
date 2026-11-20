/**
 * 影像模式的配音轨：播放预生成的场景和选择反馈 MP3。
 *
 * 每个录音覆盖一段完整文字，旁白与对白的顺序和 readingPages 一致；
 * 字幕开始时播放对应音频；播放进度可驱动字幕翻页。
 * 没有对应音频的文字保持手动阅读，不影响画面与剧情。
 *
 * 本文件只含 AudioTrack 类，不直接 import 音频，map 与 Audio 构造器均可注入，
 * 便于在 Node 中单元测试；真实的场景→音频映射见 audio-assets.js。
 */
export class AudioTrack {
  /**
   * @param map 场景→音频 URL 的映射（可注入）
   * @param audioCtor 返回带 play/pause 的音频元素的工厂（可注入）
   * @param root 浏览器 window，用于能力检测与后台事件
   */
  constructor({ map = {}, audioCtor = null, root = null, onProgress = null } = {}) {
    const win = root || (typeof window !== 'undefined' ? window : undefined);
    this.map = map;
    this.audioCtor = audioCtor || (win && typeof win.Audio === 'function' ? (src) => new win.Audio(src) : null);
    this.onProgress = onProgress;
    this.supported = Boolean(this.audioCtor);
    this.enabled = true;   // 配音开关
    this.muted = false;    // 主静音联动
    this.volume = 0.8;
    this.current = null;   // 当前场景 id
    this.el = null;        // 当前音频元素
    this.pendingSeek = null;
    this.suspendedScene = null;
    if (win && typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) this.suspend();
        else this.resume();
      });
    }
  }

  /** 播放某场景的配音；同一场景不重复加载，无音频的场景停止当前播放。 */
  play(sceneId) {
    const src = this.map[sceneId];
    if (!this.supported || !src) {
      this.stop();
      return;
    }
    if (sceneId === this.current && this.el) {
      if (this.enabled && !this.muted) this._safePlay();
      return;
    }
    if (!this.enabled || this.muted) {
      this.stop();
      return;
    }
    this.release();
    this.el = this.audioCtor(src);
    this.el.volume = this.volume;
    this.current = sceneId;
    this.progressListener = () => this.onProgress?.({ id: this.current, time: this.el?.currentTime || 0,
      duration: this.el?.duration || 0 });
    this.seekWhenReady = () => {
      if (this.pendingSeek !== null) this.seekFraction(this.pendingSeek);
    };
    this.el.addEventListener?.('timeupdate', this.progressListener);
    this.el.addEventListener?.('durationchange', this.seekWhenReady);
    this.el.addEventListener?.('loadedmetadata', this.seekWhenReady);
    this._safePlay();
  }

  _safePlay() {
    if (!this.el) return;
    const result = this.el.play();
    // 自动播放被拦截等情况：静默处理，不影响剧情。
    if (result && typeof result.catch === 'function') result.catch(() => {});
  }

  /** 监听当前音频达到指定比例；返回取消监听函数。未加载音频时由玩家手动翻页。 */
  watchFraction(fraction, callback) {
    const el = this.el;
    if (!el || !Number.isFinite(fraction) || typeof el.addEventListener !== 'function') return () => {};
    let finished = false;
    const cleanup = () => {
      finished = true;
      el.removeEventListener('timeupdate', check);
      el.removeEventListener('durationchange', check);
      el.removeEventListener('ended', check);
    };
    const check = () => {
      if (finished || this.el !== el || !Number.isFinite(el.duration) || el.duration <= 0) return;
      if (el.ended || el.currentTime >= el.duration * fraction) {
        cleanup();
        callback();
      }
    };
    el.addEventListener('timeupdate', check);
    el.addEventListener('durationchange', check);
    el.addEventListener('ended', check);
    queueMicrotask(check);
    return cleanup;
  }

  seekFraction(fraction) {
    if (!this.el || !Number.isFinite(fraction)) return;
    const duration = this.el.duration;
    // 换场后可能先收到跳页操作，再知道录音时长。只保留当前录音的最后一次跳转。
    if (!Number.isFinite(duration) || duration <= 0) {
      this.pendingSeek = fraction;
      return;
    }
    this.pendingSeek = null;
    this.el.currentTime = Math.min(1, Math.max(0, fraction)) * duration;
  }

  release() {
    if (this.el) {
      if (this.progressListener) this.el.removeEventListener?.('timeupdate', this.progressListener);
      this.el.removeEventListener?.('durationchange', this.seekWhenReady);
      this.el.removeEventListener?.('loadedmetadata', this.seekWhenReady);
      try { this.el.pause(); } catch { /* 已释放 */ }
      this.el = null;
    }
    this.progressListener = null;
    this.seekWhenReady = null;
    this.pendingSeek = null;
    this.current = null;
  }

  /** 完全停止并复位。 */
  stop() {
    this.release();
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    if (!enabled && this.el) this.el.pause();
    else if (enabled && !this.muted) this._safePlay();
  }

  setMuted(muted) {
    this.muted = muted;
    if (muted && this.el) this.el.pause();
    else if (!muted && this.enabled) this._safePlay();
  }

  setVolume(volume) {
    this.volume = Math.min(1, Math.max(0, volume));
    if (this.el) this.el.volume = this.volume;
  }

  suspend() {
    this.suspendedScene = this.current;
    if (this.el) this.el.pause();
  }

  resume() {
    if (this.suspendedScene) {
      const sceneId = this.suspendedScene;
      this.suspendedScene = null;
      if (this.el && this.current === sceneId && this.enabled && !this.muted) this._safePlay();
    }
  }
}
