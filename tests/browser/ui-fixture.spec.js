import { test, expect } from '@playwright/test';

// 测试替身页面：不下载 Pyodide，用同一套渲染代码验证动作、参数、错误与结局。
const idle = (page) => expect(page.locator('#app')).toHaveAttribute('aria-busy', 'false');
async function open(page) {
  await page.goto('/?fixture=1');
  await idle(page);
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '开始阅读' }).click();
  await expect(page.locator('#game')).toBeVisible();
}
async function act(page, actionId, values = {}) {
  if (actionId.startsWith('choice:')) {
    await page.locator(`button[data-action="${actionId}"]`).click();
  } else {
    const form = page.locator(`form[data-action="${actionId}"]`);
    for (const [key, value] of Object.entries(values)) await form.locator(`[name="${key}"]`).selectOption(value);
    await form.getByRole('button').click();
  }
  await idle(page);
}

test('测试替身：点击通关，参数动作与结局页', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await open(page);
  await expect(page.locator('#scene-title')).toHaveText('门厅');
  await expect(page.locator('#clues')).toContainText('门边便条');
  await expect(page.locator('#actions form')).toHaveCount(0);
  await act(page, 'choice:take');
  await expect(page.locator('#inventory')).toContainText('钥匙');
  await expect(page.locator('#actions form[data-action="puzzle:use"]')).toHaveCount(1);
  await act(page, 'puzzle:use', { item: 'key' });
  await expect(page.locator('#chapter')).toHaveAttribute('data-ending', 'out');
  await expect(page.locator('#ending')).toBeVisible();
  await expect(page.locator('#choices').locator('button')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('测试替身：参数无效时保持场景并给出提示', async ({ page }) => {
  await open(page);
  await act(page, 'choice:take');
  await page.evaluate(() => {
    const form = document.querySelector('form[data-action="puzzle:use"]');
    const select = form.querySelector('select');
    const option = document.createElement('option');
    option.value = 'ghost';
    option.text = '幽灵';
    select.append(option);
    select.value = 'ghost';
  });
  await page.locator('form[data-action="puzzle:use"] button[type="submit"]').click();
  await idle(page);
  await expect(page.locator('#scene-title')).toHaveText('门厅');
  await expect(page.locator('#status')).toContainText('请选择有效的操作参数');
});

test('测试替身：连续点击同一选项只执行一次', async ({ page }) => {
  await open(page);
  await page.evaluate(() => {
    const node = document.querySelector('button[data-action="choice:take"]');
    node.click();
    node.click();
  });
  await idle(page);
  await expect(page.locator('#turn')).toHaveText('第 1 回合');
  await expect(page.locator('#inventory')).toContainText('钥匙');
  await expect(page.locator('#actions form[data-action="puzzle:use"]')).toHaveCount(1);
});

test('测试替身：保存、继续与损坏存档保留进度', async ({ page }) => {
  page.on('dialog', (dialog) => dialog.accept());
  await open(page);
  await act(page, 'choice:take');
  await page.locator('#save').click();
  await idle(page);
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('taleloom:v1:ui_demo')));
  expect(saved).toEqual({ fixture: 'ui_demo', step: 1 });
  await page.goto('/?fixture=1');
  await idle(page);
  await page.locator('[data-story="ui_demo"]').getByRole('button', { name: '继续阅读' }).click();
  await expect(page.locator('#game')).toBeVisible();
  await expect(page.locator('#inventory')).toContainText('钥匙');
  await page.locator('#import-file').setInputFiles({
    name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{"fixture":"ui_demo","step":9}'),
  });
  await idle(page);
  await expect(page.locator('#status')).toContainText('测试存档无效');
  await expect(page.locator('#inventory')).toContainText('钥匙');
});

test('测试替身：手机宽度无横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  await act(page, 'choice:take');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator('#actions form')).toBeVisible();
});
