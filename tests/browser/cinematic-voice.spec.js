import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';

const DATA = JSON.parse(execFileSync('python3', ['-B', 'tools/film_vectors.py', 'fog_harbor_ledger'],
  { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));

test('周文配音跟随原句，玩家点击后停止，文字不会随声音自动前进', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const save = DATA.scenes.truth.b06_rewrite;
  const entries = [{ label: '测试 · 复盘', scene: 'b06_rewrite', turn: save.state.turn, at: 1_000, save }];
  await page.goto('/cinematic.html');
  await page.evaluate((value) => localStorage.setItem('taleloom:v1:fog_harbor_ledger:checkpoints', value),
    JSON.stringify({ checkpoint_version: 1, story_id: 'fog_harbor_ledger', entries }));
  await page.reload();
  await page.locator('#resume').click();
  await page.locator('#choices button[data-action="choice:next_zhou"]').click();
  const line = page.locator('#subtitle .line');
  for (let i = 0; i < 16; i += 1) {
    await expect(page.locator('#frame[data-awaiting-advance="true"]')).toBeVisible();
    if ((await line.textContent()).includes('也许是记到别处了')) break;
    const previous = await line.textContent();
    await page.locator('#skip').click();
    await expect.poll(() => line.textContent()).not.toBe(previous);
  }
  await expect(line).toContainText('也许是记到别处了');
  await expect.poll(() => page.evaluate(() => window.__cinematic.sound.samples.voice?.id)).toBe('voice_zhou_c01');
  await page.waitForTimeout(2700);
  await expect(line).toContainText('也许是记到别处了');
  await page.locator('#skip').click();
  await expect.poll(() => page.evaluate(() => window.__cinematic.sound.samples.voice)).toBe(null);
  await expect(line).not.toContainText('也许是记到别处了');
});

test('序章大堂：周文的原句能触发已录配音', async ({ page }) => {
  const save = DATA.scenes.truth.p02_lobby;
  const entries = [{ label: '测试 · 大堂', scene: 'p02_lobby', turn: save.state.turn, at: 1_000, save }];
  await page.goto('/cinematic.html?fast=1');
  await page.evaluate((value) => localStorage.setItem('taleloom:v1:fog_harbor_ledger:checkpoints', value),
    JSON.stringify({ checkpoint_version: 1, story_id: 'fog_harbor_ledger', entries }));
  await page.reload();
  await page.locator('#resume').click();
  const voice = () => page.evaluate(() => window.__cinematic.sound.samples.voice?.id || null);
  await page.evaluate(() => window.__cinematic.sound.playVoiceFor(
    { story_id: 'fog_harbor_ledger', scene_id: 'p02_lobby' },
    { speaker: '周文', text: '“商行来的？周文。我替掌柜记账。”' }));
  await expect.poll(voice, { timeout: 10_000 }).toBe('voice_zhou_p02_lobby_1');
  await page.waitForTimeout(700);
  expect(await voice()).toBe('voice_zhou_p02_lobby_1');
});
