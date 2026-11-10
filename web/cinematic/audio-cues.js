/** 由 Python 快照中的剧本、场景和结局 ID 决定声音；不读取画面选项。 */
const SCENES = {
  p01_dock: ['harbor_arrival', 'harbor'],
  p02_lobby: ['inn_night', 'lobby'], p03_dinner: ['inn_night', 'dinner'], p04_office: ['inn_night', 'office'],
  a01_found: ['discovery', 'office'], a02_door: ['discovery', 'office'], a03_lamp: ['discovery', 'ledger'], a04_window: ['discovery', 'office'],
  b01_coat: ['inquiry', 'lobby'], b01_grab: ['guarded', 'lobby'], b01_paper: ['inquiry', 'ledger'],
  b02_kitchen: ['inquiry', 'kitchen'], b03_porch: ['inquiry', 'harbor'], b03_repair: ['guarded', 'harbor'],
  b04_duty: ['inquiry', 'dutyroom'], b05_gu: ['inquiry', 'lobby'], b05_silent: ['guarded', 'lobby'], b06_rewrite: ['inquiry', 'ledger'],
  c01_batch: ['ledger_inquiry', 'ledger_room'], c02_724: ['ledger_pressure', 'ledger_room'],
  c04_ask_a: ['ledger_pressure', 'ledger_room'], c04_ask_b: ['ledger_pressure', 'ledger_room'],
  c04_book_a: ['ledger_grief', 'ledger_room'], c04_book_b: ['ledger_grief', 'ledger_room'],
  c04_refuse_a: ['ledger_pressure', 'ledger_room'], c04_refuse_b: ['ledger_pressure', 'ledger_room'],
  c03_roster_a: ['ledger_grief', 'ledger_room'], c03_roster_b: ['ledger_grief', 'ledger_room'],
  c05_tonight: ['ledger_revelation', 'ledger_room'],
  d01_kitchen: ['inquiry', 'kitchen'], d02_weight: ['discovery', 'kitchen'],
  d02_sleeve: ['confrontation', 'kitchen'], d02_refuse: ['guarded', 'kitchen'],
  d03_custody: ['guarded', 'lobby'], d04_missing: ['guarded', 'lobby'], d04_box: ['discovery', 'lobby'], d04_seal: ['inquiry', 'lobby'],
  e01_table: ['confrontation', 'dinner'], e02_zhou: ['confrontation', 'dinner'],
  e02_gu: ['confrontation', 'dinner'], e02_ayun: ['confrontation', 'dinner'],
  e03_confess: ['revelation', 'dinner'], e03_deny: ['guarded', 'dinner'],
  e04_funds: ['revelation', 'dinner'], e04_sign: ['revelation', 'dinner'],
};
const ENDINGS = { truth: 'dawn', dawn: 'dawn', insufficient: 'dark', scapegoat: 'dark', wrong: 'dark' };

/** 返回剧本声音意图；其他剧本返回 null，由原有声音规则处理。 */
export function cueFor(view) {
  if (view?.story_id !== 'fog_harbor_ledger') return null;
  if (view.ending_id) return { music: ENDINGS[view.ending_id] || 'dark', ambience: 'ending' };
  const pair = SCENES[view.scene_id];
  return pair ? { music: pair[0], ambience: pair[1] } : null;
}

/** 首次进入特定账目场景时的实物拟音，场景 ID 来自 Python 引擎。 */
export function entrySfxFor(view) {
  return view?.story_id === 'fog_harbor_ledger' && view.scene_id === 'c01_batch' ? 'ledger_paper' : null;
}

/** B06 的三个调查方向都会进入 C01；在选择时已下载好录音。 */
export function preloadFor(view) {
  return view?.story_id === 'fog_harbor_ledger' && view.scene_id === 'b06_rewrite'
    ? ['ledger_inquiry', 'ledger_room', 'ledger_paper'] : [];
}

/** 字幕里使用的配乐名称；新轨道和合成声共用同一套说法。 */
export const MUSIC_LABELS = {
  harbor_arrival: '雾港靠岸', inn_night: '旅馆夜话', discovery: '命案发现',
  inquiry: '问询', guarded: '戒备', ledger_inquiry: '账目调查',
  ledger_pressure: '账目催逼', ledger_grief: '旧账', ledger_revelation: '今晚的账',
  confrontation: '对质', revelation: '自白', dawn: '天亮', dark: '未散',
};

export const AMBIENCE_LABELS = {
  harbor: '夜港水声', lobby: '大堂炉火', dinner: '一张饭桌', office: '雨夜账房',
  ledger: '灯下纸页', kitchen: '后厨水声', dutyroom: '值房', ledger_room: '账房雨夜',
  ending: '尾声',
};

export const musicLabel = (name) => MUSIC_LABELS[name] || name || '';
export const ambienceLabel = (name) => AMBIENCE_LABELS[name] || name || '';

/** 当原创轨道尚未录制时，沿用已经上线的 Web Audio 声音。 */
export const PROCEDURAL_MUSIC = {
  harbor_arrival: 'calm', inn_night: 'calm', discovery: 'tense', inquiry: 'study', guarded: 'dark',
  ledger_inquiry: 'study', ledger_pressure: 'tense', ledger_grief: 'dark', ledger_revelation: 'dark',
  confrontation: 'tense', revelation: 'dark', dawn: 'dawn', dark: 'dark',
};
export const PROCEDURAL_AMBIENCE = { ledger_room: 'ledger' };
