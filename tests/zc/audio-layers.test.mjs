import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SampledLayers } from '../../web/cinematic/audio-layers.js';

function fakeAudio() {
  const sources = [];
  const ctx = {
    currentTime: 0,
    createGain() { return { gain: { value: 0, setValueAtTime(value) { this.value = value; }, linearRampToValueAtTime(value) { this.value = value; }, cancelScheduledValues() {} }, connect() { return this; }, disconnect() {} }; },
    createBufferSource() {
      const source = { loop: false, connect() { return this; }, start() { this.started = true; }, stop() { this.stopped = true; }, disconnect() {} };
      sources.push(source);
      return source;
    },
    decodeAudioData: async (buffer) => ({ duration: buffer.byteLength }),
  };
  return { ctx, sources };
}

test('旧场景的异步加载完成后不再播放', async () => {
  const { ctx, sources } = fakeAudio();
  let release;
  const fetcher = () => new Promise((resolve) => { release = resolve; });
  const layers = new SampledLayers(ctx, ctx.createGain(), { old: { url: '/old.wav', layer: 'bgm' } }, fetcher);
  const pending = layers.setBed('bgm', 'old');
  await layers.setBed('bgm', null);
  release({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) });
  assert.equal(await pending, false);
  assert.equal(sources.length, 0);
});

test('缺失素材可降级，重复同一轨道不会叠加播放', async () => {
  const { ctx, sources } = fakeAudio();
  const layers = new SampledLayers(ctx, ctx.createGain(), { cue: { url: '/cue.wav', layer: 'bgm' } },
    async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) }));
  assert.equal(await layers.setBed('bgm', 'missing'), false);
  assert.equal(await layers.setBed('bgm', 'cue'), true);
  assert.equal(await layers.setBed('bgm', 'cue'), true);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].loop, true);
});

test('加载失败不会覆盖现有轨道，下一次可重试', async () => {
  const { ctx, sources } = fakeAudio();
  let calls = 0;
  const layers = new SampledLayers(ctx, ctx.createGain(), { cue: { url: '/cue.wav', layer: 'bgm' } },
    async () => { calls += 1; return { ok: calls > 1, status: 503, arrayBuffer: async () => new ArrayBuffer(8) }; });
  assert.equal(await layers.setBed('bgm', 'cue'), false);
  assert.equal(sources.length, 0);
  assert.equal(await layers.setBed('bgm', 'cue'), true);
  assert.equal(calls, 2);
});

test('新场景素材失败时旧场景录音退出，交给合成声降级', async () => {
  const { ctx, sources } = fakeAudio();
  const layers = new SampledLayers(ctx, ctx.createGain(), {
    old: { url: '/old.wav', layer: 'bgm' }, next: { url: '/next.wav', layer: 'bgm' },
  }, async (url) => ({ ok: url === '/old.wav', status: 404, arrayBuffer: async () => new ArrayBuffer(8) }));
  assert.equal(await layers.setBed('bgm', 'old'), true);
  assert.equal(await layers.setBed('bgm', 'next'), false);
  assert.equal(sources[0].stopped, true);
  assert.equal(layers.active.bgm, null);
});

test('浏览器资源请求同步报错时也返回合成声降级', async () => {
  const { ctx } = fakeAudio();
  const layers = new SampledLayers(ctx, ctx.createGain(), { cue: { url: '/cue.wav', layer: 'bgm' } },
    () => { throw new TypeError('fetch unavailable'); });
  assert.equal(await layers.setBed('bgm', 'cue'), false);
});

test('预取的录音进入场景后复用解码结果', async () => {
  const { ctx } = fakeAudio();
  let calls = 0;
  const layers = new SampledLayers(ctx, ctx.createGain(), { cue: { url: '/cue.wav', layer: 'bgm' } },
    async () => { calls += 1; return { ok: true, arrayBuffer: async () => new ArrayBuffer(8) }; });
  await layers.preload(['cue']);
  assert.equal(await layers.setBed('bgm', 'cue'), true);
  assert.equal(calls, 1);
});

test('玩家提前继续时过期人物配音不能在下一段突然响起', async () => {
  const { ctx, sources } = fakeAudio();
  let release;
  const layers = new SampledLayers(ctx, ctx.createGain(), { line: { url: '/voice.mp3', layer: 'voice' } },
    () => new Promise((resolve) => { release = resolve; }));
  const pending = layers.playVoice('line');
  await Promise.resolve();
  layers.stopVoice();
  release({ ok: true, arrayBuffer: async () => new ArrayBuffer(2) });
  assert.equal(await pending, false);
  assert.equal(sources.length, 0);
});

test('人物配音非循环，点击继续会停止并恢复音乐音量', async () => {
  const { ctx, sources } = fakeAudio();
  const layers = new SampledLayers(ctx, ctx.createGain(), { line: { url: '/voice.mp3', layer: 'voice' } },
    async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(2) }));
  assert.equal(await layers.playVoice('line'), true);
  assert.equal(sources[0].loop, false);
  layers.stopVoice();
  assert.equal(sources[0].stopped, true);
  assert.equal(layers.buses.bgm.gain.value, 1);
});
