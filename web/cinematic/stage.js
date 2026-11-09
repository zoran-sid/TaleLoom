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

/** 光里的浮尘：place(u, v) 把两个 0–1 的随机数映射到光束内的位置。 */
function motes(ctx, t, count, place, rgb, seed) {
  const r = prng(seed);
  for (let i = 0; i < count; i += 1) {
    const u = (r() + t * 0.008 * (0.5 + r())) % 1;
    const v = r();
    const [x, y] = place(u, v);
    ctx.fillStyle = `rgba(${rgb},${0.15 + 0.35 * Math.abs(Math.sin(t * 0.9 + i))})`;
    ctx.fillRect(x + Math.sin(t * 0.7 + i) * 6, y + Math.cos(t * 0.5 + i) * 6, 2.2, 2.2);
  }
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

/** 一条小船：船身、船舱、桅杆；lamp 为船头灯笼的亮度（0 为不点灯）。 */
function boat(ctx, x, y, k, color, lamp, t) {
  const bob = Math.sin(t * 1.4) * 3 * k;
  ctx.save();
  ctx.translate(x, y + bob);
  ctx.scale(k, k);
  poly(ctx, [-110, 0, 110, 0, 86, 30, -86, 30], color);
  ctx.fillStyle = color;
  ctx.fillRect(-40, -46, 70, 46);
  ctx.fillRect(-4, -120, 5, 120);
  poly(ctx, [1, -120, 40, -110, 1, -100], color);
  ctx.restore();
  ctx.fillStyle = `rgba(${COOL},0.12)`;
  ctx.fillRect(x - 100 * k, y + 34 * k + bob, 200 * k, 2);
  if (lamp > 0) {
    glow(ctx, x + 100 * k, y - 10 * k + bob, 70 * k, AMBER, 0.7 * lamp);
    glow(ctx, x + 100 * k, y + 40 * k, 40 * k, AMBER, 0.2 * lamp);
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
  if (o.storm) {
    ctx.strokeStyle = 'rgba(190,205,220,0.28)';
    ctx.lineWidth = 3;
    for (let row = 0; row < 7; row += 1) {
      const base = 590 + row * 52;
      ctx.beginPath();
      for (let x = -300; x <= W + 300; x += 20) {
        const y = base + Math.sin(x * 0.012 + s * (1.7 + row * 0.25) + row) * (14 + row * 7) + Math.sin(x * 0.031 - s * 2.4) * 6;
        if (x === -300) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    plume(ctx, st.cool, s, { x: 760, y: 600, count: 30, life: 1.8, rise: 120, spread: 160, ySpread: 40, size: 50, alpha: 0.25, seed: 41 });
  }
  ctx.fillStyle = INK;
  for (let x = 660; x < 1060; x += 46) ctx.fillRect(x, 560, 7, 70 + Math.sin(x) * 8);
  ctx.fillRect(640, 556, 430, 8);
  if (o.boat === 'arrive') {
    const t = ease(s / 16);
    boat(ctx, 1780 - 820 * t, 586, 1.1, mix('#0a0d11', '#2c3237', dawn), 0, s);
  } else if (o.boat === 'leave') {
    const t = clamp01(s / 18);
    boat(ctx, 780 + 820 * t, 584 - 14 * t, 0.9 - 0.45 * t, '#06080b', 1 - 0.7 * t, s);
  }
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
  for (let i = 0; i < 3; i += 1) {
    const a = s * (1.9 + i * 0.45) + i * 2.1;
    const radius = 70 + 26 * Math.sin(s * 1.3 + i);
    const mx = 800 + Math.cos(a) * radius;
    const my = 168 + Math.sin(a) * radius * 0.55;
    const flap = 0.35 + 0.65 * Math.abs(Math.sin(s * 28 + i));
    ctx.fillStyle = 'rgba(235,214,170,0.75)';
    ctx.beginPath();
    ctx.ellipse(mx - 4, my, 5, 3.5 * flap, -0.4, 0, Math.PI * 2);
    ctx.ellipse(mx + 4, my, 5, 3.5 * flap, 0.4, 0, Math.PI * 2);
    ctx.fill();
  }
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
  motes(ctx, s, 55, (u, v) => [1180 - 640 * u + (v - 0.5) * 260 * (0.4 + u), 260 + 640 * u], COOL, 51);
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
  const mood = o.mood || '';
  const breath = 1 + (mood === 'cold' ? 0.004 : 0.007) * Math.sin(s * (mood === 'nervous' ? 2.6 : 1.6));
  const shiver = mood === 'nervous' ? Math.sin(s * 29) * 1.6 : 0;
  const shape = () => {
    ctx.save();
    ctx.translate(shiver, 0);
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
  if (mood === 'nervous') {
    for (const [x, y, ph] of [[742, 372, 0], [548, 388, 2.4]]) {
      const k = Math.max(0, Math.sin(s * 0.9 + ph)) ** 6;
      glow(ctx, x + shiver, y + 40 * ((s * 0.15 + ph) % 1), 10, '255,240,220', 0.9 * k);
    }
  } else if (mood === 'tears') {
    for (const [x, ph] of [[598, 0], [684, 1.7]]) {
      const k = ((s * 0.33 + ph) % 1);
      glow(ctx, x, 452 + 120 * k, 9, '235,240,255', 0.85 * Math.sin(Math.PI * k));
    }
  }
  if (o.suspect === 'gu' && mood !== 'cold') {
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

function guestroom(ctx, s, o, st) {
  const f = flicker(s, 0.7);
  vfill(ctx, -300, -300, W + 600, 1020, [[0, '#110f0d'], [1, '#221b15']]);
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  for (let x = -280; x < W + 300; x += 46) ctx.fillRect(x, -300, 18, 1020);
  vfill(ctx, -300, 720, W + 600, 500, [[0, '#17110c'], [1, '#050403']]);
  ctx.strokeStyle = 'rgba(0,0,0,0.35)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < 9; i += 1) { const y = 728 + i * i * 4 + i * 6; ctx.moveTo(-300, y); ctx.lineTo(W + 300, y); }
  ctx.stroke();
  // 雨夜的窗：雾在外面流，雨滴顺着玻璃往下滑
  ctx.fillStyle = '#060708';
  ctx.fillRect(1180, 170, 280, 360);
  ctx.save();
  ctx.beginPath();
  ctx.rect(1198, 188, 244, 324);
  ctx.clip();
  vfill(ctx, 1198, 188, 244, 324, [[0, '#2b3542'], [1, '#18202a']]);
  st.fog.draw(ctx, s * 1.8, st.cool, { alpha: 2.6, top: 180, bottom: 520 });
  const r = prng(31);
  ctx.strokeStyle = 'rgba(190,205,220,0.4)';
  ctx.lineWidth = 2;
  for (let i = 0; i < 28; i += 1) {
    const x = 1200 + r() * 240;
    const speed = 40 + r() * 90;
    const y = 188 + ((s * speed + r() * 400) % 340);
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + 1, y + 10 + r() * 14);
    ctx.stroke();
  }
  ctx.restore();
  ctx.fillStyle = '#060708';
  ctx.fillRect(1316, 188, 8, 324);
  ctx.fillRect(1198, 346, 244, 8);
  // 床
  ctx.fillStyle = '#0c0907';
  ctx.fillRect(50, 420, 36, 340);
  poly(ctx, [60, 560, 560, 560, 584, 652, 40, 652], '#1b1612');
  poly(ctx, [100, 554, 540, 554, 556, 600, 90, 600], 'rgba(205,195,175,0.12)');
  ctx.fillStyle = 'rgba(215,205,185,0.15)';
  ctx.beginPath();
  ctx.ellipse(160, 548, 62, 16, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#0b0806';
  ctx.fillRect(40, 652, 544, 28);
  ctx.fillRect(56, 680, 14, 80);
  ctx.fillRect(552, 680, 14, 80);
  // 床头灯
  ctx.fillRect(612, 560, 110, 200);
  ctx.fillRect(660, 500, 8, 60);
  poly(ctx, [628, 500, 700, 500, 688, 462, 640, 462], `rgba(${AMBER},${0.5 * f})`);
  glow(ctx, 664, 492, 440, AMBER, 0.22 * f);
  glow(ctx, 664, 492, 60, '255,222,170', 0.6 * f);
  // 椅子和搭着的湿外套
  ctx.fillStyle = '#0a0806';
  ctx.fillRect(900, 430, 110, 210);
  ctx.fillRect(880, 620, 160, 22);
  ctx.fillRect(888, 640, 12, 120);
  ctx.fillRect(1020, 640, 12, 120);
  ctx.beginPath();
  ctx.moveTo(896, 436);
  ctx.quadraticCurveTo(955, 412, 1014, 436);
  ctx.lineTo(1034, 700);
  ctx.lineTo(1012, 692);
  ctx.lineTo(992, 706);
  ctx.lineTo(964, 694);
  ctx.lineTo(938, 708);
  ctx.lineTo(912, 694);
  ctx.lineTo(886, 702);
  ctx.closePath();
  ctx.fillStyle = '#040405';
  ctx.fill();
  ctx.strokeStyle = `rgba(${AMBER},${0.3 * f})`;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(896, 436);
  ctx.lineTo(886, 702);
  ctx.stroke();
  // 衣摆滴水，地上一圈圈水纹
  ctx.fillStyle = 'rgba(150,170,190,0.12)';
  ctx.beginPath();
  ctx.ellipse(962, 772, 130, 14, 0, 0, Math.PI * 2);
  ctx.fill();
  for (const [x, ph] of [[914, 0], [964, 0.45], [1012, 0.8]]) {
    const k = (s * 0.7 + ph) % 1;
    if (k < 0.6) {
      const y = 706 + 66 * (k / 0.6) ** 2;
      ctx.fillStyle = 'rgba(200,215,230,0.7)';
      ctx.beginPath();
      ctx.ellipse(x, y, 2.5, 4, 0, 0, Math.PI * 2);
      ctx.fill();
    } else {
      const ring = (k - 0.6) / 0.4;
      ctx.strokeStyle = `rgba(200,215,230,${0.5 * (1 - ring)})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.ellipse(x, 772, 4 + 30 * ring, 2 + 5 * ring, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  // 从窗边一路走到椅子的湿脚印
  for (let i = 0; i < 8; i += 1) {
    const u = i / 7;
    const x = 1250 - 230 * u + (i % 2 ? 14 : -14);
    const y = 900 - 110 * u;
    ctx.fillStyle = 'rgba(150,170,190,0.14)';
    ctx.beginPath();
    ctx.ellipse(x, y, 16 - 5 * u, 7 - 2 * u, -0.4, 0, Math.PI * 2);
    ctx.fill();
    glow(ctx, x - 4, y - 2, 6, '210,225,240', 0.35 * Math.abs(Math.sin(s * 0.8 + i)));
  }
  st.fog.draw(ctx, s, st.warm, { alpha: 0.3, top: 300, bottom: 800, drift: 0.2 });
  shade(ctx, 760, 520, 1200, 0.72);
}

function backyard(ctx, s, o, st) {
  vfill(ctx, -300, -300, W + 600, 900, [[0, '#03050a'], [1, '#131b24']]);
  vfill(ctx, 900, 560, W + 400, 500, [[0, '#0b1118'], [1, '#03050a']]);
  const r = prng(61);
  for (let i = 0; i < 40; i += 1) {
    const x = 980 + r() * 900 + Math.sin(s * 0.6 + i) * 8;
    const y = 570 + r() * 260;
    ctx.fillStyle = `rgba(${COOL},${0.04 + 0.06 * Math.sin(s * 1.2 + i) ** 2})`;
    ctx.fillRect(x, y, 20 + r() * 60, 1.6);
  }
  // 旅馆后墙、账房的窗、后门、墙上的风灯
  ctx.fillStyle = '#0b0b0d';
  ctx.fillRect(-300, 120, 1280, 600);
  ctx.strokeStyle = 'rgba(0,0,0,0.4)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let y = 140; y < 720; y += 30) {
    ctx.moveTo(-300, y);
    ctx.lineTo(980, y);
    for (let x = (y / 30) % 2 ? -300 : -260; x < 980; x += 80) { ctx.moveTo(x, y); ctx.lineTo(x, y + 30); }
  }
  ctx.stroke();
  vfill(ctx, 300, 300, 170, 170, [[0, '#5d6a77'], [1, '#3a4550']]);
  ctx.fillStyle = '#0b0b0d';
  ctx.fillRect(381, 300, 8, 170);
  ctx.fillRect(300, 381, 170, 8);
  glow(ctx, 385, 385, 240, COOL, 0.12);
  ctx.fillStyle = '#050405';
  ctx.fillRect(640, 430, 120, 290);
  const f = flicker(s, 0.9);
  ctx.fillStyle = `rgba(${AMBER},${0.55 * f})`;
  ctx.fillRect(752, 432, 5, 286);
  poly(ctx, [757, 720, 762, 720, 900, 960, 820, 960], `rgba(${AMBER},${0.08 * f})`);
  ctx.save();
  ctx.translate(820, 380);
  ctx.rotate(Math.sin(s * 1.3) * 0.14);
  ctx.fillStyle = '#060505';
  ctx.fillRect(-2, 0, 4, 34);
  ctx.fillRect(-14, 34, 28, 36);
  glow(ctx, 0, 52, 160, AMBER, 0.32 * f);
  glow(ctx, 0, 52, 22, '255,220,160', 0.8 * f);
  ctx.restore();
  // 泥地与通往码头的石阶
  vfill(ctx, -300, 710, W + 600, 500, [[0, '#0d0c0a'], [1, '#040303']]);
  for (let i = 0; i < 8; i += 1) {
    const x = 1000 + i * 80;
    const y = 716 + i * 26;
    poly(ctx, [x, y, x + 600, y, x + 600, y + 26, x, y + 26], i % 2 ? '#0c0d0f' : '#101215');
    ctx.fillStyle = 'rgba(150,170,190,0.12)';
    ctx.fillRect(x, y, 600, 2);
  }
  // 两行脚印：皮鞋印从石阶走到窗下，布鞋印从后门走向码头，依次显现
  const trails = [
    { from: [1180, 860], to: [430, 760], n: 10, size: [17, 7] },
    { from: [710, 770], to: [1120, 830], n: 8, size: [11, 5] },
  ];
  trails.forEach((trail, tIndex) => {
    for (let i = 0; i < trail.n; i += 1) {
      const u = i / (trail.n - 1);
      const appear = clamp01((s * 0.9 - i * 0.35 - tIndex * 2) / 0.8);
      if (appear <= 0) continue;
      const x = trail.from[0] + (trail.to[0] - trail.from[0]) * u + (i % 2 ? 10 : -10);
      const y = trail.from[1] + (trail.to[1] - trail.from[1]) * u;
      ctx.fillStyle = `rgba(4,4,4,${0.85 * appear})`;
      ctx.beginPath();
      ctx.ellipse(x, y, trail.size[0], trail.size[1], tIndex ? 0.3 : -0.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = `rgba(150,170,190,${0.18 * appear})`;
      ctx.fillRect(x - 4, y - 2, 6, 1.5);
    }
  });
  st.fog.draw(ctx, s, st.cool, { alpha: 2.1, top: 300, bottom: 900, drift: 0.8 });
  shade(ctx, 760, 520, 1250, 0.66);
}

function zhouroom(ctx, s, o, st) {
  vfill(ctx, -300, -300, W + 600, 1000, [[0, '#0b0c0d'], [1, '#18191b']]);
  vfill(ctx, -300, 700, W + 600, 520, [[0, '#0f0c0a'], [1, '#040303']]);
  // 书架与一摞摞账本
  ctx.fillStyle = '#070606';
  ctx.fillRect(80, 160, 320, 560);
  const r = prng(71);
  for (let row = 0; row < 4; row += 1) {
    ctx.fillStyle = '#0d0b0a';
    ctx.fillRect(80, 290 + row * 130, 320, 10);
    for (let x = 96; x < 384;) {
      const w = 14 + r() * 18;
      const h = 70 + r() * 40;
      ctx.fillStyle = `rgba(${90 + r() * 60},${40 + r() * 30},${30 + r() * 20},0.35)`;
      ctx.fillRect(x, 290 + row * 130 - h, w - 3, h);
      x += w;
    }
  }
  // 书桌：算盘、眼镜盒、砚台
  ctx.fillStyle = '#080706';
  ctx.fillRect(980, 520, 440, 26);
  ctx.fillRect(1000, 546, 16, 214);
  ctx.fillRect(1384, 546, 16, 214);
  ctx.strokeStyle = 'rgba(60,45,35,0.9)';
  ctx.lineWidth = 6;
  ctx.strokeRect(1040, 480, 180, 40);
  for (let i = 0; i < 9; i += 1) {
    for (let j = 0; j < 3; j += 1) {
      ctx.fillStyle = '#1a1310';
      ctx.beginPath();
      ctx.ellipse(1058 + i * 19, 490 + j * 11, 6, 4, 0, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.fillStyle = '#120f0d';
  ctx.fillRect(1260, 500, 70, 20);
  glow(ctx, 1290, 506, 14, '255,240,210', 0.5 * Math.max(0, Math.sin(s * 1.1)) ** 12);
  // 我们手里的灯：一道暖光在地板上扫过
  const cx = 700 + Math.sin(s * 0.45) * 220;
  const cone = ctx.createLinearGradient(200, 1000, cx, 760);
  cone.addColorStop(0, `rgba(${AMBER},0.02)`);
  cone.addColorStop(1, `rgba(${AMBER},0.2)`);
  poly(ctx, [200, 1000, cx - 190, 740, cx + 190, 740, 360, 1000], cone);
  glow(ctx, cx, 770, 220, AMBER, 0.2);
  // 松动的地板：撬开后露出藏着的暗账
  if (o.open) {
    poly(ctx, [600, 790, 900, 790, 900, 812, 600, 812], '#010101');
    ctx.save();
    ctx.translate(600, 790);
    ctx.rotate(-0.32);
    ctx.fillStyle = '#2a1f17';
    ctx.fillRect(0, -18, 300, 18);
    ctx.restore();
    poly(ctx, [690, 796, 800, 796, 806, 808, 684, 808], 'rgba(210,200,180,0.35)');
    glow(ctx, 750, 800, 30, '255,235,200', 0.4 + 0.3 * Math.sin(s * 2));
  } else {
    ctx.fillStyle = 'rgba(70,52,38,0.4)';
    ctx.fillRect(600, 790, 300, 20);
  }
  motes(ctx, s, 40, (u, v) => [cx - 180 + 360 * v, 760 - 260 * u], AMBER, 73);
  shade(ctx, cx, 640, 1200, 0.78);
}

function attic(ctx, s, o, st) {
  const f = flicker(s, 1.8);
  if (o.closed) {
    // 闩上的阁楼门外：门缝下的烛光里，有人影在晃
    vfill(ctx, -300, -300, W + 600, 1100, [[0, '#0d0a08'], [1, '#1b140f']]);
    ctx.fillStyle = '#120d09';
    ctx.fillRect(600, 140, 400, 690);
    ctx.strokeStyle = 'rgba(0,0,0,0.5)';
    ctx.lineWidth = 6;
    ctx.strokeRect(640, 190, 320, 260);
    ctx.strokeRect(640, 500, 320, 280);
    const sway = Math.sin(s * 0.8) * 60;
    const strip = ctx.createLinearGradient(600, 0, 1000, 0);
    strip.addColorStop(0, `rgba(${AMBER},${0.6 * f})`);
    strip.addColorStop(clamp01(0.45 + sway / 400), 'rgba(0,0,0,0.6)');
    strip.addColorStop(clamp01(0.62 + sway / 400), `rgba(${AMBER},${0.6 * f})`);
    strip.addColorStop(1, `rgba(${AMBER},${0.6 * f})`);
    ctx.fillStyle = strip;
    ctx.fillRect(604, 826, 392, 6);
    poly(ctx, [604, 832, 996, 832, 1120, 960, 480, 960], `rgba(${AMBER},${0.07 * f})`);
    glow(ctx, 940, 480, 6, AMBER, 0.8 * f);
    shade(ctx, 800, 700, 1100, 0.8);
    return;
  }
  vfill(ctx, -300, -300, W + 600, 1100, [[0, '#120d0a'], [1, '#24190f']]);
  poly(ctx, [-300, -300, W + 300, -300, W + 300, 90, 880, 90, -300, 560], '#070504');
  ctx.strokeStyle = 'rgba(0,0,0,0.6)';
  ctx.lineWidth = 10;
  ctx.beginPath();
  for (let i = 0; i < 5; i += 1) { ctx.moveTo(880 + i * 180, 90); ctx.lineTo(880 + i * 180 - 400, -300); }
  ctx.stroke();
  // 圆窗里的雾光
  ctx.save();
  ctx.beginPath();
  ctx.arc(1200, 300, 90, 0, Math.PI * 2);
  ctx.clip();
  vfill(ctx, 1110, 210, 180, 180, [[0, '#56636f'], [1, '#2f3842']]);
  st.fog.draw(ctx, s * 2, st.cool, { alpha: 3, top: 200, bottom: 400 });
  ctx.restore();
  ctx.strokeStyle = '#070504';
  ctx.lineWidth = 10;
  ctx.beginPath();
  ctx.arc(1200, 300, 90, 0, Math.PI * 2);
  ctx.moveTo(1110, 300); ctx.lineTo(1290, 300);
  ctx.moveTo(1200, 210); ctx.lineTo(1200, 390);
  ctx.stroke();
  vfill(ctx, -300, 760, W + 600, 400, [[0, '#120c08'], [1, '#040302']]);
  // 窄床、木盒、小桌、蜡烛
  poly(ctx, [100, 640, 620, 640, 640, 700, 80, 700], '#1a130e');
  poly(ctx, [120, 630, 600, 630, 610, 660, 110, 660], 'rgba(200,180,150,0.1)');
  ctx.fillStyle = '#0b0806';
  ctx.fillRect(80, 700, 560, 24);
  ctx.fillStyle = '#2a1c12';
  ctx.fillRect(240, 592, 90, 44);
  ctx.fillStyle = '#3a2716';
  ctx.fillRect(236, 584, 98, 12);
  glow(ctx, 322, 588, 12, '255,230,180', 0.8 * Math.max(0, Math.sin(s * 0.9)) ** 10);
  ctx.fillStyle = '#0b0806';
  ctx.fillRect(900, 600, 240, 20);
  ctx.fillRect(916, 620, 14, 140);
  ctx.fillRect(1110, 620, 14, 140);
  poly(ctx, [1040, 592, 1100, 590, 1104, 600, 1044, 602], 'rgba(220,210,190,0.3)');
  ctx.fillStyle = 'rgba(230,220,200,0.55)';
  ctx.fillRect(970, 560, 12, 40);
  const lean = Math.sin(s * 3.1) * 3 + Math.sin(s * 7.3) * 1.5;
  ctx.beginPath();
  ctx.moveTo(970, 560);
  ctx.quadraticCurveTo(968 + lean, 540, 976 + lean, 524);
  ctx.quadraticCurveTo(984 + lean, 540, 982, 560);
  ctx.fillStyle = `rgba(255,200,120,${0.9 * f})`;
  ctx.fill();
  glow(ctx, 976, 540, 520, AMBER, 0.3 * f);
  glow(ctx, 976, 540, 40, '255,236,190', 0.8 * f);
  shade(ctx, 900, 520, 1150, 0.78);
}

function doorway(ctx, s, o, st) {
  // 失败：撬地板时，门被推开，周文站在走廊的灯光里
  zhouroom(ctx, s, { open: true }, st);
  const open = ease(s / 3);
  const left = 1340 - 240 * open;
  poly(ctx, [left, 120, 1340, 120, 1340, 820, left, 820], `rgba(${AMBER},${0.55})`);
  poly(ctx, [left, 820, 1340, 820, 1340 + 260 * open, 1000, left - 420 * open, 1000], `rgba(${AMBER},${0.14 * open})`);
  ctx.save();
  ctx.translate(1240, 820);
  ctx.scale(1.55, 1.55);
  ctx.translate(-1240, -820);
  ctx.beginPath();
  standing(ctx, 'zhou', 1240, 820, s);
  ctx.fillStyle = INK;
  ctx.globalAlpha = open;
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.restore();
  glow(ctx, 1290, 560, 26, '255,230,170', open * (0.6 + 0.4 * Math.sin(s * 5)));
  shade(ctx, 1200, 500, 1300, 0.6);
}

function storeroom(ctx, s, o, st) {
  // 失败：被反锁在储藏室，门在撞击下震动，灰尘簌簌往下落
  vfill(ctx, -300, -300, W + 600, 1100, [[0, '#0a0806'], [1, '#160f0a']]);
  vfill(ctx, -300, 780, W + 600, 400, [[0, '#0d0907'], [1, '#030202']]);
  const r = prng(81);
  for (const sx of [80, 1140]) {
    ctx.fillStyle = '#060504';
    ctx.fillRect(sx, 160, 380, 620);
    for (let row = 0; row < 4; row += 1) {
      ctx.fillStyle = '#0d0907';
      ctx.fillRect(sx, 300 + row * 140, 380, 10);
      for (let x = sx + 20; x < sx + 360; x += 40 + r() * 20) {
        poly(ctx, [x, 300 + row * 140, x + 22, 300 + row * 140, x + 18, 240 + row * 140, x + 14, 220 + row * 140, x + 8, 220 + row * 140, x + 4, 240 + row * 140], 'rgba(40,52,40,0.55)');
      }
    }
  }
  const burst = (s % 3.2) < 0.9;
  const knock = burst ? Math.sin(s * 40) * 4 : 0;
  ctx.fillStyle = '#100b08';
  ctx.fillRect(620 + knock, 200, 360, 600);
  ctx.strokeStyle = 'rgba(0,0,0,0.5)';
  ctx.lineWidth = 6;
  ctx.strokeRect(660 + knock, 250, 280, 230);
  ctx.strokeRect(660 + knock, 520, 280, 240);
  ctx.fillStyle = `rgba(${AMBER},0.6)`;
  ctx.fillRect(624, 798, 352, 5);
  poly(ctx, [624, 803, 976, 803, 1100, 960, 500, 960], `rgba(${AMBER},0.08)`);
  plume(ctx, st.warm, s, { x: 800, y: 210, count: 26, life: 2.6, rise: -60, spread: 300, ySpread: 20, size: 8, alpha: burst ? 0.5 : 0.2, seed: 83 });
  shade(ctx, 800, 600, 1100, 0.78);
}

// ---------- 飞船（《深空回声》） ----------

const RED = '255,64,52';
const CYAN = '90,200,224';

function stars(ctx, t, seed, count, area) {
  const r = prng(seed);
  for (let i = 0; i < count; i += 1) {
    const x = area[0] + r() * area[2];
    const y = area[1] + r() * area[3];
    const tw = 0.35 + 0.65 * Math.abs(Math.sin(t * (0.4 + r()) + i));
    ctx.fillStyle = `rgba(230,236,255,${(0.25 + r() * 0.6) * tw})`;
    const size = r() < 0.08 ? 2.4 : 1.4;
    ctx.fillRect(x, y, size, size);
  }
}

function panels(ctx, top, bottom, light) {
  vfill(ctx, -300, top, W + 600, bottom - top, [[0, '#0b1014'], [1, '#182128']]);
  ctx.strokeStyle = `rgba(${light},0.07)`;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let x = -280; x < W + 300; x += 160) { ctx.moveTo(x, top); ctx.lineTo(x, bottom); }
  for (let y = top + 90; y < bottom; y += 140) { ctx.moveTo(-300, y); ctx.lineTo(W + 300, y); }
  ctx.stroke();
}

/** 旋转的红色警报灯：光束扫过，整间舱室随之泛红。 */
function alarm(ctx, x, y, t, strength) {
  if (strength <= 0) return;
  const a = t * 2.4;
  for (const angle of [a, a + Math.PI]) {
    const c = Math.cos(angle);
    const g = ctx.createLinearGradient(x, y, x + 900 * c, y + 400);
    g.addColorStop(0, `rgba(${RED},${0.32 * strength * Math.abs(c)})`);
    g.addColorStop(1, `rgba(${RED},0)`);
    poly(ctx, [x, y, x + 900 * c - 160, y + 520, x + 900 * c + 160, y + 520], g);
  }
  glow(ctx, x, y, 60, RED, 0.9 * strength);
  ctx.fillStyle = `rgba(${RED},${0.08 * strength * (0.6 + 0.4 * Math.sin(t * 4.8))})`;
  ctx.fillRect(-300, -300, W + 600, H + 600);
}

function bay(ctx, s, o, st) {
  const power = o.dying ? 1 - ease(s / 9) : 1;
  panels(ctx, -300, 760, CYAN);
  vfill(ctx, -300, 760, W + 600, 460, [[0, '#10161b'], [1, '#040506']]);
  ctx.fillStyle = '#070a0c';
  ctx.fillRect(-300, 40, W + 600, 26);
  ctx.fillRect(-300, 90, W + 600, 14);
  for (let i = 0; i < 4; i += 1) {
    const x = 160 + i * 360;
    const open = i === 1;
    ctx.fillStyle = '#0a0e11';
    ctx.beginPath();
    ctx.roundRect(x, 260, 240, 470, 110);
    ctx.fill();
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(x + 36, 300, 168, 300, 80);
    ctx.clip();
    vfill(ctx, x + 36, 300, 168, 300, [[0, `rgba(${CYAN},${(open ? 0.08 : 0.32) * power})`], [1, `rgba(${CYAN},${(open ? 0.03 : 0.14) * power})`]]);
    if (!open) {
      ctx.fillStyle = 'rgba(4,6,8,0.85)';
      ctx.beginPath();
      ctx.ellipse(x + 120, 380, 34, 42, 0, 0, Math.PI * 2);
      ctx.ellipse(x + 120, 520, 60, 110, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
    if (open) {
      ctx.save();
      ctx.translate(x + 204, 300);
      ctx.rotate(0.5);
      ctx.fillStyle = 'rgba(120,170,190,0.18)';
      ctx.beginPath();
      ctx.roundRect(0, 0, 168, 300, 80);
      ctx.fill();
      ctx.restore();
    }
    glow(ctx, x + 120, 740, 120, CYAN, 0.12 * power);
    ctx.fillStyle = `rgba(${i === 1 ? RED : CYAN},${0.8 * power * (0.5 + 0.5 * Math.sin(s * 3 + i))})`;
    ctx.fillRect(x + 110, 640, 20, 8);
  }
  motes(ctx, s, 50, (u, v) => [260 + 1100 * v, 280 + 440 * u], CYAN, 91);
  alarm(ctx, 800, 70, s, power);
  shade(ctx, 800, 440, 1150, 0.62 + 0.3 * (1 - power));
}

function corridor(ctx, s, o, st) {
  const vx = 800;
  const vy = 430;
  const lit = o.dark ? 0.12 : 1;
  vfill(ctx, -300, -300, W + 600, H + 600, [[0, '#06090b'], [1, '#0d1317']]);
  poly(ctx, [-300, -300, W + 300, -300, vx + 90, vy - 70, vx - 90, vy - 70], '#0a0e11');
  poly(ctx, [-300, H + 300, W + 300, H + 300, vx + 90, vy + 70, vx - 90, vy + 70], '#0c1013');
  poly(ctx, [-300, -300, vx - 90, vy - 70, vx - 90, vy + 70, -300, H + 300], '#0e1418');
  poly(ctx, [W + 300, -300, vx + 90, vy - 70, vx + 90, vy + 70, W + 300, H + 300], '#0e1418');
  const ribs = 9;
  const head = Math.floor(s * 5) % (ribs + 4);
  for (let i = 0; i < ribs; i += 1) {
    const k = 1 - i / ribs;
    const d = k ** 1.8;
    const hw = 90 + 1000 * d;
    const hh = 70 + 760 * d;
    ctx.strokeStyle = 'rgba(30,40,48,0.9)';
    ctx.lineWidth = 6 + 18 * d;
    ctx.strokeRect(vx - hw, vy - hh, hw * 2, hh * 2);
    const on = (i === head || i === head - 1 ? 1 : 0.25) * lit;
    glow(ctx, vx, vy - hh + 6, 60 + 220 * d, RED, 0.45 * on);
    ctx.fillStyle = `rgba(${RED},${0.9 * on})`;
    ctx.fillRect(vx - 30 * (0.3 + d), vy - hh, 60 * (0.3 + d), 6 + 6 * d);
  }
  if (!o.dark) {
    const signs = [['工具间', -1, 0.55], ['能源舱', 1, 0.55], ['通信室', -1, 0.3], ['气闸', 1, 0.3]];
    ctx.textAlign = 'center';
    for (const [label, side, d] of signs) {
      const x = vx + side * (90 + 1000 * d * d * 0.9);
      const y = vy - 30;
      ctx.font = `600 ${Math.round(14 + 30 * d)}px "PingFang SC","Noto Sans CJK SC",sans-serif`;
      ctx.fillStyle = `rgba(${CYAN},${0.55 + 0.2 * Math.sin(s * 2 + d * 10)})`;
      ctx.fillText(label, x, y);
    }
  }
  motes(ctx, s, 40, (u, v) => [vx - 500 + 1000 * v, vy - 300 + 600 * u], CYAN, 93);
  shade(ctx, vx, vy, 1150, 0.55 + 0.35 * (1 - lit));
}

function toolroom(ctx, s, o, st) {
  const f = flicker(s, 2.2) * (Math.sin(s * 0.7) > 0.93 ? 0.35 : 1);
  panels(ctx, -300, 740, CYAN);
  vfill(ctx, -300, 740, W + 600, 460, [[0, '#121518'], [1, '#040506']]);
  ctx.fillStyle = '#0c1013';
  ctx.fillRect(120, 140, 760, 420);
  ctx.fillStyle = 'rgba(90,110,120,0.18)';
  for (let x = 150; x < 860; x += 30) for (let y = 170; y < 540; y += 30) ctx.fillRect(x, y, 3, 3);
  ctx.fillStyle = '#05070a';
  ctx.save(); ctx.translate(240, 220); ctx.rotate(0.3); ctx.fillRect(-8, 0, 16, 200); ctx.beginPath(); ctx.arc(0, 0, 30, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  ctx.fillRect(400, 200, 22, 220); ctx.fillRect(360, 190, 100, 40);
  ctx.save(); ctx.translate(640, 230); ctx.rotate(-0.4); ctx.fillRect(-10, 0, 20, 230); ctx.restore();
  ctx.fillStyle = '#0a0d10';
  ctx.fillRect(80, 600, 900, 40);
  ctx.fillRect(110, 640, 30, 120);
  ctx.fillRect(920, 640, 30, 120);
  ctx.fillStyle = '#10181d';
  ctx.beginPath();
  ctx.roundRect(1100, 360, 150, 400, 70);
  ctx.fill();
  ctx.fillStyle = `rgba(${CYAN},0.55)`;
  ctx.fillRect(1120, 520, 110, 40);
  ctx.fillStyle = 'rgba(4,8,10,0.9)';
  ctx.font = '600 22px "PingFang SC",sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('O₂', 1175, 548);
  glow(ctx, 1175, 540, 160, CYAN, 0.15);
  // 断裂的配电板：时不时迸出火花
  ctx.fillStyle = '#070909';
  ctx.fillRect(1340, 220, 180, 240);
  const burst = (s % 2.7) < 0.5;
  if (burst) {
    glow(ctx, 1430, 300, 140, '255,200,120', 0.6);
    const r = prng(Math.floor(s / 2.7) + 7);
    for (let i = 0; i < 16; i += 1) {
      const age = (s % 2.7) / 0.5;
      const vxp = (r() - 0.5) * 300;
      const vyp = -r() * 160;
      ctx.fillStyle = `rgba(255,220,140,${1 - age})`;
      ctx.fillRect(1430 + vxp * age, 300 + vyp * age + 400 * age * age, 3, 3);
    }
  }
  glow(ctx, 800, 60, 700, '200,220,230', 0.16 * f);
  shade(ctx, 800, 420, 1150, 0.62);
}

function airlock(ctx, s, o, st) {
  panels(ctx, -300, 780, CYAN);
  vfill(ctx, -300, 780, W + 600, 420, [[0, '#101418'], [1, '#040506']]);
  ctx.save();
  ctx.beginPath();
  ctx.rect(470, 120, 660, 660);
  ctx.clip();
  for (let i = -12; i < 20; i += 1) {
    poly(ctx, [470 + i * 60, 120, 500 + i * 60, 120, 500 + i * 60 - 660, 780, 470 + i * 60 - 660, 780], i % 2 ? 'rgba(210,170,40,0.5)' : 'rgba(10,10,10,0.8)');
  }
  ctx.restore();
  ctx.fillStyle = '#0d1216';
  ctx.beginPath();
  ctx.arc(800, 450, 290, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = 'rgba(120,140,150,0.35)';
  for (const [r, w] of [[290, 10], [230, 6], [150, 4]]) {
    ctx.lineWidth = w;
    ctx.beginPath();
    ctx.arc(800, 450, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  for (let i = 0; i < 12; i += 1) {
    const a = (i / 12) * Math.PI * 2;
    ctx.fillStyle = 'rgba(150,165,175,0.5)';
    ctx.beginPath();
    ctx.arc(800 + Math.cos(a) * 262, 450 + Math.sin(a) * 262, 8, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.save();
  ctx.beginPath();
  ctx.arc(800, 450, 100, 0, Math.PI * 2);
  ctx.clip();
  ctx.fillStyle = '#020306';
  ctx.fillRect(700, 350, 200, 200);
  stars(ctx, s, 101, 60, [700, 350, 200, 200]);
  ctx.restore();
  // 松脱的控制面板：轻轻晃动，指示灯红闪
  ctx.save();
  ctx.translate(1240, 360);
  ctx.rotate(0.06 + Math.sin(s * 2.2) * 0.03);
  ctx.fillStyle = '#0a0e11';
  ctx.fillRect(0, 0, 200, 300);
  ctx.strokeStyle = 'rgba(120,140,150,0.3)';
  ctx.lineWidth = 3;
  ctx.strokeRect(0, 0, 200, 300);
  ctx.restore();
  glow(ctx, 1300, 420, 30, RED, 0.9 * (Math.sin(s * 5) > 0 ? 1 : 0.2));
  glow(ctx, 1380, 420, 24, '80,255,140', 0.15);
  alarm(ctx, 800, 90, s * 0.6, 0.45);
  shade(ctx, 800, 450, 1100, 0.62);
}

function energy(ctx, s, o, st) {
  panels(ctx, -300, 780, CYAN);
  vfill(ctx, -300, 780, W + 600, 420, [[0, '#0f1418'], [1, '#040506']]);
  ctx.strokeStyle = '#0a0f12';
  ctx.lineWidth = 34;
  ctx.beginPath();
  ctx.moveTo(-300, 200); ctx.lineTo(600, 200); ctx.quadraticCurveTo(660, 200, 660, 260);
  ctx.moveTo(W + 300, 300); ctx.lineTo(1000, 300); ctx.quadraticCurveTo(940, 300, 940, 360);
  ctx.stroke();
  ctx.fillStyle = '#0b1013';
  ctx.fillRect(640, 120, 320, 680);
  const pulse = 0.35 + 0.25 * Math.sin(s * 0.9);
  for (let i = 0; i < 6; i += 1) {
    const y = 180 + i * 100;
    ctx.fillStyle = `rgba(${CYAN},${pulse * (0.5 + 0.5 * Math.sin(s * 1.5 - i * 0.6))})`;
    ctx.fillRect(650, y, 300, 14);
  }
  glow(ctx, 800, 460, 520, CYAN, 0.18 * pulse);
  plume(ctx, st.cool, s, { x: 560, y: 760, count: 14, life: 3.5, rise: 80, spread: 60, size: 50, alpha: 0.14, seed: 111 });
  for (let i = 0; i < 6; i += 1) {
    const x = 1080 + (i % 3) * 120;
    const y = 470 + Math.floor(i / 3) * 160;
    ctx.fillStyle = '#0a0d10';
    ctx.fillRect(x, y, 90, 130);
    const charge = i === 4 ? 0.9 : 0.15;
    ctx.fillStyle = `rgba(${i === 4 ? '90,255,150' : RED},${0.6 + 0.3 * Math.sin(s * 2 + i)})`;
    ctx.fillRect(x + 12, y + 110 - 90 * charge, 66, 90 * charge);
  }
  shade(ctx, 800, 460, 1150, 0.6);
}

function comms(ctx, s, o, st) {
  panels(ctx, -300, 760, CYAN);
  vfill(ctx, -300, 760, W + 600, 460, [[0, '#101418'], [1, '#040506']]);
  // 观察窗外，观测室的记录灯在闪
  ctx.fillStyle = '#020306';
  ctx.fillRect(1100, 140, 380, 260);
  stars(ctx, s, 121, 50, [1100, 140, 380, 260]);
  glow(ctx, 1380, 330, 24, RED, Math.sin(s * 3) > 0.2 ? 0.9 : 0.1);
  ctx.strokeStyle = '#0c1115';
  ctx.lineWidth = 14;
  ctx.strokeRect(1100, 140, 380, 260);
  ctx.fillStyle = '#0a0d10';
  ctx.fillRect(160, 560, 900, 60);
  ctx.fillRect(200, 620, 30, 140);
  ctx.fillRect(990, 620, 30, 140);
  const screens = [[200, 'wave'], [480, 'dark'], [760, 'text']];
  for (const [x, kind] of screens) {
    ctx.fillStyle = '#05080a';
    ctx.fillRect(x, 330, 250, 190);
    if (kind === 'wave') {
      ctx.strokeStyle = `rgba(${CYAN},0.8)`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i <= 230; i += 4) {
        const y = 425 + Math.sin(i * 0.08 + s * 4) * 30 * Math.sin(i * 0.02 + s);
        if (i === 0) ctx.moveTo(x + 10 + i, y); else ctx.lineTo(x + 10 + i, y);
      }
      ctx.stroke();
      glow(ctx, x + 125, 425, 160, CYAN, 0.12);
    } else if (kind === 'text') {
      for (let i = 0; i < 6; i += 1) {
        ctx.fillStyle = `rgba(${CYAN},${0.35 + 0.2 * (i % 2)})`;
        ctx.fillRect(x + 20, 350 + i * 24, 80 + ((i * 53) % 120), 6);
      }
      if (Math.sin(s * 6) > 0) { ctx.fillStyle = `rgba(${CYAN},0.9)`; ctx.fillRect(x + 20, 350 + 6 * 24, 12, 14); }
    }
  }
  poly(ctx, [520, 540, 600, 536, 604, 556, 524, 560], 'rgba(230,225,200,0.45)');
  shade(ctx, 700, 450, 1150, 0.6);
}

function observatory(ctx, s, o, st) {
  vfill(ctx, -300, -300, W + 600, H + 600, [[0, '#010205'], [1, '#05080e']]);
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(160, 80, 1280, 640, 60);
  ctx.clip();
  ctx.fillStyle = '#010206';
  ctx.fillRect(160, 80, 1280, 640);
  stars(ctx, s, 131, 220, [160, 80, 1280, 640]);
  const g = ctx.createRadialGradient(1100, 1500, 700, 1100, 1500, 960);
  g.addColorStop(0, '#0d2033');
  g.addColorStop(0.92, '#1d4a6a');
  g.addColorStop(1, 'rgba(120,190,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(160, 80, 1280, 640);
  const frost = ctx.createRadialGradient(800, 400, 380, 800, 400, 800);
  frost.addColorStop(0, 'rgba(220,235,255,0)');
  frost.addColorStop(1, 'rgba(220,235,255,0.35)');
  ctx.fillStyle = frost;
  ctx.fillRect(160, 80, 1280, 640);
  ctx.restore();
  ctx.strokeStyle = '#0b1014';
  ctx.lineWidth = 26;
  ctx.beginPath();
  ctx.roundRect(160, 80, 1280, 640, 60);
  ctx.moveTo(800, 80); ctx.lineTo(800, 720);
  ctx.stroke();
  vfill(ctx, -300, 740, W + 600, 460, [[0, '#0e1317'], [1, '#030405']]);
  ctx.fillStyle = '#0a0d10';
  ctx.fillRect(1180, 640, 180, 120);
  glow(ctx, 1220, 670, 26, RED, (s * 1.7) % 1 < 0.5 ? 0.9 : 0.15);
  shade(ctx, 800, 420, 1200, 0.5);
}

/** 飞船外景：o.pod 为逃生舱离开（o.dawn 时星球边缘泛起晨光）；开场只显示漂流的“回声号”。 */
function space(ctx, s, o, st) {
  vfill(ctx, -300, -300, W + 600, H + 600, [[0, '#010204'], [1, '#04070d']]);
  stars(ctx, s, 141, 260, [-300, -300, W + 600, H + 600]);
  const dawn = o.dawn ? ease(s / 10) : 0;
  const g = ctx.createRadialGradient(900, 2200, 1300, 900, 2200, 1560);
  g.addColorStop(0, mix('#071322', '#1a2f4a', dawn));
  g.addColorStop(0.9, mix('#16365a', '#f0b77a', dawn));
  g.addColorStop(1, 'rgba(255,200,140,0)');
  ctx.fillStyle = g;
  ctx.fillRect(-300, 300, W + 600, H + 300);
  if (dawn) glow(ctx, 1300, 760, 700, '255,190,120', 0.35 * dawn);
  // “回声号”：舰体剪影与逐盏熄灭的灯
  ctx.save();
  ctx.translate(520 + Math.sin(s * 0.2) * 10, 360);
  ctx.rotate(-0.12 + Math.sin(s * 0.15) * 0.02);
  poly(ctx, [-520, -40, 260, -60, 380, 0, 260, 60, -520, 40], '#0a0e12');
  ctx.fillStyle = '#0a0e12';
  ctx.fillRect(-420, -110, 120, 220);
  ctx.fillRect(-120, -90, 80, 180);
  for (let i = 0; i < 10; i += 1) {
    const alive = !o.pod || i / 10 > clamp01(s / 12);
    ctx.fillStyle = `rgba(255,210,140,${alive ? 0.7 : 0.05})`;
    ctx.fillRect(-460 + i * 70, -6, 10, 6);
  }
  ctx.restore();
  if (o.pod) {
    const t = ease(s / 14);
    const x = 900 + 600 * t;
    const y = 420 - 160 * t;
    const k = 1 - 0.6 * t;
    glow(ctx, x - 50 * k, y + 10 * k, 120 * k, '120,200,255', 0.6);
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(k, k);
    ctx.fillStyle = '#1a2229';
    ctx.beginPath();
    ctx.ellipse(0, 0, 60, 34, -0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = 'rgba(160,220,255,0.5)';
    ctx.beginPath();
    ctx.ellipse(18, -6, 14, 10, -0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
  shade(ctx, 800, 450, 1300, 0.4);
}

const SCENES = {
  black: { draw(ctx) { ctx.fillStyle = '#000'; ctx.fillRect(-300, -300, W + 600, H + 600); }, camera: () => [1, 0, 0] },
  harbor: { focus: [430, 470], draw: harbor, camera: (s) => [1 + 0.14 * ease(s / 18), -110 * ease(s / 18), 20 * ease(s / 18)] },
  ending: { focus: [700, 470], draw: (ctx, s, o, st) => harbor(ctx, s, { ...o, dawn: o.dawn }, st), camera: (s) => [1.12 - 0.1 * ease(s / 16), -60 + 40 * ease(s / 16), 0] },
  lobby: { focus: [560, 470], draw: lobby, camera: (s) => [1.02 + 0.06 * ease(s / 22), -50 * ease(s / 22) + Math.sin(s * 0.3) * 6, Math.sin(s * 0.23) * 4] },
  office: { focus: [880, 470], draw: office, camera: (s) => [1.06, -110 + 220 * ease(s / 24), Math.sin(s * 0.2) * 5] },
  kitchen: { focus: [720, 520], draw: kitchen, camera: (s) => [1.04 + 0.03 * Math.sin(s * 0.12), -40 + Math.sin(s * 0.18) * 30, 0] },
  portrait: { focus: [660, 480], draw: portrait, camera: (s) => [1 + 0.08 * ease(s / 12), 30 * ease(s / 12), -20 * ease(s / 12)] },
  generic: { focus: [800, 450], draw: generic, camera: (s) => [1.03 + 0.03 * ease(s / 20), Math.sin(s * 0.15) * 30, 0] },
  guestroom: { focus: [930, 520], draw: guestroom, camera: (s) => [1.04 + 0.05 * ease(s / 20), 70 * ease(s / 20), 0] },
  backyard: { focus: [640, 560], draw: backyard, camera: (s) => [1.05, -70 + 170 * ease(s / 22), Math.sin(s * 0.2) * 6] },
  zhouroom: { focus: [860, 600], draw: zhouroom, camera: (s) => [1.05 + 0.04 * ease(s / 18), -40 + Math.sin(s * 0.16) * 30, 0] },
  attic: { focus: [820, 500], draw: attic, camera: (s) => [1.06 + 0.04 * ease(s / 18), 30 * Math.sin(s * 0.12), 10] },
  doorway: { focus: [1050, 520], draw: doorway, camera: (s) => [1 + 0.12 * ease(s / 6), 120 * ease(s / 6), 0] },
  storeroom: { focus: [800, 500], draw: storeroom, camera: (s) => [1.05 + 0.06 * ease(s / 10), 0, 0] },
  bay: { focus: [700, 480], draw: bay, camera: (s) => [1.04 + 0.05 * ease(s / 20), 60 * Math.sin(s * 0.12), 0] },
  corridor: { focus: [800, 430], draw: corridor, camera: (s) => [1 + 0.1 * ease(s / 24), Math.sin(s * 0.2) * 20, Math.sin(s * 0.9) * 3] },
  toolroom: { focus: [760, 460], draw: toolroom, camera: (s) => [1.04 + 0.04 * ease(s / 20), -60 + 140 * ease(s / 22), 0] },
  airlock: { focus: [880, 450], draw: airlock, camera: (s) => [1.03 + 0.07 * ease(s / 18), 30 * ease(s / 18), 0] },
  energy: { focus: [820, 460], draw: energy, camera: (s) => [1.04 + 0.04 * ease(s / 20), Math.sin(s * 0.15) * 40, 0] },
  comms: { focus: [640, 450], draw: comms, camera: (s) => [1.04 + 0.04 * ease(s / 20), -40 + 100 * ease(s / 22), 0] },
  observatory: { focus: [800, 420], draw: observatory, camera: (s) => [1.02 + 0.06 * ease(s / 24), 0, Math.sin(s * 0.2) * 6] },
  space: { focus: [700, 420], draw: space, camera: (s) => [1 + 0.08 * ease(s / 20), -40 * ease(s / 20), 0] },
};

/** 是否有这个画面键，播放器据此把“画面键开头”的场景 id 对应到画面。 */
export function hasScene(name) {
  return Object.prototype.hasOwnProperty.call(SCENES, name) && name !== 'black';
}

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
    this.shakeUntil = 0;
    this.shakeMs = 1;
    this.shakePower = 0;
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

  /** 镜头震动 ms 毫秒，power 为最大位移（虚拟像素）；减少动态效果时不震。 */
  shake(ms, power) {
    if (REDUCED) return;
    this.shakeMs = ms;
    this.shakePower = power;
    this.shakeUntil = performance.now() + ms;
  }

  frame(now) {
    const { ctx, canvas } = this;
    const s = (now - this.sceneAt) / 1000;
    // 填满画框：按较大的缩放比例铺满，窄屏（竖屏手机）或宽屏（横屏手机）时围绕画面重点裁切。
    const cw = canvas.width;
    const ch = canvas.height;
    const k = Math.max(cw / W, ch / H);
    const vw = cw / k;
    const vh = ch / k;
    const [fx, fy] = this.options.focus || this.scene.focus || [W / 2, H / 2];
    const ox = vw >= W - 0.5 ? (W - vw) / 2 : Math.min(Math.max(fx - vw / 2, -240), W + 240 - vw);
    const oy = vh >= H - 0.5 ? (H - vh) / 2 : Math.min(Math.max(fy - vh / 2, -150), H + 150 - vh);
    let [zoom, dx, dy] = REDUCED ? [1.02, 0, 0] : this.scene.camera(s);
    if (now < this.shakeUntil) {
      const left = (this.shakeUntil - now) / this.shakeMs;
      dx += (Math.random() - 0.5) * 2 * this.shakePower * left;
      dy += (Math.random() - 0.5) * 2 * this.shakePower * left;
    }
    ctx.setTransform(k, 0, 0, k, -ox * k, -oy * k);
    const cx = ox + vw / 2;
    const cy = oy + vh / 2;
    ctx.translate(cx, cy);
    ctx.scale(zoom, zoom);
    ctx.translate(-cx - dx, -cy - dy);
    this.scene.draw(ctx, REDUCED ? s * 0.4 : s, this.options, this.res);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const flash = Math.max(0, 1 - (now - this.flashAt) / 700);
    if (flash > 0) {
      ctx.fillStyle = `rgba(255,236,200,${0.16 * flash})`;
      ctx.fillRect(0, 0, cw, ch);
    }
    const dark = this.level(now);
    if (dark > 0) {
      ctx.fillStyle = `rgba(0,0,0,${dark})`;
      ctx.fillRect(0, 0, cw, ch);
    }
    requestAnimationFrame(this.frame);
  }
}
