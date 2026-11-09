import { test } from 'node:test';
import assert from 'node:assert/strict';
import { BrowserSaveStore } from '../../web/storage/index.js';
import { CinematicSaveStore } from '../../web/storage/cinematic.js';
function memory() {
  const data = new Map();
  return { get length() { return data.size; }, key(i) { return [...data.keys()][i]; },
    getItem(k) { return data.get(k) ?? null; }, setItem(k,v) { data.set(k,v); } };
}
test('多槽独立，读取不泄漏引用，旧键兼容', () => {
  const storage = memory(), store = new BrowserSaveStore('story', storage);
  storage.setItem('taleloom:v1:story', JSON.stringify({ state: { turn: 1 } }));
  store.write('2', { state: { turn: 2, scene: 'a' } });
  store.write('auto', { state: { turn: 3 } });
  assert.deepEqual(store.listSlots(), ['2', 'auto', 'quick']);
  const data = store.read('2'); data.state.turn = 10;
  assert.equal(store.read('2').state.turn, 2);
  assert.equal(store.read('quick').state.turn, 1);
  assert.equal(store.describeSlots()[0].scene, 'a');
  assert.ok(!Number.isNaN(Date.parse(store.describeSlots()[0].saved_at)));
});
test('坏输入及容量失败保留旧档', () => {
  const storage = memory(), store = new BrowserSaveStore('story', storage);
  store.write('2', { state: { turn: 2 } });
  for (const payload of [null, [], { state: NaN }, { value: undefined }]) assert.throws(() => store.write('2', payload));
  storage.setItem = () => { throw new Error('quota'); };
  assert.throws(() => store.write('2', { state: { turn: 3 } }), /导出/);
  assert.equal(store.read('2').state.turn, 2);
  assert.throws(() => store.read('../escape'), /无效/);
});

function checkpoint(label = '开场', turn = 0) {
  return { label, scene: '休眠舱', turn, at: turn + 1,
    save: { save_version: 1, story_id: 'film', fingerprint: 'fixture',
      state: { story_id: 'film', scene: 'bay_start', turn, ending: null } } };
}

test('影像存档点升级旧键，刷新后可读并跨端导出', () => {
  const storage = memory();
  storage.setItem('taleloom:cinematic:film:autosaves', JSON.stringify([checkpoint()]));
  const store = new CinematicSaveStore('film', storage);
  assert.deepEqual(store.readEntries(), [checkpoint()]);
  store.writeEntries([checkpoint(), checkpoint('气闸', 2)]);
  const fresh = new CinematicSaveStore('film', storage);
  const bundle = fresh.exportBundle();
  assert.equal(bundle.checkpoint_version, 1);
  assert.equal(bundle.entries.length, 2);
  const other = new CinematicSaveStore('film', memory());
  other.importBundle(bundle);
  bundle.entries[0].label = '外部修改';
  assert.equal(other.readEntries()[0].label, '开场');
  fresh.writeEntries(fresh.readEntries().slice(0, 1));
  assert.equal(fresh.readEntries().length, 1);
});

test('坏容器、跨剧本、重复名称和容量失败不破坏存档点', () => {
  const storage = memory(), store = new CinematicSaveStore('film', storage);
  store.writeEntries([checkpoint()]);
  const before = store.exportBundle();
  for (const bundle of [{ ...before, story_id: 'other' }, { ...before, checkpoint_version: true }, { ...before, entries: null }]) {
    assert.throws(() => store.importBundle(bundle));
  }
  assert.throws(() => store.writeEntries([checkpoint(), checkpoint()]));
  const foreign = checkpoint(); foreign.save.state.story_id = 'other';
  assert.throws(() => store.writeEntries([foreign]));
  storage.setItem = () => { throw new Error('quota'); };
  assert.throws(() => store.writeEntries([]), /导出/);
  assert.deepEqual(store.exportBundle(), before);
});

test('升级写入失败仍能读取旧影像存档，并明确报告只读状态', () => {
  const storage = memory();
  storage.setItem('taleloom:cinematic:film:autosaves', JSON.stringify([checkpoint()]));
  storage.setItem = () => { throw new Error('quota'); };
  const store = new CinematicSaveStore('film', storage);
  assert.deepEqual(store.readEntries(), [checkpoint()]);
  assert.match(store.migrationWarning, /导出/);
});
