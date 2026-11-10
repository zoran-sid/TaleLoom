/**
 * 场景配音的资源映射：交给 Vite 处理 MP3 URL，
 * 保证开发与部署后的路径都正确。新增素材从 Seed Audio 清单接入。
 */
import p01 from './audio/p01_dock.mp3';
import p02 from './audio/p02_lobby.mp3';
import p03 from './audio/p03_dinner.mp3';
import p04 from './audio/p04_office.mp3';
import a01 from './audio/a01_found.mp3';
import a02 from './audio/a02_door.mp3';
import a03 from './audio/a03_lamp.mp3';
import a04 from './audio/a04_window.mp3';
import seed from './seed-runtime.json';
import legacy from './legacy-cues.json';

const seedFiles = import.meta.glob('./audio/seed/*.mp3', { eager: true, query: '?url', import: 'default' });
const seedUrl = (file) => seedFiles[`./audio/seed/${file}`];

// 场景 id → 音频资源 URL。
export const SCENE_AUDIO = {
  p01_dock: p01, p02_lobby: p02, p03_dinner: p03, p04_office: p04,
  a01_found: a01, a02_door: a02, a03_lamp: a03, a04_window: a04,
};

export const SCENE_CUES = { ...legacy.scenes };
export const CHOICE_AUDIO = {};
export const AMBIENCE_AUDIO = {};
for (const [sceneId, asset] of Object.entries(seed.scenes)) {
  const url = seedUrl(asset.file);
  if (!url) continue;
  SCENE_AUDIO[sceneId] = url;
  SCENE_CUES[sceneId] = asset;
}
for (const [key, asset] of Object.entries(seed.choices)) {
  const url = seedUrl(asset.file);
  if (!url) continue;
  const id = asset.file.slice(0, -4);
  SCENE_AUDIO[id] = url;
  CHOICE_AUDIO[key] = { ...asset, id };
}
for (const [place, file] of Object.entries(seed.ambience)) {
  const url = seedUrl(file);
  if (url) AMBIENCE_AUDIO[place] = url;
}
