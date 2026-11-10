/**
 * 场景配音的资源映射：显式 import 每个 MP3，交给 Vite 处理资源 URL，
 * 保证开发与部署后的路径都正确。仅《雾港旧案：未结的账》序章与第一幕有配音。
 */
import p01 from './audio/p01_dock.mp3';
import p02 from './audio/p02_lobby.mp3';
import p03 from './audio/p03_dinner.mp3';
import p04 from './audio/p04_office.mp3';
import a01 from './audio/a01_found.mp3';
import a02 from './audio/a02_door.mp3';
import a03 from './audio/a03_lamp.mp3';
import a04 from './audio/a04_window.mp3';

// 场景 id → 音频资源 URL。
export const SCENE_AUDIO = {
  p01_dock: p01, p02_lobby: p02, p03_dinner: p03, p04_office: p04,
  a01_found: a01, a02_door: a02, a03_lamp: a03, a04_window: a04,
};
