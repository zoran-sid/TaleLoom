import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import process from 'node:process';
import { openSaves } from './ui-driver.js';

const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const vectors = JSON.parse(execFileSync(PYTHON, ['-B', 'tools/web_vectors.py'], { encoding: 'utf8' }));
const idle = (page) => expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false', { timeout: 90_000 });
async function start(page, storyId, resume = false) {
  await page.goto('/');
  await idle(page);
  await page.locator(`[data-story="${storyId}"]`).getByRole('button', { name: resume ? '继续阅读' : '开始阅读' }).click();
  await expect(page.locator('#game')).toBeVisible({ timeout: 90_000 });
  await idle(page);
}
async function act(page, action) {
  if (action.action_id.startsWith('choice:')) {
    await page.locator(`button[data-action="${action.action_id}"]`).click();
  } else {
    const form = page.locator(`form[data-action="${action.action_id}"]`);
    for (const [key, value] of Object.entries(action.values)) await form.locator(`[name="${key}"]`).selectOption(value);
    await form.getByRole('button').click();
  }
  await idle(page);
}

for (const vector of vectors) {
  test(`Pyodide 与 CPython 状态一致：${vector.story_id}/${vector.name}`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('dialog', (dialog) => dialog.accept());
    // 禁止外部 CDN：运行环境必须随网站自托管。
    await page.route('**/*', (route) => {
      if (new URL(route.request().url()).hostname !== '127.0.0.1') return route.abort();
      return route.continue();
    });
    await start(page, vector.story_id);
    // 新游戏随机播种；用固定起始存档将浏览器与原生回放置于同一随机状态。
    await page.locator('#import-file').setInputFiles({ name: 'seed.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(vector.initial_save)) });
    await idle(page);
    for (const action of vector.actions) await act(page, action);
    await expect(page.locator('#chapter')).toHaveAttribute('data-ending', vector.ending);
    await expect(page.locator('#ending')).toBeVisible();
    await expect(page.locator('#choices button')).toHaveCount(0);
    await openSaves(page);
    await page.locator('#save').click();
    await idle(page);
    const saved = await page.evaluate((id) => JSON.parse(localStorage.getItem(`taleloom:v1:${id}`)), vector.story_id);
    const { saved_at, ...payload } = saved;
    expect(Number.isNaN(Date.parse(saved_at))).toBe(false);
    expect(payload).toEqual(vector.save);
    expect(errors).toEqual([]);
  });
}

test('保存后刷新可继续，损坏和跨剧本存档保留当前进度', async ({ page }) => {
  page.on('dialog', (dialog) => dialog.accept());
  await start(page, 'fog_harbor');
  await act(page, { action_id: 'choice:office', values: {} });
  await act(page, { action_id: 'choice:ledger', values: {} });
  await openSaves(page);
  await page.locator('#save').click();
  await idle(page);
  await start(page, 'fog_harbor', true);
  await expect(page.locator('#scene-title')).toHaveText('账房');
  await expect(page.locator('#clues')).toContainText('被撕去的账页');
  const before = await page.locator('#turn').textContent();
  for (const payload of [null, { ...vectors[0].save }, { save_version: 1, story_id: 'fog_harbor', state: { scene: [] } }]) {
    await page.locator('#import-file').setInputFiles({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(payload)) });
    await idle(page);
    await expect(page.locator('#status')).toContainText('原进度已保留');
    await expect(page.locator('#turn')).toHaveText(before);
  }
  const downloadPromise = page.waitForEvent('download');
  await openSaves(page);
  await page.locator('#export').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('taleloom-fog_harbor.json');
});

test('手机宽度可完整操作，无横向溢出；笔记阅读不推进回合', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page, 'deep_space');
  const turn = await page.locator('#turn').textContent();
  await page.locator('#inventory').scrollIntoViewIfNeeded();
  await expect(page.locator('#turn')).toHaveText(turn);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/mobile-game.png', fullPage: true });
  await act(page, { action_id: 'choice:locker', values: {} });
  await expect(page.locator('#inventory')).toContainText('绝缘胶带');
});

test('运行时下载失败可重试', async ({ page }) => {
  await page.route('**/runtime.json', (route) => route.abort());
  await page.goto('/');
  await idle(page);
  await page.locator('[data-story="fog_harbor"]').getByRole('button', { name: '开始阅读' }).click();
  await idle(page);
  await expect(page.locator('#retry')).toBeVisible();
  await page.unroute('**/runtime.json');
  await page.locator('#retry').click();
  await expect(page.locator('#game')).toBeVisible({ timeout: 90_000 });
  await idle(page);
});

test('浏览器存储失败提供导出入口', async ({ page }) => {
  await page.addInitScript(() => { Storage.prototype.setItem = () => { throw new Error('quota'); }; });
  await start(page, 'fog_harbor');
  await openSaves(page);
  await page.locator('#save').click();
  await idle(page);
  await expect(page.locator('#status')).toContainText('请导出存档');
  await expect(page.locator('#export')).toBeEnabled();
});

test('成功导入有明确提示，未保存返回会要求确认', async ({ page }) => {
  const dialogs = [];
  page.on('dialog', (dialog) => { dialogs.push(dialog.message()); return dialog.accept(); });
  await start(page, 'fog_harbor');
  const payload = vectors.find((v) => v.story_id === 'fog_harbor').save;
  await page.locator('#import-file').setInputFiles({ name: 'valid.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(payload)) });
  await idle(page);
  await expect(page.locator('#status')).toContainText('存档已导入');
  dialogs.length = 0;
  await page.locator('#home').click();
  expect(dialogs).toHaveLength(1);
  expect(dialogs[0]).toContain('未保存');
  await expect(page.locator('#library')).toBeVisible();
});
