import { test } from 'node:test';
import assert from 'node:assert/strict';
import { BrowserSaveStore } from '../../web/storage/index.js';
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
