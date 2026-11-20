import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AudioTrack } from '../../web/cinematic/audio-track.js';

function makeCtor() {
  const elements = [];
  const ctor = (src) => {
    const el = {
      src, playCalls: 0, paused: true, duration: 100, currentTime: 0, listeners: new Map(),
      play: () => { el.playCalls += 1; el.paused = false; return Promise.resolve(); },
      pause: () => { el.paused = true; },
      addEventListener: (name, fn) => {
        if (!el.listeners.has(name)) el.listeners.set(name, new Set());
        el.listeners.get(name).add(fn);
      },
      removeEventListener: (name, fn) => { el.listeners.get(name)?.delete(fn); },
      emit: (name) => { for (const fn of el.listeners.get(name) || []) fn(); },
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

test('主静音暂停配音，取消静音从原进度继续', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  elements[0].currentTime = 40;
  t.setMuted(true);
  assert.equal(t.current, 'p01_dock');
  assert.equal(elements[0].paused, true);
  t.play('p01_dock');
  assert.equal(elements.length, 1); // 静音期间不再创建
  t.setMuted(false);
  assert.equal(elements[0].paused, false);
  assert.equal(elements[0].currentTime, 40);
});

test('suspend 暂停，resume 从原进度继续', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  elements[0].currentTime = 30;
  t.suspend();
  assert.equal(t.current, 'p01_dock');
  assert.equal(t.suspendedScene, 'p01_dock');
  assert.equal(elements[0].paused, true);
  t.resume();
  assert.equal(t.current, 'p01_dock');
  assert.equal(elements.length, 1);
  assert.equal(elements[0].currentTime, 30);
});

test('字幕监听随播放进度触发一次，手动跳过可同步音频进度', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  let pages = 0;
  const cancel = t.watchFraction(0.5, () => { pages += 1; });
  elements[0].currentTime = 49;
  elements[0].emit('timeupdate');
  assert.equal(pages, 0);
  elements[0].currentTime = 50;
  elements[0].emit('timeupdate');
  elements[0].emit('ended');
  assert.equal(pages, 1);
  cancel();
  t.seekFraction(0.8);
  assert.equal(elements[0].currentTime, 80);
});

test('配音加载前连跳时保留最后一页，换场后清理旧录音的跳转', () => {
  const { ctor, elements } = makeCtor();
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  t.play('p01_dock');
  const dock = elements[0];
  dock.duration = NaN;
  t.seekFraction(0.2);
  t.seekFraction(0.4);
  dock.duration = 100;
  dock.emit('durationchange');
  assert.equal(dock.currentTime, 40);

  dock.duration = NaN;
  t.seekFraction(0.8);
  t.play('p02_lobby');
  const lobby = elements[1];
  dock.duration = 100;
  dock.emit('loadedmetadata');
  lobby.emit('loadedmetadata');
  assert.equal(dock.currentTime, 40);
  assert.equal(lobby.currentTime, 0);
});

test('播放进度事件为后续动画提供场景和时间，停止后不再发出', () => {
  const { ctor, elements } = makeCtor();
  const events = [];
  const t = new AudioTrack({ map: MAP, audioCtor: ctor, onProgress: event => events.push(event) });
  t.play('p01_dock');
  elements[0].currentTime = 3;
  elements[0].emit('timeupdate');
  assert.deepEqual(events, [{ id: 'p01_dock', time: 3, duration: 100 }]);
  t.stop();
  elements[0].emit('timeupdate');
  assert.equal(events.length, 1);
});

test('play 返回被拒绝的 Promise 时不抛错', () => {
  const ctor = () => ({ play: () => Promise.reject(new Error('blocked')), pause: () => {} });
  const t = new AudioTrack({ map: MAP, audioCtor: ctor });
  assert.doesNotThrow(() => t.play('p01_dock'));
});
