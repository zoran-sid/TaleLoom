/** Optional recorded ambience layer; procedural Sound remains the fallback. */
export class AmbientTrack {
  constructor({ map = {}, audioCtor = null, root = null } = {}) {
    const win = root || (typeof window !== 'undefined' ? window : undefined);
    this.map = map;
    this.audioCtor = audioCtor || (win && typeof win.Audio === 'function' ? (src) => new win.Audio(src) : null);
    this.current = null;
    this.el = null;
    this.volume = 0.8;
    this.muted = false;
    this.ducked = false;
    this.fadeTimer = null;
    this.fadingOut = null;
    this.onError = null;
    win?.document?.addEventListener('visibilitychange', () => {
      if (win.document.hidden) this.suspend();
      else this.resume();
    });
  }

  level() { return this.muted ? 0 : this.volume * (this.ducked ? 0.24 : 0.52); }

  set(name) {
    const src = this.map[name];
    if (name === this.current && this.el) return true;
    const old = this.el;
    const oldLevel = old?.volume || 0;
    clearInterval(this.fadeTimer);
    this.fadingOut?.pause();
    this.fadingOut = old;
    this.current = src ? name : null;
    this.el = src && this.audioCtor ? this.audioCtor(src) : null;
    const next = this.el;
    if (next) {
      next.loop = true;
      next.preload = 'auto';
      next.volume = 0;
      next.addEventListener?.('error', () => {
        if (this.el === next) { this.stop(); this.onError?.(name); }
      });
      this._safePlay(next, name);
    }
    let step = 0;
    this.fadeTimer = setInterval(() => {
      step += 1;
      const progress = Math.min(1, step / 12);
      if (old) old.volume = oldLevel * (1 - progress);
      if (next && this.el === next) next.volume = this.level() * progress;
      if (progress === 1) {
        clearInterval(this.fadeTimer);
        this.fadeTimer = null;
        old?.pause();
        if (this.fadingOut === old) this.fadingOut = null;
      }
    }, 50);
    return Boolean(next);
  }

  _safePlay(el, name) {
    try {
      const result = el.play();
      result?.catch?.(() => { if (this.el === el) { this.stop(); this.onError?.(name); } });
    } catch {
      if (this.el === el) { this.stop(); this.onError?.(name); }
    }
  }

  setVolume(value) { this.volume = Math.min(1, Math.max(0, value)); if (this.el) this.el.volume = this.level(); }
  setMuted(value) { this.muted = value; if (this.el) this.el.volume = this.level(); }
  setDucked(value) { this.ducked = value; if (this.el) this.el.volume = this.level(); }
  suspend() { this.el?.pause(); }
  resume() { if (this.el) this._safePlay(this.el, this.current); }
  stop() {
    clearInterval(this.fadeTimer);
    this.fadeTimer = null;
    this.el?.pause();
    this.fadingOut?.pause();
    this.fadingOut = null;
    this.el = null;
    this.current = null;
  }
}
