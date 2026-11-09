import { test, expect } from '@playwright/test';

// ZRS 发现的问题（已由 ZC 修复）：选项的键盘焦点曾与静息态完全一致。
// 现在 .choice:focus-visible 有一圈琥珀色轮廓，与鼠标悬停区分开。

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

test('影像模式：选项焦点必须与静息态可分辨', async ({ page }) => {
  await toFirstChoice(page);
  await page.evaluate(() => document.activeElement?.blur());
  const readStyle = () => page.evaluate(() => {
    const b = document.querySelector('#choices button');
    const s = getComputedStyle(b);
    return { border: s.borderColor, bg: s.backgroundColor,
      outline: `${s.outlineStyle} ${s.outlineWidth}`, shadow: s.boxShadow };
  });
  const rest = await readStyle();
  await page.locator('#choices button').first().focus();
  const focus = await readStyle();
  const distinguishable = focus.border !== rest.border || focus.bg !== rest.bg
    || focus.shadow !== rest.shadow
    || (focus.outline.includes('solid') && !focus.outline.includes('0px'));
  expect(distinguishable,
    `选项焦点与静息态完全相同：${JSON.stringify({ rest, focus })}`).toBe(true);
});

// ZRS 发现的问题（已由 ZC 修复）：fast=1 时转场卡应退场，字幕仍然逐句出现（只是不等待）。
test('影像模式：fast=1 时转场卡应退场', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.addInitScript(() => {
    window.__subs = [];
    document.addEventListener('DOMContentLoaded', () => {
      const box = document.getElementById('subtitle');
      new MutationObserver(() => { if (box.textContent) window.__subs.push(box.textContent); })
        .observe(box, { childList: true, subtree: true, characterData: true });
    });
  });
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await page.waitForFunction(() => window.__cinematic?.ready(), null, { timeout: 90_000 });
  const state = await page.evaluate(() => ({ card: document.querySelector('#card').hidden, shown: window.__subs.length }));
  expect(state.card, '转场卡应已退场').toBe(true);
  expect(state.shown, '应至少显示过一句字幕').toBeGreaterThan(0);
});
