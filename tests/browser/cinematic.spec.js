// ZC：影像模式的冒烟测试。?fast=1 跳过逐字字幕与转场等待，剧情仍由真实引擎驱动。
// 这些用例走旧样片 fog_harbor_film（?story= 指定）；《未结的账》的用例在 cinematic-ledger.spec.js。
import { test, expect } from '@playwright/test';

test('影像版：每个选择都进入下一段，线索进笔记，一路走到结局', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  const choices = page.locator('#choices');
  const pick = (name) => choices.getByRole('button', { name }).click();
  const seen = [];
  const record = async () => seen.push(...await choices.locator('button.choice .label').allTextContents());

  await expect(choices.getByRole('button', { name: /推开账房的门/ })).toBeVisible({ timeout: 90_000 });
  await record();
  await pick(/推开账房的门/);
  await expect(choices.getByRole('button', { name: /翻开桌上的账本/ })).toBeVisible();
  await expect(page.locator('#notes-count')).toHaveText('2');
  await record();
  await pick(/翻开桌上的账本/);
  await expect(page.locator('#notes-count')).toHaveText('4');
  await page.getByRole('button', { name: /线索笔记/ }).click();
  await expect(page.locator('#notebook')).toContainText('对不上的数目');
  await page.keyboard.press('Escape');
  await record();
  await pick(/上楼搜他的客房/);
  await record();
  await pick(/当面质问顾先生/);
  await record();
  await pick(/把他看住，等天亮交给警署/);
  await expect(page.locator('#card')).toContainText('交给天亮');
  await expect(choices.getByRole('button', { name: /重新开始/ })).toBeVisible();
  expect(seen.filter((label) => label.startsWith('回到'))).toEqual([]);
  expect(errors).toEqual([]);
});

test('影像版：冒险选择中途失败，可以退回上一个选择，机会会减少', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  const choices = page.locator('#choices');
  const pick = (name) => choices.getByRole('button', { name }).click();
  await pick(/推开账房的门/);
  await pick(/查看半开的窗户/);
  await pick(/绕到后院/);
  await expect(page.locator('#notes-count')).toHaveText('4');
  await pick(/趁着夜色，沿石阶下到码头/);
  await expect(page.locator('#card')).toContainText('失足');
  await pick(/回到上一个选择（还剩 3 次机会）/);
  await expect(choices.getByRole('button', { name: /跟着皮鞋印/ })).toBeVisible();
  await expect(page.locator('#chances')).toHaveText('机会 ●●○');
  await expect(page.locator('#notes-count')).toHaveText('4');
  // 再失败两次，机会用完后只能从头再来
  for (const left of [2, 1]) {
    await pick(/趁着夜色，沿石阶下到码头/);
    await pick(new RegExp(`回到上一个选择（还剩 ${left} 次机会）`));
  }
  await pick(/趁着夜色，沿石阶下到码头/);
  await expect(page.locator('#card')).toContainText('机会已经用完');
  await expect(choices.getByRole('button', { name: /回到上一个选择/ })).toHaveCount(0);
  await pick(/从头再来/);
  await expect(choices.getByRole('button', { name: /推开账房的门/ })).toBeVisible();
  await expect(page.locator('#chances')).toHaveText('机会 ●●●');
  expect(errors).toEqual([]);
});

test('影像版：没有证据就逼问，嫌疑人起戒心并记在笔记里', async ({ page }) => {
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  const choices = page.locator('#choices');
  await choices.getByRole('button', { name: /直接指着顾先生/ }).click();
  await expect(choices.getByRole('button', { name: /去账房看现场/ })).toBeVisible();
  await page.getByRole('button', { name: /线索笔记/ }).click();
  const meter = page.locator('.nb-meter', { hasText: '顾先生的戒心' });
  await expect(meter).toHaveClass(/raised/);
  await expect(meter).toContainText('●');
  await expect(page.locator('.nb-meter', { hasText: '周文的戒心' })).toContainText('○');
});

test('影像版：关键节点自动存档，可以从笔记回到存档点，刷新后可以继续', async ({ page }) => {
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  const choices = page.locator('#choices');
  const pick = (name) => choices.getByRole('button', { name }).click();
  await pick(/推开账房的门/);
  await pick(/翻开桌上的账本/);
  await expect(page.locator('#notes-count')).toHaveText('4');
  await page.getByRole('button', { name: /线索笔记/ }).click();
  const saves = page.locator('.nb-save');
  await expect(saves).toHaveCount(2);
  await expect(saves.first()).toContainText('第一幕 · 账房');
  const back = page.locator('.nb-save', { hasText: '第一幕 · 账房' }).getByRole('button');
  await back.click();
  await expect(back).toHaveText('确定回到这里？');
  await back.click();
  await expect(choices.getByRole('button', { name: /翻开桌上的账本/ })).toBeVisible();
  await expect(page.locator('#notes-count')).toHaveText('2');

  await page.reload();
  await expect(page.locator('#resume')).toHaveText('从存档点继续：第一幕 · 账房');
  await page.locator('#resume').click();
  await expect(choices.getByRole('button', { name: /翻开桌上的账本/ })).toBeVisible({ timeout: 90_000 });
  await expect(page.locator('#notes-count')).toHaveText('2');
});

test('影像版：较差的结局可以回到最近的存档点重新推理', async ({ page }) => {
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  const choices = page.locator('#choices');
  const pick = (name) => choices.getByRole('button', { name }).click();
  for (const step of [/推开账房的门/, /翻开桌上的账本/, /拿着账本去后厨找账房先生/, /转身去问阿芸/,
    /不再逼她，回大堂把线索理一理/, /召集所有人到大堂对质/, /不作指认，等天亮警署的人来/]) {
    await pick(step);
  }
  await expect(page.locator('#card')).toContainText('交给天亮');
  await pick(/回到存档点「对质之前」/);
  await expect(choices.getByRole('button', { name: /不作指认/ })).toBeVisible();
  await expect(choices.getByRole('button', { name: /作出指认/ })).toBeVisible();
});

test('探索版（?story=fog_harbor）：大堂 → 账房获得线索 → 回大堂审问顾先生', async ({ page }) => {
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
  await page.goto('/cinematic.html?fast=1&story=fog_harbor');
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
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  const first = page.locator('#choices').getByRole('button', { name: /推开账房的门/ });
  await expect(first).toBeVisible({ timeout: 90_000 });
  const frame = await page.locator('#frame').boundingBox();
  const box = await first.boundingBox();
  expect(box.y).toBeGreaterThanOrEqual(frame.y + frame.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('影像模式：横屏手机画面占满可用高度，选项在画面内且不溢出', async ({ page }) => {
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  const first = page.locator('#choices').getByRole('button', { name: /推开账房的门/ });
  await expect(first).toBeVisible({ timeout: 90_000 });
  const frame = await page.locator('#frame').boundingBox();
  expect(frame.height).toBeGreaterThan(390 * 0.8);
  const box = await first.boundingBox();
  expect(box.y + box.height).toBeLessThanOrEqual(frame.y + frame.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('影像模式（?story=deep_space）：飞船主题、画面内的氧气与电量随回合下降', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/cinematic.html?fast=1&story=deep_space');
  await expect(page.locator('#intro h1')).toHaveText('深空回声');
  await page.locator('#begin').click();
  const choices = page.locator('#choices');
  await expect(choices.getByRole('button', { name: /前往走廊/ })).toBeVisible({ timeout: 90_000 });
  const meters = page.locator('#meters .meter');
  await expect(meters).toHaveText(['氧气 8', '电量 20']);
  await choices.getByRole('button', { name: /前往走廊/ }).click();
  await expect(choices.getByRole('button', { name: /去工具间/ })).toBeVisible();
  // 深空剧本有 35% 概率的电量波动（随机种子每局不同），电量可能多掉一格。
  await expect(meters.first()).toHaveText('氧气 7');
  await expect(meters.nth(1)).toHaveText(/^电量 1[89]$/);
  expect(errors).toEqual([]);
});
