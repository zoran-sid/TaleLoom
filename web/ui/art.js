/**
 * 首页与阅读页的版画图形。负责人：ZRS。
 *
 * 每个故事世界有一幅代码绘制的几何版画（雾港、深空）和一个主题色；影像剧照
 * 经样式处理成单色版画后用作场景配图。图形只用 SVG 属性和样式类，不写内联
 * style，以符合站点的 style-src 'self' 策略。主体画在中间 700×700 内，四周可裁。
 */
import plates from './plates.json';

const stills = import.meta.glob('../cinematic/media/*.jpg', { eager: true, query: '?url', import: 'default' });
const stillUrl = (name) => stills[`../cinematic/media/${name}.jpg`];
const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

let serial = 0;

/** 雾港：灯塔、旅馆、码头；雾带横向漂移，光束缓慢扫过。 */
function fogArt() {
  let windows = '';
  for (let row = 0; row < 3; row += 1) {
    for (let column = 0; column < 5; column += 1) {
      const lit = row === 1 && column === 3;
      windows += `<rect x="${566 + column * 42}" y="${492 + row * 46}" width="22" height="30" `
        + (lit ? 'class="art-lamp art-lit"/>' : 'class="art-tint" opacity=".42"/>');
    }
  }
  let posts = '';
  for (let x = 40; x < 1000; x += 96) posts += `<rect x="${x}" y="652" width="10" height="${44 + (x % 3) * 8}"/>`;
  return `<svg class="art art-fog" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
    <rect class="art-tint" width="1000" height="1000"/>
    <circle class="art-paper" cx="668" cy="296" r="128"/>
    <path class="art-main" opacity=".26" d="M0 566 L170 508 L340 548 L520 524 L760 552 L1000 530 L1000 650 L0 650Z"/>
    <g class="art-beam"><path class="art-lamp" opacity=".34" d="M318 374 L1250 232 L1250 446Z"/></g>
    <path class="art-main" d="M288 640 L301 402 L335 402 L348 640Z"/>
    <path class="art-paper" opacity=".85" d="M296.4 486 L339.6 486 L341.8 528 L294.2 528Z"/>
    <rect class="art-ink" x="294" y="392" width="48" height="11"/>
    <rect class="art-lamp" x="304" y="356" width="28" height="36"/>
    <path class="art-ink" d="M296 356 L318 326 L340 356Z"/>
    <path class="art-main" d="M528 474 L668 402 L808 474Z"/>
    <rect class="art-ink" x="544" y="474" width="248" height="166"/>
    ${windows}
    <rect class="art-ink" x="0" y="640" width="1000" height="14"/>
    <rect class="art-main" x="0" y="654" width="1000" height="346"/>
    <g class="art-ink">${posts}</g>
    <g class="art-lamp" opacity=".8"><rect x="684" y="690" width="34" height="5"/><rect x="676" y="712" width="50" height="5"/><rect x="690" y="736" width="26" height="5"/></g>
    <g class="art-tint" opacity=".34"><rect x="110" y="730" width="230" height="5"/><rect x="420" y="772" width="180" height="5"/><rect x="60" y="836" width="300" height="5"/><rect x="640" y="816" width="250" height="5"/><rect x="330" y="908" width="380" height="5"/></g>
    <g class="art-paper">
      <rect class="art-band" x="-120" y="424" width="600" height="46" rx="23" opacity=".82"/>
      <rect class="art-band" x="430" y="548" width="720" height="54" rx="27" opacity=".72"/>
      <rect class="art-band" x="40" y="586" width="520" height="38" rx="19" opacity=".88"/>
      <rect class="art-band" x="300" y="700" width="820" height="48" rx="24" opacity=".42"/>
      <rect class="art-band" x="-220" y="786" width="700" height="58" rx="29" opacity=".4"/>
      <rect class="art-band" x="520" y="876" width="640" height="44" rx="22" opacity=".34"/>
    </g>
    <g class="art-stroke-ink" fill="none" stroke-width="5" stroke-linecap="round"><path d="M420 236 q17 -15 34 0 q17 -15 34 0"/><path d="M500 190 q11 -10 22 0 q11 -10 22 0"/></g>
  </svg>`;
}

/** 深空：行星、两道轨道、沿轨道航行的回声号；飞船向外发出一圈圈回声。 */
function deepArt() {
  serial += 1;
  const clip = `art-planet-${serial}`;
  let seed = 11;
  const random = () => { seed = seed * 16807 % 2147483647; return seed / 2147483647; };
  let stars = '';
  for (let index = 0; index < 80; index += 1) {
    const x = Math.round(random() * 1000);
    const y = Math.round(random() * 1000);
    const r = (0.9 + random() * 2.1).toFixed(1);
    stars += `<circle cx="${x}" cy="${y}" r="${r}"${index % 3 === 0 ? ' class="art-twinkle"' : ' opacity=".7"'}/>`;
  }
  const echo = (extra) => `<circle class="art-echo${extra}" r="16" fill="none" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
  const craft = `${echo('')}${echo(' art-echo-2')}${echo(' art-echo-3')}
      <rect class="art-tint" x="-60" y="-6" width="28" height="12"/><rect class="art-tint" x="32" y="-6" width="28" height="12"/>
      <rect class="art-paper" x="-28" y="-10" width="56" height="20" rx="10"/><circle class="art-lamp art-lit" cx="14" r="4"/>`;
  // 关闭动态效果时飞船停在轨道上方，不再航行。
  const ship = reducedMotion()
    ? `<g transform="translate(667 359) rotate(20)">${craft}</g>`
    : `<g><animateMotion dur="110s" begin="-33s" repeatCount="indefinite" rotate="auto" path="M90 500a430 150 0 1 1 860 0a430 150 0 1 1 -860 0"/>${craft}</g>`;
  return `<svg class="art art-deep" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
    <defs><clipPath id="${clip}"><circle cx="250" cy="810" r="330"/></clipPath></defs>
    <rect class="art-main" width="1000" height="1000"/>
    <g class="art-paper">${stars}</g>
    <circle class="art-lamp" cx="250" cy="196" r="30"/>
    <circle class="art-stroke-lamp" cx="250" cy="196" r="54" fill="none" stroke-width="2" opacity=".5"/>
    <circle class="art-mid" cx="250" cy="810" r="330"/>
    <g clip-path="url(#${clip})">
      <g class="art-tint" opacity=".28"><rect x="-100" y="560" width="800" height="26"/><rect x="-100" y="640" width="800" height="60"/><rect x="-100" y="760" width="800" height="18"/><rect x="-100" y="840" width="800" height="44"/></g>
      <circle class="art-main" cx="356" cy="900" r="330" opacity=".5"/>
    </g>
    <g transform="rotate(-20 520 500)">
      <ellipse class="art-stroke-paper" cx="520" cy="500" rx="430" ry="150" fill="none" stroke-width="2" opacity=".6"/>
      <ellipse class="art-stroke-paper" cx="520" cy="500" rx="300" ry="104" fill="none" stroke-width="2" stroke-dasharray="3 12" opacity=".5"/>
      ${ship}
    </g>
  </svg>`;
}

const drawings = { fog: fogArt, deep: deepArt };

/** 故事所属的世界（决定主题色与题图）；未登记的故事返回 null。 */
export function worldOf(storyId) {
  return plates.stories[storyId]?.world ?? plates.films[storyId]?.world ?? null;
}

function fill(node, markup) {
  node.innerHTML = markup;
  return node;
}

/** 把节点画成某个世界的几何版画；未知世界时画一块只有首字的素色版。 */
export function drawWorld(node, world, fallbackText = '') {
  node.classList.add('plate');
  node.dataset.world = world || 'plain';
  if (drawings[world]) return fill(node, drawings[world]());
  node.replaceChildren();
  const initial = document.createElement('span');
  initial.className = 'plate-initial';
  initial.textContent = [...fallbackText][0] || '';
  initial.setAttribute('aria-hidden', 'true');
  node.append(initial);
  return node;
}

/** 把节点画成版画处理后的剧照；素材缺失时返回 false。 */
export function drawStill(node, name, world) {
  const source = stillUrl(name);
  if (!source) return false;
  node.classList.add('plate', 'plate-still');
  node.dataset.world = world || 'plain';
  const image = document.createElement('img');
  image.src = source;
  image.alt = '';
  image.decoding = 'async';
  node.replaceChildren(image);
  return true;
}

/** 影像版条目的题图。 */
export function drawFilm(node, filmId) {
  const film = plates.films[filmId];
  if (film && drawStill(node, film.still, film.world)) return node;
  return drawWorld(node, film?.world ?? null);
}

/**
 * 阅读页的场景配图：有对应剧照用剧照，否则用该故事的几何版画；
 * 未登记的故事返回 null，由调用方隐藏配图。
 * 返回值是配图的标识，标识不变时调用方不必重画。
 */
export function scenePlateKey(storyId, sceneId) {
  const story = plates.stories[storyId];
  if (!story) return null;
  const still = story.scenes[sceneId];
  return still && stillUrl(still) ? `still:${still}` : `world:${story.world}`;
}

export function drawScenePlate(node, storyId, key) {
  const world = worldOf(storyId);
  node.classList.remove('plate-still');
  if (key.startsWith('still:')) drawStill(node, key.slice(6), world);
  else drawWorld(node, world);
  return node;
}
