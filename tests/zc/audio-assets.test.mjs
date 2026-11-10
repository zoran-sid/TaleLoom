import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { AUDIO_ASSETS } from '../../web/cinematic/audio-assets.js';
import { ambienceLabel, cueFor, musicLabel } from '../../web/cinematic/audio-cues.js';

// 序章与第一章：p01–p04、a01–a04。
const SECTION = ['p01_dock', 'p02_lobby', 'p03_dinner', 'p04_office',
  'a01_found', 'a02_door', 'a03_lamp', 'a04_window'];
const RECORDED = ['harbor_arrival', 'inn_night', 'discovery',
  'harbor', 'lobby', 'dinner', 'office', 'ledger'];

test('序章与第一章的每条配乐、环境声都已登记为对应层', () => {
  for (const scene of SECTION) {
    const cue = cueFor({ story_id: 'fog_harbor_ledger', scene_id: scene });
    assert.ok(cue, scene);
    assert.equal(AUDIO_ASSETS[cue.music]?.layer, 'bgm', `${scene} 配乐未登记`);
    assert.equal(AUDIO_ASSETS[cue.ambience]?.layer, 'ambience', `${scene} 环境声未登记`);
    assert.ok(musicLabel(cue.music), `${scene} 配乐缺少字幕名称`);
    assert.ok(ambienceLabel(cue.ambience), `${scene} 环境声缺少字幕名称`);
  }
});

test('录音文件可从本站加载且不是空文件', () => {
  for (const id of RECORDED) {
    const asset = AUDIO_ASSETS[id];
    assert.ok(asset.url.startsWith('file:'), `${id} 应使用 import.meta.url 打包`);
    const path = fileURLToPath(asset.url);
    assert.match(path, /\/web\/cinematic\/audio\/[a-z_]+\.mp3$/);
    assert.ok(statSync(path).size > 20_000, `${id} 文件过小或尚未生成`);
  }
});

test('manifest 的请求记录与提交的 MP3 一致', () => {
  const manifest = JSON.parse(readFileSync(new URL('../../web/cinematic/audio/manifest.json', import.meta.url)));
  const records = new Map(manifest.assets.map((record) => [record.id, record]));
  for (const id of RECORDED) {
    const record = records.get(id);
    assert.ok(record, `${id} 缺少生成记录`);
    assert.ok(record.request_id, `${id} 缺少 fal 请求 ID`);
    assert.equal(typeof record.lufs, 'number', `${id} 缺少响度记录`);
    const path = fileURLToPath(AUDIO_ASSETS[id].url);
    const digest = createHash('sha256').update(readFileSync(path)).digest('hex');
    assert.equal(record.sha256, digest, `${id} 的 MP3 与生成记录不一致`);
  }
});
