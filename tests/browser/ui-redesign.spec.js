import { test, expect } from '@playwright/test';
import { openSaves } from './ui-driver.js';

const idle = (page) => expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');

// 首页改版：首屏版画、书架题图、影像推荐位的版画剧照，桌面与手机都不横向溢出。
for (const width of [390, 1280]) {
  test(`首页 ${width}px：版画画出，标题不被裁切`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/?fixture=1');
    await idle(page);
    await expect(page.locator('#plate-fog svg')).toHaveCount(1);
    await expect(page.locator('#plate-deep svg')).toHaveCount(1);
    await expect(page.locator('[data-story="ui_demo"] .story-thumb')).toBeVisible();
    await expect(page.locator('[data-cinematic="fog_harbor_ledger"] .plate-still img')).toHaveCount(1);
    await expect(page.locator('.howto .feature')).toHaveCount(4);
    const metrics = await page.evaluate(() => {
      const title = document.querySelector('#library-title').getBoundingClientRect();
      return { right: title.right, overflow: document.documentElement.scrollWidth > innerWidth };
    });
    expect(metrics.right).toBeLessThanOrEqual(width);
    expect(metrics.overflow).toBe(false);
  });
}

test('存档菜单：展开后可操作，按 Esc 收起；未登记的剧本不显示场景配图', async ({ page }) => {
  await page.goto('/?fixture=1');
  await idle(page);
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '开始阅读' }).click();
  await expect(page.locator('#game')).toBeVisible();
  await expect(page.locator('#scene-plate')).toBeHidden();
  await expect(page.locator('#save')).toBeHidden();
  await openSaves(page);
  await expect(page.locator('#save')).toBeVisible();
  await expect(page.locator('#save-slot')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#save')).toBeHidden();
});
