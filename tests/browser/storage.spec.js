import { test, expect } from '@playwright/test';
const idle = page => expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
async function open(page) {
  await page.goto('/?fixture=1'); await idle(page);
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '开始阅读' }).click();
  await idle(page);
}
test('多槽和自动存档在刷新后保留，可选择不同进度', async ({ page }) => {
  page.on('dialog', d => d.accept());
  await open(page);
  await page.locator('#save-slot').selectOption('1');
  await page.locator('#save').click(); await idle(page);
  await page.locator('[data-action="choice:take"]').click(); await idle(page);
  await page.locator('#save-slot').selectOption('2');
  await page.locator('#save').click(); await idle(page);
  await page.locator('#save-list-button').click(); await idle(page);
  await expect(page.locator('#save-list')).toContainText('auto');
  await expect(page.locator('#save-list')).toContainText('回合');
  await page.reload(); await idle(page);
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '继续阅读' }).click(); await idle(page);
  await expect(page.locator('#turn')).toHaveText('第 1 回合');
  await page.locator('#save-slot').selectOption('1');
  await page.locator('#load').click(); await idle(page);
  await expect(page.locator('#turn')).toHaveText('第 0 回合');
  await page.locator('#save-slot').selectOption('2');
  await page.locator('#load').click(); await idle(page);
  await expect(page.locator('#turn')).toHaveText('第 1 回合');
});
test('升级前快速存档仍能在正式存储界面继续', async ({ page }) => {
  await page.goto('/?fixture=1'); await idle(page);
  await page.evaluate(() => localStorage.setItem('taleloom:v1:ui_demo', JSON.stringify({ fixture: 'ui_demo', step: 1 })));
  await page.reload(); await idle(page);
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '继续阅读' }).click(); await idle(page);
  await expect(page.locator('#inventory')).toContainText('钥匙');
});
