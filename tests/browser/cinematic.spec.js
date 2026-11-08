// ZC：影像模式样片的冒烟测试。?fast=1 跳过逐字字幕与转场等待，剧情仍由真实引擎驱动。
import { test, expect } from '@playwright/test';

test('影像模式：大堂 → 账房获得线索 → 回大堂审问顾先生', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  // 记录每一条出现过的字幕（连续相同的只算一次），用来检查回到大堂时不重播描述。
  await page.addInitScript(() => {
    window.__subs = [];
    document.addEventListener('DOMContentLoaded', () => {
      const box = document.getElementById('subtitle');
      new MutationObserver(() => {
        const text = box.textContent;
        if (text && window.__subs.at(-1) !== text) window.__subs.push(text);
      }).observe(box, { childList: true, subtree: true, characterData: true });
    });
  });
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  const choices = page.locator('#choices');
  const pick = (name) => choices.getByRole('button', { name }).click();

  await expect(choices.getByRole('button', { name: /去账房查看现场/ })).toBeVisible({ timeout: 90_000 });
  const lit = await page.locator('#stage').evaluate((canvas) => {
    const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let bright = 0;
    for (let i = 0; i < data.length; i += 4 * 97) if (data[i] + data[i + 1] + data[i + 2] > 90) bright += 1;
    return bright;
  });
  expect(lit).toBeGreaterThan(20);

  await pick(/去账房查看现场/);
  await pick(/翻看桌上的账本/);
  await expect(choices.getByRole('button', { name: /深入调查：被撕去的账页/ })).toBeVisible();

  // 线索笔记随时可查，翻看不推进剧情
  await expect(page.locator('#notes-count')).toHaveText('1');
  await page.getByRole('button', { name: /线索笔记/ }).click();
  await expect(page.locator('#notebook')).toContainText('被撕去的账页');
  await expect(page.locator('#notebook')).toContainText('当前场景 · 账房');
  await page.keyboard.press('Escape');
  await expect(page.locator('#notebook')).toBeHidden();
  await expect(choices.getByRole('button', { name: /回到大堂/ })).toBeVisible();

  await pick(/回到大堂/);
  await expect(choices.getByRole('button', { name: /去账房查看现场/ })).toBeVisible();
  const lobbyLines = await page.evaluate(() => window.__subs.filter((t) => t.includes('一九三一年，雾港')).length);
  expect(lobbyLines).toBe(1);
  await pick(/审问：顾先生 · 昨晚十一点在做什么/);
  await expect(choices.getByRole('button', { name: /顾先生 · 昨晚十一点在做什么/ })).toContainText('已问过');
  expect(errors).toEqual([]);
});

test('影像模式：手机宽度下选项在画面下方，没有横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  const first = page.locator('#choices').getByRole('button', { name: /去账房查看现场/ });
  await expect(first).toBeVisible({ timeout: 90_000 });
  const frame = await page.locator('#frame').boundingBox();
  const box = await first.boundingBox();
  expect(box.y).toBeGreaterThanOrEqual(frame.y + frame.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
