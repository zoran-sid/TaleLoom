/** LQ：正式浏览器 SaveStore，多槽与旧单槽兼容；规则校验仍在 Python 会话。 */
const prefix = 'taleloom:v1:';
const valid = (value) => typeof value === 'string' && /^[\w-]{1,60}$/.test(value);

function copy(value) {
  const seen = new Set();
  function check(v) {
    if (v === null || typeof v === 'string' || typeof v === 'boolean' || (typeof v === 'number' && Number.isFinite(v))) return;
    if (typeof v !== 'object' || seen.has(v)) throw new Error('存档必须为有效 JSON 数据');
    seen.add(v);
    if (Array.isArray(v)) v.forEach(check);
    else if (Object.getPrototypeOf(v) === Object.prototype) Object.values(v).forEach(check);
    else throw new Error('存档必须为有效 JSON 数据');
    seen.delete(v);
  }
  check(value);
  if (value === null || Array.isArray(value) || typeof value !== 'object') throw new Error('存档必须为 JSON 对象');
  return JSON.parse(JSON.stringify(value));
}

// 复用同一严格 JSON 边界；新增导出不改变现有存档读写接口。
export { copy as copyJson };

export class BrowserSaveStore {
  constructor(storyId, storage = globalThis.localStorage) {
    if (!valid(storyId)) throw new Error('存档剧本名称无效');
    this.storyId = storyId;
    this.storage = storage;
  }
  key(slot) {
    if (!valid(slot)) throw new Error('存档槽名称无效');
    // quick 沿用原键，升级后已有试玩存档仍可继续。
    return prefix + this.storyId + (slot === 'quick' ? '' : ':' + slot);
  }
  listSlots() {
    try {
      const base = prefix + this.storyId;
      const slots = [];
      for (let i = 0; i < this.storage.length; i++) {
        const key = this.storage.key(i);
        if (key === base) slots.push('quick');
        else if (key.startsWith(base + ':') && valid(key.slice(base.length + 1))) slots.push(key.slice(base.length + 1));
      }
      return slots.sort();
    } catch { throw new Error('本机存储不可用，请导出存档保存进度。'); }
  }
  read(slot = 'quick') {
    const key = this.key(slot);
    try {
      const raw = this.storage.getItem(key);
      return raw === null ? null : copy(JSON.parse(raw));
    } catch { throw new Error('无法读取本机存档。可以使用导入功能恢复 JSON 存档。'); }
  }
  write(slot, payload) {
    const key = this.key(slot);
    // 编码完成后才调用 setItem，容量失败由 Web Storage 的原子操作保留旧值。
    const data = { ...copy(payload), saved_at: new Date().toISOString() };
    try { this.storage.setItem(key, JSON.stringify(data)); }
    catch { throw new Error('本机存储不可用或空间不足，请导出存档保存进度。'); }
  }
  describeSlots() {
    return this.listSlots().map(slot => {
      try {
        const data = this.read(slot);
        return { slot, saved_at: data.saved_at ?? null, scene: data.state?.scene, turn: data.state?.turn };
      } catch { return { slot, error: '存档损坏或无法读取' }; }
    });
  }
}

export function readSave(storyId, slot = 'quick') {
  return new BrowserSaveStore(storyId).read(slot);
}
export function writeSave(storyId, payload, slot = 'quick') {
  new BrowserSaveStore(storyId).write(slot, payload);
}
export function describeSaves(storyId) {
  return new BrowserSaveStore(storyId).describeSlots();
}
