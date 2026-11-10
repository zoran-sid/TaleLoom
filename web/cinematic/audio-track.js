/**
 * 影像模式的配音轨：播放预生成的场景配音（Seed Audio 生成的 MP3）。
 *
 * 每个场景一个完整音频，里面旁白与对白的顺序和 readingPages 完全一致；
 * 进入场景时自动播放对应音频，换场、静音、打开笔记、重开或回退时停止。
 * 没有对应音频的场景（其他剧本或本剧后续幕次）静默跳过，不影响画面与文字。
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
  constructor({ map = {}, audioCtor = null, root = null } = {}) {
    const win = root || (typeof window !== 'undefined' ? window : undefined);
    this.map = map;
    this.audioCtor = audioCtor || (win && typeof win.Audio === 'function' ? (src) => new win.Audio(src) : null);
    this.supported = Boolean(this.audioCtor);
    this.enabled = true;   // 配音开关
    this.muted = false;    // 主静音联动
    this.current = null;   // 当前场景 id
    this.el = null;        // 当前音频元素
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
    if (!this.supported || !this.enabled || this.muted || !src) {
      this.stop();
      return;
    }
    if (sceneId === this.current && this.el) {
      this._safePlay();
      return;
    }
    this.release();
    this.el = this.audioCtor(src);
    this.current = sceneId;
    this._safePlay();
  }

  _safePlay() {
    if (!this.el) return;
    const result = this.el.play();
    // 自动播放被拦截等情况：静默处理，不影响剧情。
    if (result && typeof result.catch === 'function') result.catch(() => {});
  }

  release() {
    if (this.el) {
      try { this.el.pause(); } catch { /* 已释放 */ }
      this.el = null;
    }
    this.current = null;
  }

  /** 完全停止并复位。 */
  stop() {
    this.release();
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    if (!enabled) this.stop();
  }

  setMuted(muted) {
    this.muted = muted;
    if (muted) this.stop();
  }

  suspend() {
    // 记下场景，resume 时接着重播这一段。
    this.suspendedScene = this.current;
    this.release();
  }

  resume() {
    if (this.suspendedScene) {
      const sceneId = this.suspendedScene;
      this.suspendedScene = null;
      this.play(sceneId);
    }
  }
}
