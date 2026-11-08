/**
 * 影像模式的画面：Canvas 实时绘制场景、镜头运动、雾与光。负责人：ZC（样片）。
 *
 * 所有坐标使用 1600×900 的虚拟画布，按实际尺寸缩放；不加载图片文件。
 * 画面只读剧情状态（当前场景、审问对象），不参与任何剧情判定。
 */

const W = 1600;
const H = 900;
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const INK = '#040405';
const AMBER = '236,172,92';
const FIRE = '255,142,58';
const COOL = '165,182,198';

// ---------- 小工具 ----------

function prng(seed) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => { const k = clamp01(x); return k * k * (3 - 2 * k); };
const flicker = (t, k = 1) => 0.9 + 0.05 * Math.sin(t * 13.1 * k) + 0.035 * Math.sin(t * 7.7 * k + 1.3) + 0.02 * Math.sin(t * 23.3 * k);

function hex(c) { return [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)); }
function mix(a, b, k) {
  const x = hex(a);
  const y = hex(b);
  return `rgb(${x.map((v, i) => Math.round(v + (y[i] - v) * k)).join(',')})`;
}
function glow(ctx, x, y, r, rgb, a) {
  if (a <= 0) return;
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, `rgba(${rgb},${a})`);
  g.addColorStop(1, `rgba(${rgb},0)`);
  ctx.fillStyle = g;
  ctx.fillRect(x - r, y - r, r * 2, r * 2);
}
function vfill(ctx, x, y, w, h, stops) {
  const g = ctx.createLinearGradient(0, y, 0, y + h);
  stops.forEach(([o, c]) => g.addColorStop(o, c));
  ctx.fillStyle = g;
  ctx.fillRect(x, y, w, h);
}
function poly(ctx, pts, fill) {
  ctx.beginPath();
  ctx.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();
}
function shade(ctx, x, y, r, edge) {
  const g = ctx.createRadialGradient(x, y, r * 0.12, x, y, r);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, `rgba(0,0,0,${edge})`);
  ctx.fillStyle = g;
  ctx.fillRect(-300, -300, W + 600, H + 600);
}
function ellipsePath(ctx, x, y, rx, ry, rot = 0) {
  ctx.moveTo(x + rx * Math.cos(rot), y + rx * Math.sin(rot));
  ctx.ellipse(x, y, rx, ry, rot, 0, Math.PI * 2);
}

/** 无状态的粒子：按时间算出位置，适合烟、蒸汽和从窗口灌进来的雾。 */
function plume(ctx, sprite, t, { x, y, count, life, rise, spread, drift = 0, ySpread = 0, size, alpha, seed = 1 }) {
  const r = prng(seed);
  for (let i = 0; i < count; i += 1) {
    const jitter = r();
    const lane = r();
    const age = ((t + (i / count) * life + jitter * life * 0.3) % life) / life;
    const px = x + drift * age * life + Math.sin(age * 5 + i) * spread * age + (jitter - 0.5) * spread * 0.4;
    const py = y - rise * age * life + (lane - 0.5) * ySpread * (0.4 + age);
    const s = size * (0.4 + age * 1.6);
    ctx.globalAlpha = alpha * Math.sin(Math.PI * age);
    ctx.drawImage(sprite, px - s, py - s * 0.6, s * 2, s * 1.2);
  }
  ctx.globalAlpha = 1;
}

function makeSprite(rgb) {
  const c = document.createElement('canvas');
  c.width = 128;
  c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, `rgba(${rgb},1)`);
  grad.addColorStop(0.45, `rgba(${rgb},0.45)`);
  grad.addColorStop(1, `rgba(${rgb},0)`);
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  return c;
}

class Fog {
  constructor(count, seed) {
    const r = prng(seed);
    this.p = Array.from({ length: count }, () => ({
      x: r() * W * 1.6, y: r(), s: 160 + r() * 360, v: 5 + r() * 16, a: 0.05 + r() * 0.08, ph: r() * 6.28,
    }));
  }

  draw(ctx, t, sprite, { alpha = 1, top = 0, bottom = H, drift = 1 } = {}) {
    for (const p of this.p) {
      const span = W * 1.9;
      const x = (((p.x + t * p.v * drift) % span) + span) % span - W * 0.35;
      const y = top + p.y * (bottom - top) + Math.sin(t * 0.21 + p.ph) * 16;
      ctx.globalAlpha = p.a * alpha * (0.7 + 0.3 * Math.sin(t * 0.33 + p.ph));
      ctx.drawImage(sprite, x - p.s, y - p.s * 0.45, p.s * 2, p.s * 0.9);
    }
    ctx.globalAlpha = 1;
  }
}

// ---------- 人物剪影 ----------

/** 顾先生坐在藤椅上；hand 为 0（放下）到 1（举到嘴边）。返回烟头位置。 */
function seatedGu(ctx, hand) {
  ellipsePath(ctx, 305, 452, 25, 31);               // 头
  ellipsePath(ctx, 306, 424, 54, 9);                // 帽檐
  ctx.moveTo(283, 425);
  ctx.bezierCurveTo(283, 392, 330, 392, 330, 425);  // 帽顶
  ctx.moveTo(292, 478);                             // 颈、肩、躯干
  ctx.lineTo(318, 478);
  ctx.bezierCurveTo(372, 486, 382, 520, 378, 620);
  ctx.lineTo(238, 620);
  ctx.bezierCurveTo(236, 530, 246, 488, 292, 478);
  ctx.moveTo(330, 598);                             // 翘起的腿
  ctx.lineTo(470, 588);
  ctx.lineTo(474, 618);
  ctx.lineTo(340, 632);
  ctx.moveTo(442, 600);
  ctx.lineTo(474, 600);
  ctx.lineTo(468, 742);
  ctx.lineTo(492, 750);
  ctx.lineTo(492, 762);
  ctx.lineTo(440, 762);
  ctx.moveTo(250, 616);                             // 另一条腿
  ctx.lineTo(300, 616);
  ctx.lineTo(296, 760);
  ctx.lineTo(262, 760);
  const hx = 372 + (318 - 372) * hand;
  const hy = 596 + (470 - 596) * hand;
  const ex = 364 + (hx - 364) * 0.55 + 30 * (1 - hand);
  const ey = 506 + (hy - 506) * 0.55 + 40;
  ctx.moveTo(352, 500);                             // 拿烟的手臂
  ctx.lineTo(ex + 12, ey);
  ctx.lineTo(hx + 10, hy + 8);
  ctx.lineTo(hx - 8, hy - 6);
  ctx.lineTo(ex - 10, ey - 8);
  ctx.lineTo(340, 512);
  return [hx - 10, hy - 4];
}

/** 藤椅：深褐色、带编织纹理和一侧受光的边，和坐着的人区分开。 */
function rattanChair(ctx, f) {
  ctx.save();
  ctx.beginPath();
  ellipsePath(ctx, 222, 496, 100, 126);
  ctx.fillStyle = '#1e150d';
  ctx.fill();
  ctx.clip();
  ctx.strokeStyle = `rgba(${AMBER},0.09)`;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = -12; i < 14; i += 1) {
    ctx.moveTo(90 + i * 20, 360);
    ctx.lineTo(170 + i * 20, 640);
    ctx.moveTo(170 + i * 20, 360);
    ctx.lineTo(90 + i * 20, 640);
  }
  ctx.stroke();
  ctx.restore();
  ctx.strokeStyle = `rgba(${AMBER},${0.32 * f})`;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.ellipse(222, 496, 100, 126, 0, -1.25, 0.75);
  ctx.stroke();
  ctx.fillStyle = '#150e09';
  ctx.fillRect(140, 602, 250, 34);
  ctx.fillRect(152, 630, 14, 130);
  ctx.fillRect(366, 630, 14, 130);
  ctx.fillStyle = `rgba(${AMBER},${0.2 * f})`;
  ctx.fillRect(140, 602, 250, 3);
}

/** 站立的人物：kind 为 ayun（发髻、围裙）或 zhou（长衫、眼镜）。 */
function standing(ctx, kind, x, base, t) {
  const sway = Math.sin(t * 0.9 + x) * 2;
  if (kind === 'ayun') {
    ellipsePath(ctx, x + sway, base - 392, 23, 28);
    ellipsePath(ctx, x - 18 + sway, base - 410, 14, 13);   // 发髻
    ctx.moveTo(x - 12 + sway, base - 366);
    ctx.lineTo(x + 12 + sway, base - 366);
    ctx.bezierCurveTo(x + 48, base - 356, x + 46, base - 300, x + 44, base - 250);
    ctx.lineTo(x + 70, base);
    ctx.lineTo(x - 70, base);
    ctx.lineTo(x - 44, base - 250);
    ctx.bezierCurveTo(x - 46, base - 300, x - 48, base - 356, x - 12 + sway, base - 366);
  } else {
    ellipsePath(ctx, x + sway, base - 422, 24, 30);
    ctx.moveTo(x - 13 + sway, base - 394);
    ctx.lineTo(x + 13 + sway, base - 394);
    ctx.bezierCurveTo(x + 56, base - 384, x + 58, base - 320, x + 54, base - 240);
    ctx.lineTo(x + 50, base);
    ctx.lineTo(x - 50, base);
    ctx.lineTo(x - 54, base - 240);
    ctx.bezierCurveTo(x - 58, base - 320, x - 56, base - 384, x - 13 + sway, base - 394);
    const wipe = Math.sin(t * 5.2) * 6;
    ctx.moveTo(x + 40, base - 360);                          // 擦眼镜的手
    ctx.lineTo(x + 30 + wipe, base - 300);
    ctx.lineTo(x + 18 + wipe, base - 410);
    ctx.lineTo(x + 32 + wipe, base - 414);
    ctx.lineTo(x + 46 + wipe, base - 304);
    ctx.lineTo(x + 54, base - 356);
  }
}

function zhouGlasses(ctx, x, base, t, light) {
  const sway = Math.sin(t * 0.9 + x) * 2;
  ctx.strokeStyle = `rgba(${light},0.35)`;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.arc(x - 10 + sway, base - 424, 7, 0, Math.PI * 2);
  ctx.moveTo(x + 17 + sway, base - 424);
  ctx.arc(x + 10 + sway, base - 424, 7, 0, Math.PI * 2);
  ctx.stroke();
  const pulse = Math.max(0, Math.sin(t * 1.4)) ** 24;
  glow(ctx, x - 12 + sway, base - 426, 18, '255,240,210', 0.9 * pulse);
}

/** 先画偏移的亮色轮廓，再盖上剪影，得到一侧的轮廓光。 */
function silhouette(ctx, draw, rim, dx, alpha) {
  ctx.save();
  ctx.translate(dx, 0);
  ctx.beginPath();
  draw();
  ctx.fillStyle = `rgba(${rim},${alpha})`;
  ctx.fill();
  ctx.restore();
  ctx.beginPath();
  const out = draw();
  ctx.fillStyle = INK;
  ctx.fill();
  return out;
}

// ---------- 场景 ----------

const town = (() => {
  const r = prng(7);
  const blocks = [];
  for (let x = -260; x < W + 260;) {
    const w = 40 + r() * 90;
    const h = 30 + r() * 110;
    const lit = [];
    for (let i = 0; i < 3; i += 1) if (r() < 0.35) lit.push([x + 6 + r() * (w - 14), 548 - h + 10 + r() * (h - 24), r() * 6]);
    blocks.push({ x, w, h, lit });
    x += w + r() * 6;
  }
  return blocks;
})();

function harbor(ctx, s, o, st) {
  const dawn = o.dawn ? ease(s / 14) : 0;
  vfill(ctx, -300, -300, W + 600, 860, [[0, mix('#03050a', '#3c4652', dawn)], [1, mix('#1a2430', '#a8a9a2', dawn)]]);
  glow(ctx, 1180, 170, 340, '205,214,224', 0.1 * (1 - dawn));
  glow(ctx, 1120, 560, 760, '246,205,150', 0.4 * dawn);
  for (const b of town) {
    ctx.fillStyle = mix('#0b1016', '#3b434b', dawn);
    ctx.fillRect(b.x, 548 - b.h, b.w, b.h);
    for (const [wx, wy, ph] of b.lit) {
      ctx.fillStyle = `rgba(${AMBER},${(0.35 + 0.25 * Math.sin(s * 0.7 + ph)) * (1 - dawn)})`;
      ctx.fillRect(wx, wy, 5, 7);
    }
  }
  poly(ctx, [1398, 548, 1442, 548, 1432, 330, 1408, 330], mix('#090c11', '#353c43', dawn));
  ctx.fillStyle = mix('#090c11', '#353c43', dawn);
  ctx.fillRect(1402, 300, 36, 32);
  const lamp = 1 - dawn * 0.8;
  glow(ctx, 1420, 316, 110, AMBER, 0.65 * lamp);
  const angle = s * 0.85;
  for (const a of [angle, angle + Math.PI]) {
    const c = Math.cos(a);
    if (Math.abs(c) < 0.04) continue;
    const end = 1420 + 1900 * c;
    const spread = 18 + 90 * Math.abs(c);
    const g = ctx.createLinearGradient(1420, 316, end, 316);
    g.addColorStop(0, `rgba(${AMBER},${0.24 * lamp * Math.abs(Math.sin(a) * 0.5 + 0.5)})`);
    g.addColorStop(1, `rgba(${AMBER},0)`);
    poly(ctx, [1420, 312, end, 316 - spread, end, 316 + spread, 1420, 320], g);
  }
  vfill(ctx, -300, 548, W + 600, 700, [[0, mix('#0a0f15', '#5c6467', dawn)], [1, mix('#020305', '#23292d', dawn)]]);
  const r = prng(11);
  for (let i = 0; i < 90; i += 1) {
    const depth = (i / 90) ** 1.6;
    const y = 552 + depth * 380;
    const x = r() * (W + 200) - 100 + Math.sin(s * 0.6 + i) * 9;
    const warm = x < 640 || Math.abs(x - 1420) < 160;
    ctx.fillStyle = warm ? `rgba(${AMBER},${0.08 + 0.14 * Math.sin(s * 1.5 + i) ** 2})` : `rgba(${COOL},${0.04 + 0.06 * Math.sin(s * 1.1 + i) ** 2})`;
    ctx.fillRect(x, y, 16 + r() * 80 * (1 - depth * 0.5), 1.4 + depth * 1.6);
  }
  ctx.fillStyle = INK;
  for (let x = 660; x < 1060; x += 46) ctx.fillRect(x, 560, 7, 70 + Math.sin(x) * 8);
  ctx.fillRect(640, 556, 430, 8);
  poly(ctx, [-300, 960, -300, 300, 120, 300, 160, 250, 470, 250, 510, 300, 650, 300, 650, 960], '#060709');
  ctx.fillStyle = '#0d0e10';
  ctx.fillRect(176, 196, 300, 50);
  const sign = flicker(s, 0.4);
  ctx.font = '600 32px "Songti SC","STSong","Noto Serif CJK SC","Source Han Serif SC",serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = `rgba(${AMBER},${0.62 * sign * (1 - dawn * 0.6)})`;
  ctx.fillText('海鸥旅馆', 326, 232);
  glow(ctx, 326, 220, 220, AMBER, 0.12 * sign * (1 - dawn));
  for (let row = 0; row < 2; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      const x = 170 + col * 150;
      const y = 350 + row * 170;
      const on = !(row === 1 && col === 2);
      const f = flicker(s + col * 3 + row * 7, 0.6);
      ctx.fillStyle = on ? `rgba(${AMBER},${0.58 * f * (1 - dawn * 0.7)})` : '#0b0c0e';
      ctx.fillRect(x, y, 62, 86);
      ctx.fillStyle = '#060709';
      ctx.fillRect(x + 29, y, 4, 86);
      ctx.fillRect(x, y + 40, 62, 4);
      if (on) glow(ctx, x + 31, y + 43, 110, AMBER, 0.12 * f * (1 - dawn));
    }
  }
  st.fog.draw(ctx, s, st.cool, { alpha: 1.5 * (1 - 0.85 * dawn), top: 230, bottom: 780 });
  shade(ctx, 700, 450, 1150, 0.62 * (1 - dawn * 0.5));
}

function lobby(ctx, s, o, st) {
  const f = flicker(s);
  vfill(ctx, -300, -300, W + 600, 1020, [[0, '#0f0b08'], [1, '#261c14']]);
  ctx.fillStyle = '#130e0a';
  ctx.fillRect(-300, 520, W + 600, 200);
  ctx.strokeStyle = 'rgba(0,0,0,0.55)';
  ctx.lineWidth = 3;
  for (let x = -260; x < W + 260; x += 170) ctx.strokeRect(x + 18, 540, 134, 160);
  vfill(ctx, -300, 720, W + 600, 500, [[0, '#1a130d'], [1, '#060403']]);
  ctx.strokeStyle = 'rgba(0,0,0,0.4)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = -8; i <= 8; i += 1) { ctx.moveTo(800 + i * 40, 720); ctx.lineTo(800 + i * 260, 1100); }
  ctx.stroke();
  // 门：毛玻璃后是流动的雾
  ctx.fillStyle = '#0a0806';
  ctx.fillRect(500, 240, 210, 482);
  ctx.save();
  ctx.beginPath();
  for (let row = 0; row < 3; row += 1) for (let col = 0; col < 2; col += 1) ctx.rect(518 + col * 92, 262 + row * 118, 82, 104);
  ctx.clip();
  vfill(ctx, 500, 240, 210, 380, [[0, '#2c3743'], [1, '#1b222a']]);
  st.fog.draw(ctx, s * 2.2, st.cool, { alpha: 3.2, top: 240, bottom: 600, drift: 1.4 });
  ctx.restore();
  ctx.fillStyle = 'rgba(0,0,0,0.6)';
  ctx.fillRect(500, 620, 210, 100);
  // 墙上的挂钟与钟摆
  ctx.fillStyle = '#0b0807';
  ctx.fillRect(838, 168, 84, 260);
  ctx.beginPath();
  ctx.arc(880, 222, 34, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(${AMBER},0.22)`;
  ctx.fill();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(880, 222); ctx.lineTo(880, 198);
  ctx.moveTo(880, 222); ctx.lineTo(897, 230);
  ctx.stroke();
  const swing = Math.sin(s * Math.PI) * 0.32;
  ctx.save();
  ctx.translate(880, 270);
  ctx.rotate(swing);
  ctx.fillStyle = `rgba(${AMBER},0.35)`;
  ctx.fillRect(-2, 0, 4, 110);
  ctx.beginPath();
  ctx.arc(0, 118, 13, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  // 柜台、钥匙板、楼梯
  ctx.fillStyle = '#0a0705';
  ctx.fillRect(1010, 290, 300, 140);
  for (let i = 0; i < 12; i += 1) {
    const kx = 1032 + (i % 6) * 46;
    const ky = 312 + Math.floor(i / 6) * 58;
    ctx.fillStyle = `rgba(${AMBER},${0.3 + 0.2 * Math.sin(s * 0.8 + i)})`;
    ctx.fillRect(kx, ky, 3, 18);
  }
  poly(ctx, [960, 724, 960, 540, 1440, 540, 1440, 724], '#070504');
  ctx.fillStyle = `rgba(${AMBER},0.28)`;
  ctx.fillRect(960, 538, 480, 3);
  glow(ctx, 1210, 528, 14, AMBER, 0.6);
  for (let i = 0; i < 9; i += 1) poly(ctx, [1460 + i * 40, 720 - i * 52, 1700, 720 - i * 52, 1700, 760, 1460 + i * 40, 760], i % 2 ? '#080605' : '#0c0907');
  ctx.strokeStyle = `rgba(${AMBER},0.2)`;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(1450, 640);
  ctx.lineTo(1800, 180);
  ctx.stroke();
  if (o.gathering) {
    silhouette(ctx, () => standing(ctx, 'zhou', 1120, 760, s), AMBER, 3, 0.32);
    zhouGlasses(ctx, 1120, 760, s, AMBER);
    silhouette(ctx, () => standing(ctx, 'ayun', 1300, 760, s), AMBER, 3, 0.32);
  }
  // 顾先生与香烟
  const phase = (s % 7) / 7;
  const hand = phase < 0.4 ? Math.sin((phase / 0.4) * Math.PI) : 0;
  rattanChair(ctx, f);
  const [cx, cy] = silhouette(ctx, () => seatedGu(ctx, hand), AMBER, 4, 0.5 * f);
  glow(ctx, cx, cy, 18 + 14 * hand, '255,120,50', 0.75 + 0.25 * hand);
  ctx.fillStyle = `rgba(255,170,90,${0.8 + 0.2 * hand})`;
  ctx.fillRect(cx - 2, cy - 2, 4, 4);
  plume(ctx, st.warm, s, { x: cx, y: cy, count: 16, life: 5.5, rise: 34, spread: 30, size: 16, alpha: 0.22, seed: 3 });
  // 吊灯
  ctx.strokeStyle = INK;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(800, -300);
  ctx.lineTo(800, 120);
  ctx.stroke();
  poly(ctx, [770, 120, 830, 120, 846, 168, 754, 168], '#0b0806');
  glow(ctx, 800, 170, 760, AMBER, 0.28 * f);
  glow(ctx, 800, 168, 120, '255,224,170', 0.75 * f);
  st.fog.draw(ctx, s, st.warm, { alpha: 0.5, top: 120, bottom: 760, drift: 0.4 });
  shade(ctx, 760, 300, 1200, 0.8 * (1.08 - f * 0.1));
}

function office(ctx, s, o, st) {
  vfill(ctx, -300, -300, W + 600, 1000, [[0, '#0a0e13'], [1, '#141b21']]);
  vfill(ctx, -300, 700, W + 600, 520, [[0, '#0b0f12'], [1, '#030405']]);
  // 窗与窗外的雾光
  ctx.fillStyle = '#05070a';
  ctx.fillRect(1044, 156, 352, 420);
  ctx.save();
  ctx.beginPath();
  ctx.rect(1066, 178, 308, 376);
  ctx.clip();
  vfill(ctx, 1066, 178, 308, 376, [[0, '#76838f'], [1, '#4a5662']]);
  st.fog.draw(ctx, s * 2.5, st.cool, { alpha: 4, top: 160, bottom: 560, drift: -1.2 });
  ctx.restore();
  ctx.fillStyle = '#05070a';
  ctx.fillRect(1216, 178, 8, 376);
  ctx.fillRect(1066, 362, 308, 8);
  const open = 0.5 + 0.06 * Math.sin(s * 0.9);
  poly(ctx, [1066, 178, 1066 - 90 * open, 198, 1066 - 90 * open, 536, 1066, 554], 'rgba(34,44,56,0.8)');
  ctx.strokeStyle = 'rgba(150,170,190,0.28)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(1066 - 90 * open, 198);
  ctx.lineTo(1066 - 90 * open, 536);
  ctx.moveTo(1066 - 90 * open, 367);
  ctx.lineTo(1066, 366);
  ctx.stroke();
  const shaft = ctx.createLinearGradient(1180, 300, 600, 940);
  shaft.addColorStop(0, `rgba(${COOL},${0.2 + 0.05 * Math.sin(s * 0.7)})`);
  shaft.addColorStop(1, `rgba(${COOL},0)`);
  poly(ctx, [1066, 190, 1374, 190, 1374, 554, 980, 960, 300, 960], shaft);
  // 窗帘
  ctx.beginPath();
  ctx.moveTo(1010, 120);
  for (let y = 120; y <= 620; y += 20) ctx.lineTo(1010 + Math.sin(y * 0.03 + s * 1.3) * 10 * (y - 120) / 500, y);
  ctx.lineTo(950, 620);
  ctx.lineTo(950, 120);
  ctx.fillStyle = '#070a0d';
  ctx.fill();
  // 门缝里漏进大堂的暖光
  const f = flicker(s, 0.6);
  poly(ctx, [-300, 700, 70, 700, 260, 960, -300, 960], `rgba(${AMBER},${0.1 * f})`);
  ctx.fillStyle = '#040506';
  ctx.fillRect(40, 160, 34, 560);
  // 书桌、账本与伏在桌上的掌柜（只画剪影）
  ctx.beginPath();
  ctx.rect(600, 360, 70, 170);
  ctx.moveTo(596, 520);
  ctx.bezierCurveTo(600, 440, 650, 432, 700, 442);
  ctx.lineTo(760, 470);
  ctx.lineTo(600, 560);
  ellipsePath(ctx, 724, 452, 36, 22, 0.25);
  ctx.moveTo(740, 462);
  ctx.lineTo(868, 462);
  ctx.lineTo(868, 472);
  ctx.lineTo(740, 474);
  ctx.fillStyle = INK;
  ctx.fill();
  poly(ctx, [756, 466, 900, 466, 914, 474, 744, 474], 'rgba(205,205,192,0.32)');
  ctx.fillStyle = '#05070a';
  ctx.fillRect(470, 472, 540, 30);
  ctx.fillRect(492, 500, 496, 140);
  ctx.fillRect(500, 630, 18, 130);
  ctx.fillRect(962, 630, 18, 130);
  ctx.fillStyle = 'rgba(150,170,190,0.28)';
  ctx.fillRect(470, 470, 540, 2);
  ctx.strokeStyle = 'rgba(160,180,200,0.42)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(604, 470);
  ctx.bezierCurveTo(612, 438, 650, 432, 692, 440);
  ctx.moveTo(694, 438);
  ctx.quadraticCurveTo(724, 422, 758, 446);
  ctx.moveTo(760, 461);
  ctx.lineTo(866, 461);
  ctx.stroke();
  // 散落的算盘珠与纸
  ctx.save();
  ctx.translate(560, 836);
  ctx.rotate(-0.18);
  ctx.strokeStyle = '#0b0e11';
  ctx.lineWidth = 8;
  ctx.strokeRect(-90, -28, 180, 56);
  ctx.restore();
  const r = prng(5);
  for (let i = 0; i < 46; i += 1) {
    const bx = 360 + r() * 640;
    const by = 790 + r() * 120;
    ctx.fillStyle = '#0b0d10';
    ctx.beginPath();
    ctx.ellipse(bx, by, 7, 5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(${COOL},0.32)`;
    ctx.fillRect(bx + 1, by - 3, 2, 2);
  }
  for (const [px, py, ph] of [[860, 800, 0], [1000, 860, 2]]) {
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(0.2 + Math.sin(s * 1.7 + ph) * 0.04);
    ctx.fillStyle = 'rgba(190,196,200,0.18)';
    ctx.fillRect(-40, -26, 80, 52);
    ctx.restore();
  }
  plume(ctx, st.cool, s, { x: 1080, y: 380, count: 34, life: 11, rise: -6, drift: -58, spread: 60, ySpread: 300, size: 120, alpha: 0.09, seed: 9 });
  st.fog.draw(ctx, s, st.cool, { alpha: 0.6, top: 500, bottom: 980, drift: -0.5 });
  shade(ctx, 1000, 420, 1250, 0.74);
}

function kitchen(ctx, s, o, st) {
  const f = flicker(s, 1.5);
  vfill(ctx, -300, -300, W + 600, 1060, [[0, '#140d08'], [1, '#2b1b10']]);
  ctx.strokeStyle = 'rgba(0,0,0,0.25)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let y = 40; y < 760; y += 34) {
    ctx.moveTo(-300, y);
    ctx.lineTo(W + 300, y);
    for (let x = (y / 34) % 2 ? -300 : -260; x < W + 300; x += 80) { ctx.moveTo(x, y); ctx.lineTo(x, y + 34); }
  }
  ctx.stroke();
  vfill(ctx, -300, 760, W + 600, 460, [[0, '#140d08'], [1, '#050302']]);
  // 灶台与炉火
  poly(ctx, [60, 790, 60, 430, 540, 430, 540, 790], '#0b0705');
  ctx.fillStyle = '#100a07';
  ctx.fillRect(40, 410, 520, 26);
  glow(ctx, 290, 660, 920, FIRE, 0.3 * f);
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(196, 730);
  ctx.lineTo(196, 640);
  ctx.quadraticCurveTo(290, 560, 384, 640);
  ctx.lineTo(384, 730);
  ctx.clip();
  vfill(ctx, 190, 560, 200, 180, [[0, '#6b2a0e'], [1, '#2a0c04']]);
  for (let i = 0; i < 9; i += 1) {
    const x = 210 + i * 20;
    const h = 60 + 40 * Math.abs(Math.sin(s * (3 + i * 0.7) + i));
    const g = ctx.createLinearGradient(0, 730 - h, 0, 730);
    g.addColorStop(0, 'rgba(255,210,120,0)');
    g.addColorStop(0.5, `rgba(255,160,60,${0.6 * f})`);
    g.addColorStop(1, 'rgba(255,230,160,0.9)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(x - 16, 730);
    ctx.quadraticCurveTo(x - 6 + Math.sin(s * 6 + i) * 6, 730 - h * 0.6, x + Math.sin(s * 4 + i) * 5, 730 - h);
    ctx.quadraticCurveTo(x + 8, 730 - h * 0.5, x + 16, 730);
    ctx.fill();
  }
  ctx.restore();
  glow(ctx, 290, 690, 230, '255,196,120', 0.55 * f);
  ctx.beginPath();
  ctx.ellipse(300, 380, 90, 48, 0, 0, Math.PI * 2);
  ctx.fillStyle = '#0b0705';
  ctx.fill();
  ctx.fillRect(206, 330, 188, 12);
  plume(ctx, st.warm, s, { x: 300, y: 320, count: 18, life: 4.5, rise: 52, spread: 50, size: 34, alpha: 0.2, seed: 13 });
  // 挂着的炊具
  ctx.fillStyle = '#0a0705';
  ctx.fillRect(600, 140, 420, 8);
  for (let i = 0; i < 5; i += 1) {
    const sw = Math.sin(s * 1.2 + i) * 0.05;
    ctx.save();
    ctx.translate(640 + i * 90, 148);
    ctx.rotate(sw);
    ctx.fillRect(-2, 0, 4, 90 + i * 8);
    ctx.beginPath();
    ctx.ellipse(0, 100 + i * 8, 18, 12, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(${FIRE},${0.25 * f})`;
    ctx.fillRect(-18, 96 + i * 8, 4, 8);
    ctx.fillStyle = '#0a0705';
    ctx.restore();
  }
  // 储藏室的门与水缸
  ctx.fillStyle = '#0a0705';
  ctx.fillRect(1050, 270, 150, 460);
  ctx.fillStyle = '#020101';
  ctx.fillRect(1072, 292, 46, 438);
  ctx.beginPath();
  ctx.moveTo(1268, 520);
  ctx.bezierCurveTo(1230, 620, 1240, 760, 1300, 800);
  ctx.lineTo(1440, 800);
  ctx.bezierCurveTo(1500, 760, 1510, 620, 1472, 520);
  ctx.fillStyle = '#090604';
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(1370, 520, 106, 22, 0, 0, Math.PI * 2);
  ctx.fillStyle = '#0d0907';
  ctx.fill();
  ctx.strokeStyle = `rgba(${FIRE},${0.32 * f})`;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.ellipse(1370, 520, 106, 22, 0, Math.PI * 0.55, Math.PI * 1.25);
  ctx.stroke();
  ctx.fillStyle = `rgba(255,190,120,${0.18 + 0.1 * Math.sin(s * 2)})`;
  ctx.fillRect(1320 + Math.sin(s * 0.8) * 20, 520, 26, 2);
  // 阿芸与周文
  silhouette(ctx, () => standing(ctx, 'ayun', 730, 780, s), FIRE, -3, 0.4 * f);
  silhouette(ctx, () => standing(ctx, 'zhou', 920, 780, s), FIRE, -3, 0.36 * f);
  zhouGlasses(ctx, 920, 780, s, FIRE);
  shade(ctx, 520, 620, 1380, 0.72);
}

/** 审问特写：头肩剪影、一侧轮廓光、背景虚化光斑。 */
function portrait(ctx, s, o, st) {
  const warmth = o.place === 'kitchen' ? FIRE : AMBER;
  vfill(ctx, -300, -300, W + 600, H + 600, [[0, '#070605'], [1, '#120d0a']]);
  const r = prng(21);
  for (let i = 0; i < 18; i += 1) {
    const x = 900 + r() * 900 + Math.sin(s * 0.2 + i) * 20;
    const y = r() * H;
    glow(ctx, x, y, 30 + r() * 70, r() < 0.7 ? warmth : COOL, 0.05 + r() * 0.1);
  }
  glow(ctx, 1320, 200, 820, warmth, 0.22 * flicker(s));
  const breath = 1 + 0.007 * Math.sin(s * 1.6);
  const shape = () => {
    ctx.save();
    ctx.translate(640, 900);
    ctx.scale(breath, breath);
    ctx.translate(-640, -900);
    ctx.moveTo(180, 960);
    ctx.bezierCurveTo(210, 700, 380, 640, 560, 620);
    ctx.lineTo(560, 540);
    ctx.lineTo(720, 540);
    ctx.lineTo(720, 620);
    ctx.bezierCurveTo(900, 640, 1070, 700, 1100, 960);
    ellipsePath(ctx, 640, 420, 132, 164);
    if (o.suspect === 'gu') {
      ellipsePath(ctx, 646, 286, 270, 44);
      ctx.moveTo(522, 290);
      ctx.bezierCurveTo(520, 120, 770, 120, 768, 290);
    } else if (o.suspect === 'ayun') {
      ellipsePath(ctx, 528, 318, 70, 66);
      ctx.moveTo(512, 380);
      ctx.quadraticCurveTo(470, 520, 520, 600);
      ctx.lineTo(540, 590);
      ctx.quadraticCurveTo(500, 500, 530, 390);
    } else {
      ellipsePath(ctx, 640, 300, 134, 60);
    }
    ctx.restore();
  };
  silhouette(ctx, shape, warmth, 9, 0.55 * flicker(s, 0.7));
  if (o.suspect === 'zhou') {
    ctx.strokeStyle = `rgba(${warmth},0.4)`;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(590, 430, 38, 0, Math.PI * 2);
    ctx.moveTo(728, 430);
    ctx.arc(690, 430, 38, 0, Math.PI * 2);
    ctx.moveTo(628, 430);
    ctx.lineTo(652, 430);
    ctx.stroke();
    glow(ctx, 702, 418, 40, '255,240,210', 0.9 * Math.max(0, Math.sin(s * 1.3)) ** 20);
  }
  if (o.suspect === 'gu') {
    const pull = (s % 6) / 6 < 0.3;
    ctx.fillStyle = 'rgba(220,210,200,0.55)';
    ctx.fillRect(716, 514, 92, 6);
    glow(ctx, 810, 517, pull ? 46 : 30, '255,120,50', pull ? 0.9 : 0.6);
    plume(ctx, st.warm, s, { x: 826, y: 506, count: 18, life: 6, rise: 40, spread: 70, size: 40, alpha: 0.16, seed: 17 });
  }
  st.fog.draw(ctx, s, st.warm, { alpha: 0.4, top: 0, bottom: H, drift: 0.3 });
  shade(ctx, 820, 420, 1100, 0.75);
}

function generic(ctx, s, o, st) {
  const f = flicker(s, 0.8);
  vfill(ctx, -300, -300, W + 600, 1060, [[0, '#0b0c0e'], [1, '#17171a']]);
  vfill(ctx, -300, 760, W + 600, 460, [[0, '#0c0c0e'], [1, '#030303']]);
  ctx.fillStyle = '#050506';
  ctx.fillRect(1080, 200, 260, 340);
  ctx.save();
  ctx.beginPath();
  ctx.rect(1098, 218, 224, 304);
  ctx.clip();
  vfill(ctx, 1098, 218, 224, 304, [[0, '#56626d'], [1, '#333c45']]);
  st.fog.draw(ctx, s * 2, st.cool, { alpha: 3.5, top: 200, bottom: 540 });
  ctx.restore();
  ctx.fillRect(1206, 218, 8, 304);
  ctx.strokeStyle = INK;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(560, -300);
  ctx.lineTo(560, 150);
  ctx.stroke();
  poly(ctx, [536, 150, 584, 150, 598, 190, 522, 190], '#0b0a09');
  glow(ctx, 560, 190, 620, AMBER, 0.2 * f);
  st.fog.draw(ctx, s, st.cool, { alpha: 0.9, top: 200, bottom: 900 });
  shade(ctx, 760, 380, 1150, 0.78);
}

const SCENES = {
  black: { draw(ctx) { ctx.fillStyle = '#000'; ctx.fillRect(-300, -300, W + 600, H + 600); }, camera: () => [1, 0, 0] },
  harbor: { draw: harbor, camera: (s) => [1 + 0.14 * ease(s / 18), -110 * ease(s / 18), 20 * ease(s / 18)] },
  ending: { draw: (ctx, s, o, st) => harbor(ctx, s, { ...o, dawn: o.dawn }, st), camera: (s) => [1.12 - 0.1 * ease(s / 16), -60 + 40 * ease(s / 16), 0] },
  lobby: { draw: lobby, camera: (s) => [1.02 + 0.06 * ease(s / 22), -50 * ease(s / 22) + Math.sin(s * 0.3) * 6, Math.sin(s * 0.23) * 4] },
  office: { draw: office, camera: (s) => [1.06, -110 + 220 * ease(s / 24), Math.sin(s * 0.2) * 5] },
  kitchen: { draw: kitchen, camera: (s) => [1.04 + 0.03 * Math.sin(s * 0.12), -40 + Math.sin(s * 0.18) * 30, 0] },
  portrait: { draw: portrait, camera: (s) => [1 + 0.08 * ease(s / 12), 30 * ease(s / 12), -20 * ease(s / 12)] },
  generic: { draw: generic, camera: (s) => [1.03 + 0.03 * ease(s / 20), Math.sin(s * 0.15) * 30, 0] },
};

export class Stage {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.scene = SCENES.black;
    this.options = {};
    this.sceneAt = performance.now();
    this.fadeFrom = 1;
    this.fadeTo = 1;
    this.fadeAt = 0;
    this.fadeMs = 1;
    this.flashAt = -1e9;
    this.res = {
      fog: new Fog(38, 3),
      cool: makeSprite('178,190,202'),
      warm: makeSprite('214,186,150'),
    };
    this.resize();
    new ResizeObserver(() => this.resize()).observe(canvas);
    this.frame = this.frame.bind(this);
    requestAnimationFrame(this.frame);
  }

  resize() {
    const box = this.canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.max(1, Math.round(box.width * dpr));
    this.canvas.height = Math.max(1, Math.round(box.height * dpr));
  }

  /** 切换画面；未知名称使用通用房间。 */
  show(name, options = {}) {
    this.scene = SCENES[name] || SCENES.generic;
    this.options = options;
    this.sceneAt = performance.now();
  }

  level(now = performance.now()) {
    const k = ease((now - this.fadeAt) / this.fadeMs);
    return this.fadeFrom + (this.fadeTo - this.fadeFrom) * k;
  }

  /** 黑场淡入淡出：1 为全黑，0 为完全可见。 */
  fade(to, ms) {
    const now = performance.now();
    this.fadeFrom = this.level(now);
    this.fadeTo = to;
    this.fadeAt = now;
    this.fadeMs = Math.max(1, ms);
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  flash() {
    this.flashAt = performance.now();
  }

  frame(now) {
    const { ctx, canvas } = this;
    const s = (now - this.sceneAt) / 1000;
    const [zoom, dx, dy] = REDUCED ? [1.02, 0, 0] : this.scene.camera(s);
    const k = canvas.width / W;
    ctx.setTransform(k, 0, 0, k, 0, 0);
    ctx.translate(W / 2, H / 2);
    ctx.scale(zoom, zoom);
    ctx.translate(-W / 2 - dx, -H / 2 - dy);
    this.scene.draw(ctx, REDUCED ? s * 0.4 : s, this.options, this.res);
    ctx.setTransform(k, 0, 0, k, 0, 0);
    const flash = Math.max(0, 1 - (now - this.flashAt) / 700);
    if (flash > 0) {
      ctx.fillStyle = `rgba(255,236,200,${0.16 * flash})`;
      ctx.fillRect(0, 0, W, H);
    }
    const dark = this.level(now);
    if (dark > 0) {
      ctx.fillStyle = `rgba(0,0,0,${dark})`;
      ctx.fillRect(0, 0, W, H);
    }
    requestAnimationFrame(this.frame);
  }
}
