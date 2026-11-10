// 通关测试用真实“继续剧情”按钮读完段落；fast=1 仅加速转场。
// 专门验证手动阅读的 cinematic-reading.spec.js 使用原生 Playwright，不装这个驱动。
import { test as base, expect } from '@playwright/test';
export { expect };
export const test = base.extend({
  readingDriver: [async ({ page }, use) => {
    let stopped = false;
    const reading = (async () => {
      while (!stopped) {
        try {
          if (new URL(page.url()).searchParams.get('fast') === '1'
              && await page.locator('#frame[data-awaiting-advance="true"]').count()
              && !await page.locator('#notebook').isVisible()) {
            await page.locator('#skip').click({ timeout: 300 });
          }
        } catch { /* 页面导航或关闭时，让下一次观察重新定位。 */ }
        await new Promise(resolve => setTimeout(resolve, 35));
      }
    })();
    await use();
    stopped = true;
    await reading;
  }, { auto: true }],
});
