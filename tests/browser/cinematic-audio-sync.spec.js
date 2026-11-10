import { test, expect } from '@playwright/test';

test('配音自动推动整场文字，环境声说明不重复', async ({ page }) => {
  test.setTimeout(30_000);
  await page.addInitScript(() => {
    window.__readPages = [];
    class TimedAudio extends EventTarget {
      constructor(src) { super(); this.src = src; this.duration = 2; this.currentTime = 0; this.paused = true; }
      play() {
        this.paused = false;
        clearInterval(this.timer);
        this.timer = setInterval(() => {
          if (this.paused) return;
          this.currentTime = Math.min(this.duration, this.currentTime + 0.25);
          this.dispatchEvent(new Event('timeupdate'));
          if (this.currentTime === this.duration) {
            clearInterval(this.timer);
            this.dispatchEvent(new Event('ended'));
          }
        }, 40);
        return Promise.resolve();
      }
      pause() { this.paused = true; clearInterval(this.timer); }
    }
    window.Audio = TimedAudio;
    document.addEventListener('DOMContentLoaded', () => {
      const node = document.getElementById('subtitle');
      new MutationObserver(() => {
        const text = node.querySelector('.line')?.textContent;
        if (text) window.__readPages.push(text);
      }).observe(node, { childList: true, subtree: true });
    });
  });
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await expect(page.locator('#choices button[data-action="choice:route"]')).toBeVisible({ timeout: 15_000 });
  expect(await page.evaluate(() => new Set(window.__readPages).size)).toBeGreaterThan(1);
  const captions = await page.evaluate(async () => {
    const sound = window.__cinematic.sound;
    const node = document.getElementById('sound-caption');
    let changes = 0;
    const observer = new MutationObserver(() => { changes += 1; });
    observer.observe(node, { childList: true, characterData: true, subtree: true });
    sound.setAmbience('kitchen');
    sound.setAmbience('harbor');
    await new Promise(resolve => setTimeout(resolve, 0));
    const first = changes;
    sound.setAmbience('kitchen');
    sound.setAmbience('harbor');
    await new Promise(resolve => setTimeout(resolve, 0));
    observer.disconnect();
    return [first, changes - first];
  });
  expect(captions[0]).toBeGreaterThan(0);
  expect(captions[1]).toBe(0);
});
