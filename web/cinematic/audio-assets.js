/**
 * 场景配音的资源映射：交给 Vite 处理 MP3 URL，
 * 保证开发与部署后的路径都正确。新增素材从 Seed Audio 清单接入。
 */
import seed from './seed-runtime.json';

const seedFiles = import.meta.glob('./audio/seed/*.mp3', { eager: true, query: '?url', import: 'default' });
const seedUrl = (file) => seedFiles[`./audio/seed/${file}`];

// 场景 id → 音频资源 URL，以及每页结束时间；全部来自 Seed Audio 清单。
export const SCENE_AUDIO = {};
export const SCENE_CUES = {};
export const CHOICE_AUDIO = {};
export const AMBIENCE_AUDIO = {};
export const MUSIC_AUDIO = {};
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
for (const [mood, file] of Object.entries(seed.music || {})) {
  const url = seedUrl(file);
  if (url) MUSIC_AUDIO[mood] = url;
}
