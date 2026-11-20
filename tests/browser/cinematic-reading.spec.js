import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const first = '最后一班外海客船靠岸时，雨已经停了。码头的石缝里积着水，雾从水面慢慢涨到人的膝边。';

async function start(page, width = 1280, height = 900) {
  await page.setViewportSize({ width, height });
  // fast 只缩短画面转场，不能把用户要求的手动阅读变回自动播放。
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await expect(page.locator('#subtitle .line')).toHaveText(first, { timeout: 30_000 });
}

async function readToChoices(page, speakers = []) {
  for (let i = 0; i < 180; i++) {
    if (await page.locator('#choices').isVisible()) return speakers;
    if (await page.locator('#frame[data-awaiting-advance="true"]').count()) {
      const [speaker] = await page.locator('#subtitle .speaker').allTextContents();
      if (speaker && speakers.at(-1) !== speaker) speakers.push(speaker);
      await page.locator('#skip').click();
    } else await page.waitForTimeout(40);
  }
  throw new Error('没有等到剧情选项');
}

test('整段立即出现，等待不会播放下一段；点击和空格各推进一段', async ({ page }) => {
  await start(page);
  await page.waitForTimeout(1800);
  await expect(page.locator('#subtitle .line')).toHaveText(first);
  await expect(page.locator('#choices')).toBeHidden();
  await page.keyboard.press('Space');
  await expect(page.locator('#subtitle .line')).toContainText('你提着商行的公文袋');
  const second = await page.locator('#subtitle .line').innerText();
  await page.keyboard.down('Space');
  await expect(page.locator('#subtitle .line')).not.toHaveText(second);
  const third = await page.locator('#subtitle .line').innerText();
  await page.keyboard.down('Space'); // 按住空格的重复事件不能连跳。
  await page.keyboard.up('Space');
  await expect(page.locator('#subtitle .line')).toHaveText(third);
  await page.locator('#frame').click({ position: { x: 40, y: 90 } });
  await expect(page.locator('#subtitle .speaker')).toHaveText('阿水');
  await expect(page.locator('#subtitle .line')).toHaveText('“去旅馆，走前头那条路。后院的石阶涨潮淹了，别图近。”');
  await expect(page.locator('#subtitle .speaker')).toHaveCSS('color', 'rgb(243, 173, 106)');
  await expect(page.locator('#subtitle .line')).toHaveCSS('color', 'rgb(255, 255, 255)');
});

test('笔记打开时继续按钮不会跳剧情；旁白和证物引用不冒充人物对白', async ({ page }) => {
  await start(page);
  await expect(page.locator('#subtitle .speaker')).toHaveCount(0);
  await page.keyboard.press('n');
  await page.locator('#skip').click();
  await page.keyboard.press('Space');
  await page.keyboard.press('Escape');
  await expect(page.locator('#subtitle .line')).toHaveText(first);
  await page.keyboard.press('Space');
  await expect(page.locator('#subtitle .line')).toContainText('“海鸥”的木牌');
  await expect(page.locator('#subtitle .speaker')).toHaveCount(0);
});

test('阅读中也能重新开始，不必先读完当前场景', async ({ page }) => {
  await start(page);
  await page.keyboard.press('Space');
  await expect(page.locator('#subtitle .line')).not.toHaveText(first);
  await page.locator('#restart').click();
  await expect(page.locator('#subtitle .line')).toHaveText(first);
  await page.waitForTimeout(300);
  await expect(page.locator('#subtitle .line')).toHaveText(first);
});

test('进入大堂后立即跳过首句，迟到的配音会从第二句开始', async ({ page }) => {
  await page.addInitScript(() => {
    const BrowserAudio = window.Audio;
    window.Audio = function (src) {
      if (!src.includes('scene_p02_lobby')) return new BrowserAudio(src);
      const audio = new EventTarget();
      Object.assign(audio, {
        duration: NaN,
        currentTime: 0,
        play: () => Promise.resolve(),
        pause: () => {},
      });
      window.lobbyVoice = audio;
      return audio;
    };
  });
  await start(page);
  await readToChoices(page);
  for (const id of ['route', 'notice']) {
    await page.locator(`[data-action="choice:${id}"]`).click();
    await readToChoices(page);
  }
  await page.locator('[data-action="choice:inn"]').click();
  const subtitle = page.locator('#subtitle .line');
  await expect(subtitle).toContainText('大堂的炉火有些弱');
  await page.locator('#skip').click();
  await expect(subtitle).toHaveText('“商行来的？周文。我替掌柜记账。”');
  const position = await page.evaluate(() => {
    const audio = window.lobbyVoice;
    audio.duration = 100;
    audio.dispatchEvent(new Event('durationchange'));
    audio.dispatchEvent(new Event('loadedmetadata'));
    return audio.currentTime;
  });
  const timing = JSON.parse(readFileSync(new URL('../../web/cinematic/seed-runtime.json', import.meta.url)));
  const { cues, duration } = timing.scenes.p02_lobby;
  expect(position).toBeCloseTo(100 * cues[0] / duration);
  await expect(subtitle).toHaveText('“商行来的？周文。我替掌柜记账。”');
});

test('同场对白准确交替显示陈掌柜、阿芸、周文，原剧情不变', async ({ page }) => {
  await start(page);
  await readToChoices(page);
  for (const id of ['route', 'notice', 'inn']) {
    await page.locator(`[data-action="choice:${id}"]`).click();
    await readToChoices(page);
  }
  await page.locator('[data-action="choice:dinner"]').click();
  const speakers = await readToChoices(page);
  // 保留原播放器顺序：先读场景，再读这次选择带来的反馈。
  expect(speakers.slice(0, 5)).toEqual(['陈掌柜', '阿芸', '陈掌柜', '周文', '阿芸']);
  expect(speakers.slice(-3)).toEqual(['周文', '你', '周文']);
  await expect(page.locator('#subtitle .line')).toContainText('顾先生低头擦怀表');
  await expect(page.locator('[data-action="choice:wages"]')).toBeVisible();
});

for (const [width, height] of [[1440, 900], [390, 844], [844, 390]]) {
  test(`${width}×${height}：选项居中、底部保留剧情且不重叠`, async ({ page }) => {
    await start(page, width, height);
    for (let i = 0; i < 40 && !(await page.locator('#choices').isVisible()); i++) {
      await page.locator('#skip').click();
      await page.waitForTimeout(50);
    }
    await expect(page.locator('#choices')).toBeVisible();
    await expect(page.locator('#subtitle .line')).not.toBeEmpty();
    const boxes = await page.evaluate(() => {
      const rect = id => { const r = document.getElementById(id).getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height, bottom: r.bottom }; };
      return { frame: rect('frame'), choices: rect('choices'), text: rect('subtitle'),
        overflow: document.documentElement.scrollWidth > innerWidth,
        font: parseFloat(getComputedStyle(document.querySelector('#subtitle .line')).fontSize) };
    });
    expect(boxes.overflow).toBe(false);
    expect(boxes.font).toBeGreaterThanOrEqual(18);
    expect(boxes.choices.y).toBeGreaterThan(boxes.frame.y + boxes.frame.height * .1);
    expect(boxes.choices.bottom).toBeLessThanOrEqual(boxes.text.y);
    expect(boxes.text.bottom).toBeLessThanOrEqual(boxes.frame.bottom);
    expect(Math.abs(boxes.choices.x + boxes.choices.width / 2 - boxes.frame.x - boxes.frame.width / 2)).toBeLessThan(2);
  });
}
