import { test, expect } from '@playwright/test';

const idle = (page) => expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');

// 真实剧本里「指认」是最宽的表单（嫌疑人 + 动机 + 手段 + 证据）。
// 测试替身用同样的四参数动作，验证桌面与手机宽度下都不会把递交按钮挤出屏幕。
for (const width of [390, 768, 1020, 1440]) {
  test(`四参数动作在 ${width}px 下完整可操作`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/?fixture=1');
    await idle(page);
    await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '开始阅读' }).click();
    await page.locator('button[data-action="choice:take"]').click();
    await idle(page);

    const form = page.locator('form[data-action="mystery:accuse"]');
    await expect(form).toBeVisible();
    await expect(form.locator('select')).toHaveCount(4);
    const submit = form.getByRole('button', { name: '作出指认' });
    await expect(submit).toBeVisible();

    const box = await submit.boundingBox();
    expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
    expect(box.height).toBeGreaterThanOrEqual(44);
    const noOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    expect(noOverflow).toBe(true);

    await form.locator('[name="suspect"]').selectOption('zhou');
    await form.locator('[name="motive"]').selectOption('embezzle');
    await form.locator('[name="means"]').selectOption('weight');
    await form.locator('[name="evidence"]').selectOption('clue0');
    page.once('dialog', (dialog) => dialog.accept());
    await submit.click();
    await idle(page);
    await expect(page.locator('#chapter')).toHaveAttribute('data-ending', 'out');
  });
}
