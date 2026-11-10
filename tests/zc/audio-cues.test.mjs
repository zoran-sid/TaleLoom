import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cueFor, entrySfxFor, preloadFor } from '../../web/cinematic/audio-cues.js';

test('同一账桌画面按 Python 场景切换调查与揭露情绪', () => {
  assert.deepEqual(cueFor({ story_id: 'fog_harbor_ledger', scene_id: 'c01_batch' }),
    { music: 'ledger_inquiry', ambience: 'ledger_room' });
  assert.deepEqual(cueFor({ story_id: 'fog_harbor_ledger', scene_id: 'c05_tonight' }),
    { music: 'ledger_revelation', ambience: 'ledger_room' });
});

test('序章与第一章按地点和剧情换声，同一配乐不因房间重复', () => {
  assert.deepEqual(cueFor({ story_id: 'fog_harbor_ledger', scene_id: 'p01_dock' }),
    { music: 'harbor_arrival', ambience: 'harbor' });
  for (const scene of ['p02_lobby', 'p03_dinner', 'p04_office']) {
    assert.deepEqual(cueFor({ story_id: 'fog_harbor_ledger', scene_id: scene }).music, 'inn_night');
  }
  for (const scene of ['a01_found', 'a02_door', 'a03_lamp', 'a04_window']) {
    assert.deepEqual(cueFor({ story_id: 'fog_harbor_ledger', scene_id: scene }).music, 'discovery');
  }
  assert.equal(cueFor({ story_id: 'fog_harbor_ledger', scene_id: 'a03_lamp' }).ambience, 'ledger');
});

test('结局只按引擎结局 ID 选声，其他剧本沿用原播放器', () => {
  assert.equal(cueFor({ story_id: 'fog_harbor_ledger', ending_id: 'truth' }).music, 'dawn');
  assert.equal(cueFor({ story_id: 'fog_harbor_ledger', ending_id: 'wrong' }).music, 'dark');
  assert.equal(cueFor({ story_id: 'deep_space_film', scene_id: 'c01_batch' }), null);
});

test('翻账纸反馈只由引擎首次进入账目场景触发', () => {
  assert.equal(entrySfxFor({ story_id: 'fog_harbor_ledger', scene_id: 'c01_batch' }), 'ledger_paper');
  assert.equal(entrySfxFor({ story_id: 'fog_harbor_ledger', scene_id: 'p01_dock' }), null);
});

test('三条调查路线进入同一账目场景前预取小样', () => {
  assert.deepEqual(preloadFor({ story_id: 'fog_harbor_ledger', scene_id: 'b06_rewrite' }),
    ['ledger_inquiry', 'ledger_room', 'ledger_paper']);
  assert.deepEqual(preloadFor({ story_id: 'deep_space_film', scene_id: 'b06_rewrite' }), []);
});
