// ZC：《未结的账》只通过剧情选择游玩；事实、结局与存档由 Python 会话判定。
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';

const DATA = JSON.parse(execFileSync('python3', ['-B', 'tools/film_vectors.py', 'fog_harbor_ledger'],
  { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));
const VECTORS = Object.fromEntries(DATA.vectors.map((v) => [v.name, v]));
const KEY = 'taleloom:v1:fog_harbor_ledger:checkpoints';

async function ready(page) {
  await page.waitForFunction(() => window.__cinematic?.ready(), null, { timeout: 90_000 });
  await expect(page.locator('#choices')).toBeVisible();
  await expect(page.locator('#desk')).toBeHidden();
}

/** 把若干场景的标准存档写成影像存档点，然后从最后一个继续。 */
async function resumeAt(page, walkthrough, scenes, url = '/cinematic.html?fast=1') {
  const entries = scenes.map(([scene, label], i) => {
    const save = DATA.scenes[walkthrough][scene];
    return { label, scene, turn: save.state.turn, at: 1_000 + i, save };
  });
  await page.goto(url);
  await page.evaluate(([key, value]) => localStorage.setItem(key, value),
    [KEY, JSON.stringify({ checkpoint_version: 1, story_id: 'fog_harbor_ledger', entries })]);
  await page.reload();
  await expect(page.locator('#resume')).toHaveText(`从存档点继续：${entries.at(-1).label}`);
  await page.locator('#resume').click();
  await ready(page);
}

async function drive(page, { action_id: id }) {
  expect(id).toMatch(/^choice:/);
  await page.locator(`#choices button[data-action="${id}"]`).click();
  await ready(page);
}

test('未结的账：只用剧情选择走完信任沟通路线，不打开核验表单', async ({ page }) => {
  test.setTimeout(300_000);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await ready(page);
  for (const action of VECTORS.truth.actions) await drive(page, action);
  await expect(page.locator('#card')).toContainText('雾散');
  await expect(page.locator('#choices').getByRole('button', { name: /重新开始/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test('灯下残页：发现随剧情记入，可以直接去后窗', async ({ page }) => {
  await resumeAt(page, 'truth', [['a03_lamp', '测试 · 灯下残页']]);
  await page.getByRole('button', { name: /线索笔记/ }).click();
  await expect(page.locator('#notebook')).toContainText('584');
  await page.keyboard.press('Escape');
  await drive(page, { action_id: 'choice:window' });
  await expect(page.locator('#choices button[data-action="choice:hyp_gu"]')).toBeVisible();
});

test('强抓袖口仍会拒绝：剧情选择有后果，事实不由答题补齐', async ({ page }) => {
  await resumeAt(page, 'truth', [['d02_weight', '测试 · 镇纸']]);
  await drive(page, { action_id: 'choice:grab' });
  await expect(page.locator('#choices button[data-action="choice:again"]')).toBeVisible();
  await drive(page, { action_id: 'choice:again' });
  await page.getByRole('button', { name: /线索笔记/ }).click();
  await expect(page.locator('#notebook')).toContainText('他拒绝展开复核');
  await expect(page.locator('#notebook')).not.toContainText('袖口与布片');
});

test('存档点：刷新可继续，回退清除后续线索，重新开始清空', async ({ page }) => {
  await resumeAt(page, 'truth', [['a01_found', '一 · 夜深取账'], ['c01_batch', '二 · 旧账']]);
  await page.getByRole('button', { name: /线索笔记/ }).click();
  await expect(page.locator('#notebook')).toContainText('三百八十四的差额');
  const saves = page.locator('.nb-save');
  await expect(saves).toHaveCount(2);
  const back = saves.filter({ hasText: '一 · 夜深取账' }).getByRole('button');
  await back.click();
  await back.click();
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:still"]')).toBeVisible();
  const kept = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)).entries.map((e) => e.label), KEY);
  expect(kept).toEqual(['一 · 夜深取账']);
  await page.getByRole('button', { name: /线索笔记/ }).click();
  await expect(page.locator('#notebook')).not.toContainText('三百八十四的差额');
  await page.keyboard.press('Escape');
  await page.reload();
  await expect(page.locator('#resume')).toHaveText('从存档点继续：一 · 夜深取账');
  await page.locator('#resume').click();
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:still"]')).toBeVisible();
  await page.locator('#restart').click();
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:route"]')).toBeVisible();
  const fresh = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)).entries.map((e) => e.label), KEY);
  expect(fresh).toEqual(['开场']);
});

for (const [walkthrough, ending, choice] of [
  ['truth', '雾散', 'sign_zhou'], ['insufficient', '雾未散', 'sign_zhou_gap'], ['scapegoat', '错置的账', 'sign_gu'],
  ['wrong', '被误读的人', 'sign_ayun'], ['dawn', '交给天亮', 'hold'],
]) {
  test(`结局：${ending}`, async ({ page }) => {
    await resumeAt(page, walkthrough, [['e04_sign', '测试 · 最后签字']]);
    await page.locator(`#choices button[data-action="choice:${choice}"]`).click();
    await expect(page.locator('#card')).toContainText(ending);
    await expect(page.locator('#choices').getByRole('button', { name: /回到存档点「测试 · 最后签字」|重新开始/ }).first()).toBeVisible();
  });
}

for (const viewport of [{ width: 390, height: 844 }, { width: 844, height: 390 }]) {
  test(`手机 ${viewport.width}×${viewport.height}：剧情按钮可达，无横向溢出`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await resumeAt(page, 'truth', [['b06_rewrite', '测试 · 记录']]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await drive(page, { action_id: 'choice:next_zhou' });
    await expect(page.locator('#choices button[data-action="choice:next"]')).toBeVisible();
  });
}

test('键盘与减少动态效果：直接选择对话即可推进', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await resumeAt(page, 'truth', [['b02_kitchen', '测试 · 两句话']]);
  await page.locator('#choices button[data-action="choice:private"]').focus();
  await page.keyboard.press('Enter');
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:duty"]')).toBeVisible();
});

test('声音：静音与音量会记住；转入后台时暂停，回来不叠加；重要声音有文字说明', async ({ page }) => {
  await page.addInitScript(() => {
    window.__caps = [];
    document.addEventListener('DOMContentLoaded', () => {
      const node = document.getElementById('sound-caption');
      new MutationObserver(() => { if (node.textContent) window.__caps.push(node.textContent); })
        .observe(node, { childList: true, characterData: true, subtree: true });
    });
  });
  await resumeAt(page, 'truth', [['p02_lobby', '测试 · 大堂']]);
  await page.locator('#mute').click();
  await expect(page.locator('#mute')).toHaveAttribute('aria-pressed', 'true');
  await page.locator('#volume').fill('40');
  const sound = () => page.evaluate(() => {
    const s = window.__cinematic.sound;
    return { timers: s.timers.length, state: s.ctx?.state, muted: s.muted, volume: s.volume };
  });
  const before = await sound();
  expect(before.muted).toBe(true);
  expect(before.volume).toBeCloseTo(0.4);
  expect(before.timers, '大堂有座钟的嘀嗒声').toBeGreaterThan(0);
  const hide = (hidden) => page.evaluate((value) => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => value });
    document.dispatchEvent(new Event('visibilitychange'));
  }, hidden);
  await hide(true);
  await expect.poll(async () => (await sound()).timers).toBe(0);
  await expect.poll(async () => (await sound()).state).toBe('suspended');
  await hide(false);
  await expect.poll(async () => (await sound()).state).toBe('running');
  expect((await sound()).timers, '回来后不叠加').toBe(before.timers);
  await hide(false);
  expect((await sound()).timers).toBe(before.timers);
  expect(await page.evaluate(() => window.__caps.some((c) => c.includes('环境声')))).toBe(true);
  await page.reload();
  await expect(page.locator('#mute')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#volume')).toHaveValue('40');
});

test('生产构建：保留代码音画，不需要外部素材服务', async ({ page }) => {
  const failed = [];
  page.on('response', (response) => { if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`); });
  await page.route('**/*', (route) => (new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort()));
  await resumeAt(page, 'truth', [['a03_lamp', '测试 · 灯下残页']]);
  await expect(page.locator('#choices button[data-action="choice:window"]')).toBeVisible();
  expect(failed).toEqual([]);
  const scripts = await page.evaluate(() => [...document.scripts].map((s) => s.src).filter(Boolean));
  expect(scripts.every((src) => new URL(src).hostname === '127.0.0.1')).toBe(true);
});

test('深空影像版与旧样片仍按各自的剧本播放', async ({ page }) => {
  await page.goto('/cinematic.html?fast=1&story=deep_space_film');
  await expect(page.locator('#intro h1')).toHaveText('深空回声');
  await page.locator('#begin').click();
  await ready(page);
  await expect(page.locator('#meters .meter').first()).toContainText('氧气');
  await expect(page.locator('#chances')).toBeVisible();
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  await ready(page);
  await expect(page.locator('#choices').getByRole('button', { name: /推开账房的门/ })).toBeVisible();
});
