import { test, expect } from '@playwright/test';

// 第二轮：书架要有“影像模式”入口，链到 /cinematic，卡片标注“互动影像”。
test('书架显示影像模式入口并指向 /cinematic', async ({ page }) => {
  await page.goto('/?fixture=1');
  await expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
  const entry = page.locator('[data-cinematic="fog_harbor_ledger"]');
  await expect(entry).toBeVisible();
  await expect(entry).toContainText('互动影像');
  const link = entry.getByRole('link', { name: /影像模式/ });
  await expect(link).toHaveAttribute('href', '/cinematic');
});

test('书架也有《深空回声 · 影像版》的入口', async ({ page }) => {
  await page.goto('/?fixture=1');
  await expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
  const entry = page.locator('[data-cinematic="deep_space_film"]');
  await expect(entry).toContainText('深空回声 · 影像版');
  await expect(entry.getByRole('link', { name: /影像模式/ })).toHaveAttribute('href', '/cinematic?story=deep_space_film');
});

test('页眉也有影像模式入口', async ({ page }) => {
  await page.goto('/?fixture=1');
  await expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
  const header = page.locator('.masthead').getByRole('link', { name: /影像模式/ });
  await expect(header).toHaveAttribute('href', '/cinematic');
});

for (const width of [360, 390, 430]) {
  test(`手机 ${width}px 页眉不折行`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('/?fixture=1');
    await expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
    const metrics = await page.evaluate(() => {
      const edition = document.querySelector('.edition');
      const lineHeight = parseFloat(getComputedStyle(edition).lineHeight);
      const box = edition.getBoundingClientRect();
      return {
        lines: +(box.height / lineHeight).toFixed(2),
        overflowX: document.documentElement.scrollWidth > innerWidth,
        gap: Math.round(edition.getBoundingClientRect().left
          - document.querySelector('.wordmark').getBoundingClientRect().right),
      };
    });
    expect(metrics.lines).toBeLessThanOrEqual(1.2);
    expect(metrics.overflowX).toBe(false);
    expect(metrics.gap).toBeGreaterThan(8);
  });
}
