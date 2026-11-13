import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AmbientTrack } from '../../web/cinematic/ambient-track.js';

function makeTrack() {
  const elements = [];
  const audioCtor = (src) => {
    const el = new EventTarget();
    Object.assign(el, { src, volume: 0, loop: false, paused: true,
      play() { this.paused = false; return Promise.resolve(); },
      pause() { this.paused = true; } });
    elements.push(el);
    return el;
  };
  return { track: new AmbientTrack({ map: { office: '/office.mp3', harbor: '/harbor.mp3' }, audioCtor }), elements };
}

test('录制环境声循环播放，缺失资源回到合成环境声', async () => {
  const { track, elements } = makeTrack();
  assert.equal(track.set('office'), true);
  assert.equal(elements[0].loop, true);
  assert.equal(elements[0].paused, false);
  assert.equal(track.set('unknown'), false);
  await new Promise(resolve => setTimeout(resolve, 650));
  assert.equal(elements[0].paused, true);
  track.stop();
});

test('静音、音量和配音压低环境声共享同一录音', () => {
  const { track, elements } = makeTrack();
  track.set('office');
  track.setVolume(0.5);
  assert.equal(elements[0].volume, 0.26);
  track.setDucked(true);
  assert.equal(elements[0].volume, 0.12);
  track.setMuted(true);
  assert.equal(elements[0].volume, 0);
  track.setMuted(false);
  assert.equal(elements[0].volume, 0.12);
  track.stop();
});

test('录音加载失败时通知调用方恢复合成环境声', () => {
  const { track, elements } = makeTrack();
  let fallback = null;
  track.onError = (name) => { fallback = name; };
  track.set('office');
  elements[0].dispatchEvent(new Event('error'));
  assert.equal(fallback, 'office');
  assert.equal(track.el, null);
});
