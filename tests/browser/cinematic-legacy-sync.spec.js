import { test, expect } from '@playwright/test';

test('旧八场：字幕按录音时间翻页，不再按字数提前', async ({ page }) => {
  test.setTimeout(60_000);
  await page.addInitScript(() => {
    window.__legacyPages = [];
    window.__legacyTime = 0;
    document.addEventListener('taleloom:reading-page', (event) => {
      if (event.detail.sceneId === 'p01_dock') {
        window.__legacyPages.push({ text: event.detail.text.slice(0, 16), time: window.__legacyTime });
      }
    });
    document.addEventListener('taleloom:audio-progress', (event) => {
      if (event.detail.id === 'p01_dock') window.__legacyTime = event.detail.time;
    });
  });
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await expect.poll(() => page.evaluate(() => window.__legacyPages.length), { timeout: 35_000 }).toBeGreaterThan(1);
  const pages = await page.evaluate(() => window.__legacyPages);
  // 第 2 页对应 legacy-cues.json 的 13.18 秒；旧的字数估算约 12.2 秒。
  expect(pages[1].time).toBeGreaterThan(12.6);
});
