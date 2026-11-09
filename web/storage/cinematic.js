/** LQ：影像存档点持久化。入口只需改用 readEntries/writeEntries；不负责剧情回退。 */
import { BrowserSaveStore, copyJson } from './index.js';

export function checkpointBundle(storyId, entries) {
  if (typeof storyId !== 'string' || !/^[\w-]{1,60}$/.test(storyId) || !Array.isArray(entries) || entries.length > 64) {
    throw new Error('存档点剧本或列表无效');
  }
  const labels = new Set();
  for (const entry of entries) {
    const save = entry?.save, state = save?.state;
    if (!entry || typeof entry.label !== 'string' || !entry.label.trim() || entry.label.length > 120
        || labels.has(entry.label) || typeof entry.scene !== 'string'
        || !Number.isSafeInteger(entry.turn) || entry.turn < 0 || !Number.isSafeInteger(entry.at) || entry.at < 0
        || save?.save_version !== 1 || save?.story_id !== storyId || state?.story_id !== storyId
        || typeof state?.scene !== 'string' || state?.turn !== entry.turn || state?.ending != null) {
      throw new Error('存档点名称、身份、回合或标准存档无效');
    }
    labels.add(entry.label);
  }
  return copyJson({ checkpoint_version: 1, story_id: storyId, entries });
}

export class CinematicSaveStore {
  constructor(storyId, storage) {
    checkpointBundle(storyId, []);
    this.storyId = storyId;
    this.storage = storage;
    this.migrationWarning = '';
  }
  backend() {
    // 延迟访问 localStorage，让隐私模式下的预期错误能由调用者捕获。
    return new BrowserSaveStore(this.storyId, this.storage ?? globalThis.localStorage);
  }
  readEntries() {
    const backend = this.backend();
    const bundle = backend.read('checkpoints');
    if (bundle !== null) return this.validateEnvelope(bundle).entries;
    const old = (this.storage ?? globalThis.localStorage).getItem(`taleloom:cinematic:${this.storyId}:autosaves`);
    if (old === null) return [];
    let data;
    try { data = checkpointBundle(this.storyId, JSON.parse(old)); }
    catch { throw new Error('旧影像存档点损坏，原数据已保留。可导入 JSON 恢复。'); }
    try { backend.write('checkpoints', data); }
    catch (error) { this.migrationWarning = error.message; }
    // 升级失败也不丢掉仍可读取的旧节点；旧键保留作备份。
    return data.entries;
  }
  writeEntries(entries) {
    this.backend().write('checkpoints', checkpointBundle(this.storyId, entries));
  }
  exportBundle() {
    return checkpointBundle(this.storyId, this.readEntries());
  }
  importBundle(payload) {
    this.backend().write('checkpoints', this.validateEnvelope(payload));
  }
  validateEnvelope(payload) {
    if (!payload || payload.checkpoint_version !== 1 || payload.story_id !== this.storyId) {
      throw new Error('存档点容器版本或剧本不匹配');
    }
    return checkpointBundle(this.storyId, payload.entries);
  }
}
