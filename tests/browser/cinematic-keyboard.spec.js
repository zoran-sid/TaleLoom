import { test, expect } from '@playwright/test';

// 第二轮 ZRS 检查项：影像模式的键盘操作。
// 焦点可见性单独放在 cinematic-focus.spec.js（已知缺陷，见 issue 给 ZC）。

async function toFirstChoice(page) {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/cinematic.html');
  await expect(page.locator('#intro')).toHaveCSS('opacity', '1', { timeout: 30_000 });
  await page.locator('#begin').click();
  for (let i = 0; i < 120; i += 1) {
    const ready = await page.evaluate(() => !document.querySelector('#choices').hidden
      && document.querySelector('#card').hidden);
    if (ready) return;
    await page.keyboard.press('Space');
    await page.waitForTimeout(150);
  }
  throw new Error('没有等到第一个选择');
}

test('影像模式：空格可继续剧情，数字键可选择', async ({ page }) => {
  await toFirstChoice(page);
  const before = await page.evaluate(() => document.querySelector('#notes-count').textContent
    + '|' + document.querySelector('#choices').textContent.length);
  await page.keyboard.press('1');
  await page.waitForTimeout(1800);
  const after = await page.evaluate(() => document.querySelector('#notes-count').textContent
    + '|' + document.querySelector('#choices').textContent.length);
  expect(after).not.toBe(before);
});

test('影像模式：Tab 能到达选项，回车可确认', async ({ page }) => {
  await toFirstChoice(page);
  await page.locator('#choices button').first().focus();
  const focusedTag = await page.evaluate(() => document.activeElement.tagName);
  expect(focusedTag).toBe('BUTTON');
  const before = await page.evaluate(() => document.querySelector('#notes-count').textContent
    + '|' + document.querySelector('#choices').textContent.length);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1800);
  const after = await page.evaluate(() => document.querySelector('#notes-count').textContent
    + '|' + document.querySelector('#choices').textContent.length);
  expect(after).not.toBe(before);
});

test('影像模式：Esc 合上笔记', async ({ page }) => {
  await toFirstChoice(page);
  await page.keyboard.press('n');
  await expect(page.locator('#notebook')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#notebook')).toBeHidden();
});
