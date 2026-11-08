import { test, expect } from '@playwright/test';

// 版面与可读性检查：字体档位、正文换行、无横向溢出、焦点可见。
test('网页版面：字号档位与无溢出', async ({ page }) => {
  await page.goto('/?fixture=1');
  await expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '开始阅读' }).click();
  await page.locator('button[data-action="choice:take"]').click();
  await expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');

  const metrics = await page.evaluate(() => {
    const px = (node, prop) => parseFloat(getComputedStyle(node)[prop]);
    return {
      prose: px(document.querySelector('#scene-text'), 'fontSize'),
      sceneTitle: px(document.querySelector('#scene-title'), 'fontSize'),
      choice: px(document.querySelector('#choices button'), 'fontSize'),
      muted: px(document.querySelector('.notebook h3'), 'fontSize'),
      overflow: document.documentElement.scrollWidth > innerWidth,
      buttonHeight: document.querySelector('#choices button').getBoundingClientRect().height,
    };
  });
  expect(metrics.prose).toBeGreaterThanOrEqual(18);
  expect(metrics.sceneTitle).toBeGreaterThanOrEqual(26);
  expect(metrics.choice).toBeGreaterThanOrEqual(15);
  expect(metrics.overflow).toBe(false);
  expect(metrics.buttonHeight).toBeGreaterThanOrEqual(44);
});

test('网页焦点：键盘可到达选项并看到轮廓', async ({ page }) => {
  await page.goto('/?fixture=1');
  await expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '开始阅读' }).click();
  await page.locator('#scene-title').focus();
  await page.keyboard.press('Tab');
  const focused = await page.evaluate(() => {
    const node = document.activeElement;
    const style = getComputedStyle(node);
    return { tag: node.tagName, outline: style.outlineStyle + ' ' + style.outlineWidth, text: node.textContent };
  });
  expect(focused.tag).toBe('BUTTON');
  expect(focused.outline).toContain('solid');
  expect(focused.outline).toContain('3px');
});
