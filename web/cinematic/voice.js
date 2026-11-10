/**
 * 影像模式的配音：用浏览器内置 Web Speech API 实时朗读，不加载音频文件。
 *
 * 设计目标：
 * - 多角色区分音色：旁白与每个角色各有 pitch／rate 与选声偏好；系统里有多个中文
 *   语音时，按性别和名字把不同语音分配给不同角色，只有一个语音时靠音高区分。
 * - 情感与氛围：按场景情绪调整语速与音高（发现尸体低沉缓慢、对质紧张、推理冷静），
 *   破折号与省略号处加入停顿，贴合《雾港旧案》的悬疑节奏。
 * - 不喧宾夺主：配音只伴随字幕，不阻塞剧情推进，玩家点击翻页立即中断；不支持
 *   Web Speech、没有中文语音或被静音时静默跳过，剧情文字始终完整。
 *
 * 浏览器要求用户点击后才能稳定出声，init() 与首次 speak 都在「开始」点击之后。
 */

// 角色基础音色：female 用于选声，pitch 越低越沉，rate 为语速倍率。
// voice 是该角色在系统语音列表里的名字偏好（按顺序匹配，小写包含即可）。
export const ROLES = {
  '': { female: false, pitch: 0.82, rate: 0.92, voice: ['kang', 'li-mu', 'liang'] },          // 旁白：沉稳冷峻
  '陈掌柜': { female: false, pitch: 0.78, rate: 0.94, voice: ['kang', 'li-mu'] },              // 中年掌柜，威严
  '老许': { female: false, pitch: 0.74, rate: 0.9, voice: ['kang', 'liang'] },                 // 值房老仆，苍老
  '顾先生': { female: false, pitch: 0.9, rate: 1.0, voice: ['li-mu', 'kang'] },                // 住客，表面镇定
  '周文': { female: false, pitch: 0.96, rate: 0.97, voice: ['liang', 'kang'] },                // 记账青年，冷静克制
  '阿水': { female: false, pitch: 1.08, rate: 1.05, voice: ['han', 'kang'] },                  // 年轻船家，清亮
  '你': { female: false, pitch: 1.0, rate: 0.96, voice: ['kang', 'liang'] },                  // 查账人，平稳
  '阿芸': { female: true, pitch: 1.22, rate: 1.0, voice: ['xiaoyan', 'ting', 'hui', 'yao', 'mei'] }, // 年轻女工
};

// 场景情绪：只作用于旁白（无 speaker 的段落）。rate/pitch 为倍率。
export const SCENE_MOOD = {
  p01_dock: { rate: 0.93, pitch: 0.96 },        // 雾夜码头：平静中压着悬疑
  p02_lobby: { rate: 1.0, pitch: 1.0 },         // 大堂：平实
  p03_dinner: { rate: 0.97, pitch: 0.98 },      // 饭桌：暗流涌动
  p04_office: { rate: 0.95, pitch: 0.96 },      // 账房：气氛转紧
  a01_found: { rate: 0.85, pitch: 0.9 },        // 发现尸体：低沉、缓慢
  a02_door: { rate: 0.96, pitch: 0.97 },        // 众人聚集：惊惶压抑
  a03_lamp: { rate: 0.94, pitch: 0.97 },        // 灯下残页：紧张
  a04_window: { rate: 0.92, pitch: 0.98 },      // 第一份假说：冷静推理
};

// 角色在特定场景的情绪覆盖（倍率），用于表现人物当下的状态。
export const ROLE_SCENE = {
  p04_office: {
    '陈掌柜': { rate: 0.95, pitch: 0.92 },       // 笑容收敛，语气严厉
    '顾先生': { rate: 1.05, pitch: 1.04 },      // 心虚，语速加快
  },
  a01_found: { '顾先生': { rate: 1.04, pitch: 1.05 } },
  a02_door: {
    '阿芸': { rate: 1.05, pitch: 1.07 },         // 惊惶
    '顾先生': { rate: 1.04, pitch: 1.04 },      // 掩饰
  },
  a03_lamp: { '顾先生': { rate: 1.05, pitch: 1.05 } }, // 试探、紧张
  a04_window: { '阿芸': { rate: 0.97, pitch: 0.99 } }, // 犹豫
};

const GAP_STOP = 130;     // 普通句末停顿（毫秒）
const GAP_PAUSE = 380;    // 破折号、省略号处的停顿
const MAX_ONE_SPEAK = 70; // 单段超过这个字数，按逗号再拆，避免引擎截断长文本

const FEMALE_HINT = /ting|mei|xia|hui|yao|sin|lily|tian|female|女|yu.shu/i;
const MALE_HINT = /kang|li.mu|liang|han|male|男/i;
const MANDARIN = /cmn|zh[-_](cn|tw|sg|hans|hant)/i;
const CHINESE = /zh|cmn|yue/i;

// 清洗文本：去掉不朗读的引号等符号；破折号与省略号转成内部停顿标记。
export function cleanText(raw) {
  return raw
    .replace(/[“”‘’「」『』]/g, '')
    .replace(/——|--|—/g, '\u001f')
    .replace(/…+|\.\.\./g, '\u001f')
    .replace(/[ \t]+/g, ' ')
    .trim();
}

/**
 * 把一段字幕拆成依次朗读的小段：{ text, gap }。
 * 按句末标点断句，PAUSE 标记处单独成段并给更长停顿；过长的句子按逗号再拆。
 */
export function splitSegments(raw) {
  const cleaned = cleanText(raw);
  if (!cleaned) return [];
  const segments = [];
  const push = (text, gap) => {
    text = text.trim();
    if (text) segments.push({ text, gap });
  };
  const parts = cleaned.split('\u001f');
  parts.forEach((part, index) => {
    const sentences = part.match(/[^。！？；!?;]+[。！？；!?;]?/g) || [];
    for (let sentence of sentences) {
      sentence = sentence.trim();
      if (!sentence) continue;
      if (sentence.length <= MAX_ONE_SPEAK) {
        push(sentence, GAP_STOP);
      } else {
        // 长句按逗号／冒号再拆，读起来更有呼吸，也规避长文本被截断。
        const clauses = sentence.match(/[^，,：:]+[，,：:]?/g) || [sentence];
        clauses.forEach((clause, i) => push(clause, i === clauses.length - 1 ? GAP_STOP : 60));
      }
    }
    // 只有标记真实存在（后面还有内容）才给上一段加长停顿；末尾标记同理落在前一段。
    if (index < parts.length - 1 && segments.length) segments[segments.length - 1].gap = GAP_PAUSE;
  });
  return segments;
}

/**
 * 从系统语音列表里为角色挑一个语音：优先国语（避免粤语腔），再按名字偏好与性别。
 * 纯函数，便于单测。返回 null 时让浏览器使用默认语音。
 */
export function resolveVoice(voices, role) {
  if (!voices || !voices.length) return null;
  const chinese = voices.filter((v) => CHINESE.test(v.lang || ''));
  if (!chinese.length) return null;
  // 优先国语／普通话语音，粤语语音（zh-HK、yue）靠后。
  let pool = chinese.filter((v) => MANDARIN.test(v.lang || ''));
  if (!pool.length) pool = chinese;

  // 1) 角色的名字偏好（ROLES.voice 关键词）。
  for (const keyword of role.voice || []) {
    const hit = pool.find((v) => v.name.toLowerCase().includes(keyword));
    if (hit) return hit;
  }
  // 2) 按性别名字线索。
  const genderMatch = pool.filter((v) =>
    (role.female && FEMALE_HINT.test(v.name)) || (!role.female && MALE_HINT.test(v.name)));
  if (genderMatch.length) return genderMatch[0];
  // 3) 只有一个中文语音或认不出性别：共用，靠 pitch 区分。
  return pool[0];
}

// 计算某角色在某场景下的最终 pitch／rate。
export function voiceParams(speaker, sceneId) {
  const role = ROLES[speaker] || ROLES[''];
  let { pitch, rate } = role;
  const mood = SCENE_MOOD[sceneId];
  if (!speaker && mood) { pitch *= mood.pitch; rate *= mood.rate; }
  const sceneRole = ROLE_SCENE[sceneId]?.[speaker];
  if (sceneRole) { pitch *= sceneRole.pitch; rate *= sceneRole.rate; }
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
  return { pitch: clamp(pitch, 0, 2), rate: clamp(rate, 0.1, 10), role };
}

export class Voice {
  // 依赖注入便于在 Node 单测里传入 mock；默认取浏览器全局。
  constructor({ synth, utteranceCtor, root } = {}) {
    const win = root || (typeof window !== 'undefined' ? window : undefined);
    this.synth = synth || (win && 'speechSynthesis' in win ? win.speechSynthesis : null);
    this.Utterance = utteranceCtor
      || (win && win.SpeechSynthesisUtterance) || null;
    this.supported = Boolean(this.synth && this.Utterance);
    this.voices = [];
    this.enabled = true;     // 配音开关
    this.muted = false;      // 主静音联动
    this.token = 0;          // 每次 speak 自增，作废旧队列的回调
    this.queue = [];
    this.gapTimer = null;
    this.lastRequest = null;
    this._onVisible = null;
    if (win && typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) this.suspend();
        else this.resume();
      });
    }
  }

  /** 在用户点击「开始」后调用：加载语音列表并监听异步刷新。 */
  init() {
    if (!this.supported) return;
    const refresh = () => { this.voices = this.synth.getVoices() || []; };
    refresh();
    if (typeof this.synth.onvoiceschanged !== 'undefined') {
      this.synth.onvoiceschanged = refresh;
    }
  }

  /** 朗读一页字幕；同一页可能是旁白或带署名的对白。不阻塞剧情。 */
  speak(rawText, { speaker = '', sceneId = '' } = {}) {
    this.lastRequest = { rawText, speaker, sceneId };
    if (!this.supported || !this.enabled || this.muted) return;
    this.stop();
    const token = this.token;
    const { pitch, rate, role } = voiceParams(speaker, sceneId);
    const voice = resolveVoice(this.voices, role);
    for (const segment of splitSegments(rawText)) {
      let utterance;
      try {
        utterance = new this.Utterance(segment.text);
      } catch {
        continue;
      }
      if (voice) { utterance.voice = voice; utterance.lang = voice.lang; }
      else utterance.lang = 'zh-CN';
      utterance.pitch = pitch;
      utterance.rate = rate;
      utterance.volume = 1;
      this.queue.push({ utterance, gap: segment.gap });
    }
    this.playNext(token);
  }

  playNext(token) {
    if (token !== this.token) return;
    const item = this.queue.shift();
    if (!item) return;
    const { utterance, gap } = item;
    utterance.onend = () => {
      if (token !== this.token) return;
      this.gapTimer = setTimeout(() => this.playNext(token), gap);
    };
    // 被打断或无引擎时跳过这一段，继续后面的，不让队列卡死。
    utterance.onerror = () => {
      if (token !== this.token) return;
      this.playNext(token);
    };
    try {
      this.synth.speak(utterance);
    } catch {
      this.playNext(token);
    }
  }

  /** 立即中断朗读并清空队列；翻页、静音、快速回退、重开时调用。 */
  stop() {
    this.token += 1;
    this.queue = [];
    if (this.gapTimer) { clearTimeout(this.gapTimer); this.gapTimer = null; }
    if (this.supported) {
      try { this.synth.cancel(); } catch { /* 环境不可用 */ }
    }
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    if (!enabled) this.stop();
  }

  /** 主静音：静音时连配音一起停，恢复时按配音开关决定是否出声。 */
  setMuted(muted) {
    this.muted = muted;
    if (muted) this.stop();
  }

  suspend() {
    this.stop();
  }

  /** 回到前台：若当前页字幕还在，重新朗读这一页。 */
  resume() {
    if (!this.supported || !this.enabled || this.muted || !this.lastRequest) return;
    const { rawText, speaker, sceneId } = this.lastRequest;
    this.speak(rawText, { speaker, sceneId });
  }
}
