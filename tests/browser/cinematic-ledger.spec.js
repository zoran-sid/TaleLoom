// ZC：《雾港旧案：未结的账》影像版。剧情、核对与存档点都由浏览器里的同一个 Python 会话判定；
// 用 tools/film_vectors.py 生成的通关动作驱动调查台，用沿途场景的标准存档直接进入某一段。
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';

const DATA = JSON.parse(execFileSync('python3', ['-B', 'tools/film_vectors.py', 'fog_harbor_ledger'],
  { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));
const VECTORS = Object.fromEntries(DATA.vectors.map((v) => [v.name, v]));
const KEY = 'taleloom:v1:fog_harbor_ledger:checkpoints';

const ready = (page) => page.waitForFunction(() => window.__cinematic?.ready(), null, { timeout: 90_000 });

/** 把若干场景的标准存档写成影像存档点，然后从最后一个继续。 */
async function resumeAt(page, walkthrough, scenes, url = '/cinematic.html?fast=1') {
  const entries = scenes.map(([scene, label], i) => {
    const save = DATA.scenes[walkthrough][scene];
    return { label, scene, turn: save.state.turn, at: 1_000 + i, save };
  });
  await page.goto(url);
  await page.evaluate(([key, value]) => localStorage.setItem(key, value),
    [KEY, JSON.stringify({ checkpoint_version: 1, story_id: 'fog_harbor_ledger', entries })]);
  await page.reload();
  await expect(page.locator('#resume')).toHaveText(`从存档点继续：${entries.at(-1).label}`);
  await page.locator('#resume').click();
  await ready(page);
}

async function closeDesk(page) {
  if (await page.locator('#desk').isVisible()) {
    await page.locator('#desk .desk-close').click();
    await ready(page);
  }
}

async function openDesk(page) {
  if (!(await page.locator('#desk').isVisible())) await page.locator('#choices button[data-action="desk"]').click();
  await expect(page.locator('#desk')).toBeVisible();
}

/** 在调查台上填好一组答案并提交（与玩家的点击操作相同）。 */
async function solve(page, values) {
  const { unit, ...slots } = values;
  const desk = page.locator('#desk');
  if (await desk.locator('.seq').count()) {
    while (await desk.locator('.seq-slot .tile').count()) await desk.locator('.seq-slot .tile').first().click();
    for (const option of Object.values(slots)) await desk.locator(`.seq-pool .tile[data-option="${option}"]`).click();
  } else {
    while (await desk.locator('input[type="checkbox"]:checked').count()) {
      await desk.locator('input[type="checkbox"]:checked').first().uncheck({ force: true });
    }
    for (const [key, option] of Object.entries(slots)) {
      const radio = desk.locator(`input[name="slot-${key}"][value="${option}"]`);
      if (await radio.count()) await radio.check({ force: true });
      else await desk.locator(`input[type="checkbox"][value="${option}"]`).check({ force: true });
    }
  }
  await desk.locator('.desk-submit').click();
}

async function drive(page, { action_id: id, values }) {
  if (id.startsWith('choice:')) {
    await closeDesk(page);
    await page.locator(`#choices button[data-action="${id}"]`).click();
  } else {
    await openDesk(page);
    if (id === 'mystery:inspect') await page.locator(`#desk [data-spot="${values.spot}"]`).click();
    else if (id === 'mystery:hint') await page.locator('#desk .desk-hint').click();
    else await solve(page, values);
  }
  await ready(page);
}

const notes = async (page) => Number(await page.locator('#notes-count').textContent());

test('未结的账：用调查台的点击操作走完信任沟通路线，到达结局“雾散”', async ({ page }) => {
  test.setTimeout(600_000);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/cinematic.html?fast=1');
  await page.locator('#begin').click();
  await ready(page);
  for (const action of VECTORS.truth.actions) await drive(page, action);
  await expect(page.locator('#card')).toContainText('雾散');
  await expect(page.locator('#choices').getByRole('button', { name: /重新开始/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test('灯下残页：进场不给细节，查看后才记入；答错可重试，跳过动画不跳过判定；重复提交只算一次', async ({ page }) => {
  await resumeAt(page, 'truth', [['a03_lamp', '测试 · 灯下残页']]);
  const desk = page.locator('#desk');
  await expect(desk).toBeVisible();
  await expect(desk.locator('.desk-title')).toHaveText('灯下残页');
  const before = await notes(page);
  await expect(desk.locator('.desk-submit')).toBeDisabled();
  await desk.locator('[data-spot="lamp/front"]').click();
  await ready(page);
  expect(await notes(page)).toBe(before + 1);
  await expect(desk.locator('.desk-log')).toContainText('叁佰');
  await desk.locator('[data-spot="lamp/front"]').click();
  await ready(page);
  expect(await notes(page), '重读不重复记入').toBe(before + 1);
  for (const spot of ['lamp/back', 'lamp/letter']) {
    await desk.locator(`[data-spot="${spot}"]`).click();
    await ready(page);
  }
  await expect(desk.locator('.desk-submit')).toBeEnabled();

  // 合成一笔：Python 给出针对性的反馈；连按空格、点画面都不会让它算通过。
  await solve(page, { unit: 'lamp', front: 'merged', back: 'supply', letter: 'gone' });
  await page.keyboard.press('Space');
  await page.locator('#frame').click({ position: { x: 5, y: 5 } });
  await ready(page);
  await expect(desk.locator('.desk-feedback')).toHaveText('两面标题不同，先核对它们分别属于哪笔账。');
  await expect(desk).toBeVisible();
  await expect(desk.locator('.desk-tries')).toHaveText('已尝试 1 次');
  await expect(page.locator('#choices button[data-action="choice:window"]')).toHaveCount(0);

  // 分层提示：从“看哪里”开始。
  await desk.locator('.desk-hint').click();
  await ready(page);
  await expect(desk.locator('.desk-hints li')).toHaveText(['正面窄边、纸背和信封，三处都要看。']);

  // 正确答案连点两次：只核对一次，线索只记一次。
  const count = await notes(page);
  await desk.locator('input[name="slot-front"][value="debt"]').check({ force: true });
  await desk.locator('.desk-submit').evaluate((button) => { button.click(); button.click(); });
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:window"]')).toBeVisible();
  expect(await notes(page)).toBe(count + 1);
});

test('后厨水缸：观察痕迹，错误的取物步骤给出反馈，正确取出后以刻字与旧修补认物', async ({ page }) => {
  await resumeAt(page, 'truth', [['d01_kitchen', '测试 · 后厨']]);
  const desk = page.locator('#desk');
  await expect(desk.locator('.desk-title')).toHaveText('后厨水缸');
  for (const spot of ['lid', 'rim', 'floor']) {
    await desk.locator(`[data-spot="vat/${spot}"]`).click();
    await ready(page);
  }
  await solve(page, { unit: 'vat', s1: 'lid', s2: 'witness', s3: 'lamp', s4: 'pole' });
  await ready(page);
  await expect(desk.locator('.desk-feedback')).toHaveText('先请人在旁边看着，之后取出来的东西才说得清来处。');
  await solve(page, { unit: 'vat', s1: 'witness', s2: 'lid', s3: 'lamp', s4: 'hand' });
  await ready(page);
  await expect(desk.locator('.desk-feedback')).toContainText('用长柄工具');
  await solve(page, { unit: 'vat', s1: 'witness', s2: 'lid', s3: 'lamp', s4: 'pole' });
  await ready(page);
  await closeDesk(page);
  await page.locator('#choices button[data-action="choice:lift"]').click();
  await ready(page);
  await expect(desk.locator('.desk-title')).toHaveText('镇纸认物');
  for (const spot of ['bottom', 'corner']) {
    await desk.locator(`[data-spot="weight/${spot}"]`).click();
    await ready(page);
  }
  await solve(page, { unit: 'weight', mark1: 'copper', mark2: 'heavy' });
  await ready(page);
  await expect(desk.locator('.desk-feedback')).toContainText('只有它才有的记号');
  await solve(page, { unit: 'weight', mark1: 'gull', mark2: 'repair' });
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:sleeve"]')).toBeVisible();
  await page.getByRole('button', { name: /线索笔记/ }).click();
  await expect(page.locator('#notebook')).toContainText('水缸里的镇纸');
});

test('存档点：刷新后继续，回到更早的存档点，后面的存档作废；重新开始清空', async ({ page }) => {
  await resumeAt(page, 'truth', [['a01_found', '一 · 夜深取账'], ['c01_batch', '二 · 旧账']]);
  await expect(page.locator('#desk .desk-title')).toHaveText('五百八十四与两百');
  await page.getByRole('button', { name: /线索笔记/ }).click();
  const saves = page.locator('.nb-save');
  await expect(saves).toHaveCount(2);
  const back = saves.filter({ hasText: '一 · 夜深取账' }).getByRole('button');
  await back.click();
  await back.click();
  await ready(page);
  await closeDesk(page);
  await expect(page.locator('#choices button[data-action="choice:still"]')).toBeVisible();
  const kept = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)).entries.map((e) => e.label), KEY);
  expect(kept).toEqual(['一 · 夜深取账']);

  await page.reload();
  await expect(page.locator('#resume')).toHaveText('从存档点继续：一 · 夜深取账');
  await page.locator('#resume').click();
  await ready(page);
  await closeDesk(page);
  await expect(page.locator('#choices button[data-action="choice:still"]')).toBeVisible();

  await page.locator('#restart').click();
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:route"]')).toBeVisible();
  const fresh = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)).entries.map((e) => e.label), KEY);
  expect(fresh).toEqual(['开场']);
});

for (const [walkthrough, ending, choice] of [
  ['truth', '雾散', 'sign_zhou'], ['insufficient', '雾未散', 'sign_zhou_gap'], ['scapegoat', '错置的账', 'sign_gu'],
  ['wrong', '被误读的人', 'sign_ayun'], ['dawn', '交给天亮', 'hold'],
]) {
  test(`结局：${ending}`, async ({ page }) => {
    await resumeAt(page, walkthrough, [['e04_sign', '测试 · 最后签字']]);
    await page.locator(`#choices button[data-action="choice:${choice}"]`).click();
    await expect(page.locator('#card')).toContainText(ending);
    await expect(page.locator('#choices').getByRole('button', { name: /回到存档点「测试 · 最后签字」|重新开始/ }).first()).toBeVisible();
  });
}

test('手机竖屏：调查台排在画面下方，可以完整作答，没有横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await resumeAt(page, 'truth', [['b06_rewrite', '测试 · 排列']]);
  const frame = await page.locator('#frame').boundingBox();
  const sheet = await page.locator('#desk .desk-sheet').boundingBox();
  expect(sheet.y).toBeGreaterThanOrEqual(frame.y + frame.height - 1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  for (const box of await page.locator('#desk .tile').all()) expect((await box.boundingBox()).height).toBeGreaterThanOrEqual(36);
  await solve(page, VECTORS.truth.actions.find((a) => a.values.unit === 'timeline' && a.values.p1 === 'tea').values);
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:next_zhou"]')).toBeVisible();
});

test('手机横屏：调查台在画面里滚动，按钮都能点到', async ({ page }) => {
  await page.setViewportSize({ width: 844, height: 390 });
  await resumeAt(page, 'truth', [['c05_tonight', '测试 · 三笔钱']]);
  const sheet = page.locator('#desk .desk-sheet');
  const box = await sheet.boundingBox();
  expect(box.y + box.height).toBeLessThanOrEqual(390 + 1);
  await solve(page, { unit: 'sums', m300: 'gu_debt', m384: 'zhou_new', m340: 'relief_old', merge: 'new_old' });
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:kitchen"]')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('键盘：单选用方向键，排序卡片用 Enter、↑↓、Delete', async ({ page }) => {
  await resumeAt(page, 'truth', [['b06_rewrite', '测试 · 排列']]);
  const desk = page.locator('#desk');
  await desk.locator('.seq-pool .tile[data-option="letter"]').focus();
  await page.keyboard.press('Enter');
  await desk.locator('.seq-pool .tile[data-option="tea"]').focus();
  await page.keyboard.press('Enter');
  await expect(desk.locator('.seq-slot .tile')).toHaveText(['阿芸在值房写回信', '阿芸送茶，陈掌柜还应声']);
  await desk.locator('.seq-slot .tile[data-option="tea"]').focus();
  await page.keyboard.press('ArrowUp');
  await expect(desk.locator('.seq-slot .tile')).toHaveText(['阿芸送茶，陈掌柜还应声', '阿芸在值房写回信']);
  await expect(desk.locator('.seq-slot .tile[data-option="tea"]')).toBeFocused();
  await page.keyboard.press('Delete');
  await expect(desk.locator('.seq-slot .tile')).toHaveText(['阿芸在值房写回信']);

  await resumeAt(page, 'truth', [['b02_kitchen', '测试 · 两句话']]);
  await desk.locator('input[name="slot-sentence"][value="bell"]').focus();
  await page.keyboard.press('ArrowDown');
  await expect(desk.locator('input[name="slot-sentence"][value="until"]')).toBeChecked();
  await expect(desk.locator('label.chip.on')).toHaveText('周：“阿芸一直在，约到十一点二十分，我们才散。”');
});

test('减少动态效果：调查台照常核对，结果不依赖动画', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await resumeAt(page, 'truth', [['b02_kitchen', '测试 · 两句话']]);
  await solve(page, { unit: 'claims', sentence: 'until', record: 'claim' });
  await ready(page);
  await expect(page.locator('#choices button[data-action="choice:private"]')).toBeVisible();
});

test('声音：静音与音量会记住；转入后台时暂停，回来不叠加；重要声音有文字说明', async ({ page }) => {
  await page.addInitScript(() => {
    window.__caps = [];
    document.addEventListener('DOMContentLoaded', () => {
      const node = document.getElementById('sound-caption');
      new MutationObserver(() => { if (node.textContent) window.__caps.push(node.textContent); })
        .observe(node, { childList: true, characterData: true, subtree: true });
    });
  });
  await resumeAt(page, 'truth', [['p02_lobby', '测试 · 大堂']]);
  await page.locator('#mute').click();
  await expect(page.locator('#mute')).toHaveAttribute('aria-pressed', 'true');
  await page.locator('#volume').fill('40');
  const sound = () => page.evaluate(() => {
    const s = window.__cinematic.sound;
    return { timers: s.timers.length, state: s.ctx?.state, muted: s.muted, volume: s.volume };
  });
  const before = await sound();
  expect(before.muted).toBe(true);
  expect(before.volume).toBeCloseTo(0.4);
  expect(before.timers, '大堂有座钟的嘀嗒声').toBeGreaterThan(0);
  const hide = (hidden) => page.evaluate((value) => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => value });
    document.dispatchEvent(new Event('visibilitychange'));
  }, hidden);
  await hide(true);
  await expect.poll(async () => (await sound()).timers).toBe(0);
  await expect.poll(async () => (await sound()).state).toBe('suspended');
  await hide(false);
  await expect.poll(async () => (await sound()).state).toBe('running');
  expect((await sound()).timers, '回来后不叠加').toBe(before.timers);
  await hide(false);
  expect((await sound()).timers).toBe(before.timers);
  expect(await page.evaluate(() => window.__caps.some((c) => c.includes('环境声')))).toBe(true);
  await page.reload();
  await expect(page.locator('#mute')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#volume')).toHaveValue('40');
});

test('生产构建：调查台和动画库随站点打包，没有外部请求和缺失资源', async ({ page }) => {
  const failed = [];
  page.on('response', (response) => { if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`); });
  await page.route('**/*', (route) => (new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort()));
  await resumeAt(page, 'truth', [['a03_lamp', '测试 · 灯下残页']]);
  await expect(page.locator('#desk .desk-title')).toHaveText('灯下残页');
  expect(failed).toEqual([]);
  const scripts = await page.evaluate(() => [...document.scripts].map((s) => s.src).filter(Boolean));
  expect(scripts.every((src) => new URL(src).hostname === '127.0.0.1')).toBe(true);
});

test('深空影像版与旧样片仍按各自的剧本播放', async ({ page }) => {
  await page.goto('/cinematic.html?fast=1&story=deep_space_film');
  await expect(page.locator('#intro h1')).toHaveText('深空回声');
  await page.locator('#begin').click();
  await ready(page);
  await expect(page.locator('#meters .meter').first()).toContainText('氧气');
  await expect(page.locator('#chances')).toBeVisible();
  await page.goto('/cinematic.html?fast=1&story=fog_harbor_film');
  await page.locator('#begin').click();
  await ready(page);
  await expect(page.locator('#choices').getByRole('button', { name: /推开账房的门/ })).toBeVisible();
});
