import { test, expect } from '@playwright/test';

// 已知缺陷：影像模式的选项焦点与静息态完全一致（边框/背景/阴影/轮廓全同），
// 键盘用户看不到焦点在哪。已开 issue 给 ZC；修好后把 test.fixme 改成 test。
// 证据：web/cinematic/cinematic.css 的 .choice:focus-visible 用了 outline: none，
// 且边框色与 .choice:hover 相同，而 --line 在深色主题下与 --amber 视觉接近。

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

test.fixme('影像模式：选项焦点必须与静息态可分辨', async ({ page }) => {
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

// fast=1 时转场卡不消失、字幕被跳过：已开 issue 给 ZC。
test.fixme('影像模式：fast=1 时转场卡应退场', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await page.waitForTimeout(8000);
  const state = await page.evaluate(() => ({
    card: document.querySelector('#card').hidden,
    subtitle: document.querySelector('#subtitle').textContent.trim().length,
  }));
  expect(state.card, '转场卡应已退场').toBe(true);
  expect(state.subtitle, '应至少显示过一句字幕').toBeGreaterThan(0);
});
