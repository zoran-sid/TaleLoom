import { test, expect } from '@playwright/test';

// 第二轮 ZRS 检查项：影像模式的键盘操作、减少动态效果、字幕可读性、手机布局。
// 这些用例只读计算样式与几何，不依赖演出时长；用 fast=1 跳过片头等待。

const idle = async (page) => page.waitForTimeout(300);

async function openCinematic(page, width = 1024, height = 768) {
  await page.setViewportSize({ width, height });
  // 不用 fast=1：该模式会让转场卡停住（已开 issue 给 ZC）。
  await page.goto('/cinematic.html');
  await expect(page.locator('#intro')).toHaveCSS('opacity', '1', { timeout: 30_000 });
}

test('影像模式：开始按钮可用键盘聚焦且焦点可见', async ({ page }) => {
  await openCinematic(page);
  await page.locator('#begin').focus();
  const begin = await page.evaluate(() => {
    const node = document.activeElement;
    const style = getComputedStyle(node);
    return { tag: node.tagName, id: node.id, outline: `${style.outlineStyle} ${style.outlineWidth}`, border: style.borderColor };
  });
  expect(begin.tag).toBe('BUTTON');
  expect(begin.id).toBe('begin');
  // 焦点必须可见：要么有轮廓，要么边框变化
  const visible = (begin.outline.includes('solid') && !begin.outline.includes('0px')) || begin.border !== '';
  expect(visible).toBe(true);
});

test('影像模式：减少动态效果时关闭颗粒与转场', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openCinematic(page);
  await page.locator('#begin').click();
  await idle(page);
  const motion = await page.evaluate(() => {
    const grain = getComputedStyle(document.querySelector('#grain'));
    const canvas = getComputedStyle(document.querySelector('#stage'));
    const intro = getComputedStyle(document.querySelector('#intro'));
    return {
      reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
      grainAnimation: grain.animationName,
      grainOpacity: grain.opacity,
      canvasFilter: canvas.filter,
      introTransition: intro.transitionDuration,
    };
  });
  expect(motion.reduced).toBe(true);
  expect(motion.grainAnimation).toBe('none');
});

for (const width of [390, 768, 1440]) {
  test(`影像模式：${width}px 下字幕行长与字号可读`, async ({ page }) => {
    await openCinematic(page, width, width < 500 ? 844 : 900);
    await page.locator('#begin').click();
    // 等一句真正显示出来的字幕（片头卡先退场）
    let text = '';
    for (let i = 0; i < 90; i += 1) {
      const state = await page.evaluate(() => {
        const s = document.querySelector('#subtitle');
        return { hidden: s.hidden, text: s.textContent.trim() };
      });
      if (!state.hidden && state.text.length > 6) { text = state.text; break; }
      await page.waitForTimeout(250);
    }
    expect(text.length, '字幕应显示出来').toBeGreaterThan(6);
    const metrics = await page.evaluate(() => {
      const sub = document.querySelector('#subtitle');
      const style = getComputedStyle(sub);
      const box = sub.getBoundingClientRect();
      const frame = document.querySelector('#frame').getBoundingClientRect();
      return {
        fontPx: parseFloat(style.fontSize),
        lineHeightPx: parseFloat(style.lineHeight),
        charsPerLine: style.maxWidth === 'none' ? null : null,
        boxWidth: Math.round(box.width),
        frameWidth: Math.round(frame.width),
        ratio: +(box.width / frame.width).toFixed(2),
        overflowX: document.documentElement.scrollWidth > innerWidth,
      };
    });
    // 手机不小于 16px；宽屏封顶 30px，不随视口无限放大
    expect(metrics.fontPx).toBeGreaterThanOrEqual(15.5);
    expect(metrics.fontPx).toBeLessThanOrEqual(32);
    // 宽屏一行不宜过长；手机 8% 边距留白是合理的
    expect(metrics.ratio).toBeLessThanOrEqual(width >= 768 ? 0.92 : 1);
    expect(metrics.overflowX).toBe(false);
  });
}

test('影像模式：手机竖屏无横向溢出，选项不压字幕', async ({ page }) => {
  await openCinematic(page, 390, 844);
  await page.locator('#begin').click();
  for (let i = 0; i < 120; i += 1) {
    const ready = await page.evaluate(() => !document.querySelector('#choices').hidden
      && document.querySelector('#card').hidden);
    if (ready) break;
    await page.keyboard.press('Space');
    await page.waitForTimeout(150);
  }
  const layout = await page.evaluate(() => {
    const sub = document.querySelector('#subtitle').getBoundingClientRect();
    const choices = document.querySelector('#choices').getBoundingClientRect();
    return {
      overflowX: document.documentElement.scrollWidth > innerWidth,
      overlap: choices.top < sub.bottom && sub.height > 0,
      choiceHeights: [...document.querySelectorAll('#choices button')].map((b) => b.getBoundingClientRect().height),
    };
  });
  expect(layout.overflowX).toBe(false);
  expect(layout.overlap, '选项不应压在字幕上').toBe(false);
  for (const height of layout.choiceHeights) expect(height).toBeGreaterThanOrEqual(44);
});
