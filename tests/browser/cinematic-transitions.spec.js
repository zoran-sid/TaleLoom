import { test, expect } from './cinematic-driver.js';
import { execFileSync } from 'node:child_process';
import process from 'node:process';

const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const data = JSON.parse(execFileSync(PYTHON, ['-B', 'tools/film_vectors.py', 'fog_harbor_ledger'],
  { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));
const actions = data.vectors.find(vector => vector.name === 'truth').actions;

test('八段视频按实际剧情顺序播放，最后签字仍由玩家选择', async ({ page }) => {
  test.setTimeout(300_000);
  await page.addInitScript(() => {
    window.playedTransitions = [];
    document.addEventListener('ended', event => {
      if (event.target.id === 'scene-transition') {
        window.playedTransitions.push(new URL(event.target.currentSrc).pathname);
      }
    }, true);
  });
  await page.goto('/cinematic.html?fast=1&transitions=1');
  await page.locator('#begin').click();
  const ready = () => page.waitForFunction(() => window.__cinematic?.ready(), null, { timeout: 60_000 });
  await ready();
  for (const action of actions) {
    await page.locator(`#choices button[data-action="${action.action_id}"]`).click();
    await ready();
    if ((await page.evaluate(() => window.playedTransitions)).length === 8) break;
  }
  expect(await page.evaluate(() => window.playedTransitions)).toEqual([
    expect.stringContaining('dock-opening'),
    expect.stringContaining('office-arrival'),
    expect.stringContaining('office-night'),
    expect.stringContaining('duty-room'),
    expect.stringContaining('old-ledger'),
    expect.stringContaining('water-vat'),
    expect.stringContaining('dawn-table'),
    expect.stringContaining('final-signature'),
  ]);
  await expect(page.locator('#scene-transition')).toBeHidden();
  await expect(page.locator('#choices button[data-action="choice:sign_zhou"]')).toBeVisible();
});

test('视频加载失败时继续进入剧情，仍由玩家推进阅读', async ({ page }) => {
  await page.route('**/*dock-opening*.mp4', route => route.abort());
  await page.goto('/cinematic.html?fast=1&transitions=1');
  await page.locator('#begin').click();
  await page.waitForFunction(() => window.__cinematic?.ready(), null, { timeout: 60_000 });
  await expect(page.locator('#scene-transition')).toBeHidden();
  await expect(page.locator('#choices')).toBeVisible();
});

test('手机上可跳过开场视频，随后仍停在第一段等玩家继续', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/cinematic.html');
  await page.locator('#begin').click();
  const video = page.locator('#scene-transition[data-visible]');
  await expect(video).toBeVisible({ timeout: 60_000 });
  await page.locator('#skip').click();
  await expect(page.locator('#scene-transition')).toBeHidden();
  const frame = page.locator('#frame');
  await expect(frame).toHaveAttribute('data-awaiting-advance', 'true');
  const text = await page.locator('#subtitle .line').innerText();
  await expect(page.locator('#choices')).toBeHidden();
  await page.locator('#skip').click();
  await expect(page.locator('#subtitle .line')).not.toHaveText(text);
});

test('减少动态效果设置跳过视频，保留现有场景阅读', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  let requested = false;
  page.on('request', request => { if (request.url().endsWith('.mp4')) requested = true; });
  await page.goto('/cinematic.html?fast=1&transitions=1');
  await page.locator('#begin').click();
  await page.waitForFunction(() => window.__cinematic?.ready(), null, { timeout: 60_000 });
  expect(requested).toBe(false);
  await expect(page.locator('#choices')).toBeVisible();
});
