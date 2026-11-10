import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AudioTrack } from '../../web/cinematic/audio-track.js';

function makeCtor() {
  const elements = [];
  const ctor = (src) => {
    const el = {
      src, playCalls: 0, paused: true,
      play: () => { el.playCalls += 1; return Promise.resolve(); },
      pause: () => { el.paused = true; },
    };
    elements.push(el);
    return el;
  };
  return { ctor, elements };
}

const MAP = { p01_dock: '/audio/p01.mp3', p02_lobby: '/audio/p02.mp3' };

test('无 Audio 构造器时 supported=false，play 静默不报错', () => {
  const t = new AudioTrack({ map: MAP });
  assert.equal(t.supported, false);
  t.play('p01_dock');
  t.stop();
});

test('播放有映射的场景：创建元素、设置 src 并调用 play', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  assert.equal(elements.length, 1);
  assert.equal(elements[0].src, '/audio/p01.mp3');
  assert.equal(elements[0].playCalls, 1);
  assert.equal(t.current, 'p01_dock');
});

test('同一场景重复播放不重新创建元素', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  t.play('p01_dock');
  assert.equal(elements.length, 1);
  assert.equal(elements[0].playCalls, 2);
});

test('切换场景：暂停旧元素并创建新元素', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  t.play('p02_lobby');
  assert.equal(elements.length, 2);
  assert.equal(elements[0].paused, true);
  assert.equal(t.current, 'p02_lobby');
});

test('播放无映射的场景会停止当前音频', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  t.play('unknown_scene');
  assert.equal(t.current, null);
  assert.equal(elements[0].paused, true);
});

test('stop 暂停并复位当前场景', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  t.stop();
  assert.equal(t.current, null);
  assert.equal(t.el, null);
  assert.equal(elements[0].paused, true);
});

test('配音关闭后不发声，重新开启才播放', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.setEnabled(false);
  t.play('p01_dock');
  assert.equal(elements.length, 0);
  t.setEnabled(true);
  t.play('p01_dock');
  assert.equal(elements.length, 1);
});

test('主静音时停止且不播放', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  t.setMuted(true);
  assert.equal(t.current, null);
  t.play('p01_dock');
  assert.equal(elements.length, 1); // 静音期间不再创建
});

test('suspend 记下场景并释放，resume 重新播放', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  t.suspend();
  assert.equal(t.current, null);
  assert.equal(t.suspendedScene, 'p01_dock');
  t.resume();
  assert.equal(t.current, 'p01_dock');
  assert.equal(elements.length, 2);
});

test('play 返回被拒绝的 Promise 时不抛错', () => {
  const ctor = () => ({ play: () => Promise.reject(new Error('blocked')), pause: () => {} });
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  assert.doesNotThrow(() => t.play('p01_dock'));
});
