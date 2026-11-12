// ZC：影像版的场景镜头。镜头按场景 ID 选用；没有镜头的剧本仍用代码绘制的画面。
import { test, expect } from './cinematic-driver.js';

const ready = (page) => page.waitForFunction(() => window.__cinematic?.ready(), null, { timeout: 90_000 });

test('未结的账：开场场景显示码头镜头的静帧，画布停在黑场', async ({ page }) => {
  const failed = [];
  page.on('response', (response) => { if (response.status() >= 400) failed.push(response.url()); });
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await ready(page);
  const backdrop = page.locator('#backdrop');
  await expect(backdrop).toBeVisible();
  await expect(backdrop).toHaveAttribute('data-clip', 'dock-opening');
  await expect.poll(() => backdrop.locator('img').evaluate((img) => img.complete && img.naturalWidth)).toBeGreaterThan(0);
  // 快速模式和“减少动态效果”只显示静帧，不播放循环视频。
  expect(await backdrop.locator('video').evaluate((video) => video.getAttribute('src'))).toBeNull();
  expect(failed).toEqual([]);
});

test('深空影像版：首个场景使用休眠舱镜头', async ({ page }) => {
  await page.goto('/cinematic.html?fast=1&story=deep_space_film');
  await page.locator('#begin').click();
  await ready(page);
  await expect(page.locator('#backdrop')).toHaveAttribute('data-clip', 'echo-bay-wake');
});

test('没有镜头的剧本（文字版剧本）继续使用代码画面', async ({ page }) => {
  await page.goto('/cinematic.html?fast=1&story=fog_harbor');
  await page.locator('#begin').click();
  await ready(page);
  await expect(page.locator('#backdrop')).toBeHidden();
});

test('正常速度下循环镜头会播放，页面转入后台时暂停', async ({ page }) => {
  await page.goto('/cinematic.html?story=fog_harbor_film');
  await page.locator('#begin').click();
  const video = page.locator('#backdrop video[data-visible]');
  await expect(video).toBeVisible({ timeout: 90_000 });
  await expect(page.locator('#backdrop')).toHaveAttribute('data-clip', 'lobby-counter');
  expect(await video.evaluate((node) => node.muted && node.loop)).toBe(true);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(() => page.locator('#backdrop video').evaluate((node) => node.paused)).toBe(true);
});
