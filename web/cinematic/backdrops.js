/**
 * 场景背景镜头：MiniMax 生成的手绘动画镜头，按场景 ID 选用。负责人：ZC。
 *
 * 每个影像版场景对应 media/ 下的一个镜头（映射见 backdrops.json）：
 * - 循环镜头：<id>.mp4 无声循环播放，<id>.jpg 是它的第一帧；
 * - 静帧镜头（已有的转场）：转场播完后停在 <id>.jpg（转场的最后一帧）上。
 * 先显示静帧，视频能播放时再淡入；关闭动态效果、快速模式或暂停时只显示静帧。
 * 镜头尚未生成时用 backdrops.json 的 alternates 里内容相符的已有镜头；
 * 仍找不到或素材加载失败时返回 false，由调用方退回代码绘制的画面。
 */
import table from './backdrops.json';

const files = import.meta.glob('./media/*.{mp4,jpg}', { eager: true, query: '?url', import: 'default' });
const url = (name) => files[`./media/${name}`];
const stills = new Set(table.stills);

/** 场景对应的镜头素材；没有映射或缺少静帧时为 null。 */
export function backdropFor(storyId, sceneId) {
  let clip = table.stories[storyId]?.[sceneId];
  // 镜头还没有生成时，改用 alternates 里内容相符的已有镜头。
  if (clip && !url(`${clip}.jpg`)) clip = table.alternates[clip];
  const poster = clip && url(`${clip}.jpg`);
  if (!poster) return null;
  return { clip, poster, video: stills.has(clip) ? undefined : url(`${clip}.mp4`) };
}

export class Backdrop {
  /**
   * @param {HTMLElement} root 容器，内含一张 <img> 和一个 <video>
   * @param {{ motion: () => boolean }} options motion() 为 false 时只显示静帧
   */
  constructor(root, { motion }) {
    this.root = root;
    this.image = root.querySelector('img');
    this.video = root.querySelector('video');
    this.motion = motion;
    this.clip = null;
    this.onFail = null;
    this.image.addEventListener('error', () => this.fail());
    this.video.addEventListener('error', () => this.stopVideo());
    this.video.addEventListener('playing', () => { this.video.dataset.visible = ''; });
    document.addEventListener('visibilitychange', () => (document.hidden ? this.pause() : this.resume()));
  }

  /** 显示场景的镜头；同一镜头连续出现时不重新加载。没有镜头时隐藏并返回 false。 */
  show(storyId, sceneId, onFail) {
    const asset = backdropFor(storyId, sceneId);
    if (!asset) {
      this.hide();
      return false;
    }
    this.onFail = onFail;
    this.root.hidden = false;
    if (asset.clip === this.clip) {
      this.resume();
      return true;
    }
    this.clip = asset.clip;
    this.root.dataset.clip = asset.clip;
    this.root.dataset.still = asset.video ? '0' : '1';
    this.stopVideo();
    this.image.src = asset.poster;
    this.source = asset.video;
    this.resume();
    return true;
  }

  hide() {
    this.stopVideo();
    this.clip = null;
    this.source = undefined;
    this.root.hidden = true;
    delete this.root.dataset.clip;
  }

  fail() {
    const recover = this.onFail;
    this.hide();
    recover?.();
  }

  stopVideo() {
    delete this.video.dataset.visible;
    this.video.pause();
    if (this.video.getAttribute('src')) {
      this.video.removeAttribute('src');
      this.video.load();
    }
  }

  pause() {
    this.video.pause();
  }

  /** 允许动态效果时播放循环镜头；否则停在静帧上。 */
  resume() {
    if (!this.source || this.root.hidden || document.hidden) return;
    if (!this.motion()) {
      this.stopVideo();
      return;
    }
    if (this.video.getAttribute('src') !== this.source) this.video.src = this.source;
    this.video.play().catch(() => { /* 自动播放被拒绝时保留静帧 */ });
  }
}
