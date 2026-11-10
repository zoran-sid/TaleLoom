/** 从剧本对白署名生成序章与第一章的配音清单；不改剧情，只登记声音。
 *
 *     node tools/make_voice_spec.mjs
 *
 * 输出 tools/voice_spec.json，交给 tools/audio_pipeline.py --voice 生成。
 * 同一人物同一句只录一次；同一句在不同场景出现时复用同一条录音。
 */
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dialogueSpeakers } from '../web/cinematic/dialogue-speakers.js';

const SCENES = ['p01_dock', 'p02_lobby', 'p03_dinner', 'p04_office',
  'a01_found', 'a02_door', 'a03_lamp', 'a04_window'];
const VOICES = {
  周文: { voice_id: 'Patient_Man', speed: 0.92, pitch: -2, emotion: 'neutral' },
  阿芸: { voice_id: 'Calm_Woman', speed: 0.88, pitch: 1, emotion: 'sad' },
  顾先生: { voice_id: 'Elegant_Man', speed: 0.91, pitch: -2, emotion: 'sad' },
  陈掌柜: { voice_id: 'Deep_Voice_Man', speed: 0.86, pitch: -3, emotion: 'neutral' },
  阿水: { voice_id: 'Casual_Guy', speed: 0.9, pitch: -4, emotion: 'neutral' },
  老许: { voice_id: 'Imposing_Manner', speed: 0.84, pitch: -3, emotion: 'neutral' },
};
const SLUG = { 周文: 'zhou', 阿芸: 'ayun', 顾先生: 'gu', 陈掌柜: 'chen', 阿水: 'ashui', 老许: 'laoxu' };
const speakerMap = dialogueSpeakers.fog_harbor_ledger;

const byText = new Map();
const lines = [];
const scenes = {};
for (const scene of SCENES) {
  scenes[scene] = [];
  let count = 0;
  for (const [text, speaker] of Object.entries(speakerMap[scene] || {})) {
    if (speaker === '你') continue;
    const voice = VOICES[speaker];
    if (!voice) throw new Error(`缺少 ${speaker} 的声线设置`);
    const key = `${speaker}\u0000${text}`;
    let id = byText.get(key);
    if (!id) {
      count += 1;
      id = `voice_${SLUG[speaker]}_${scene}_${count}`;
      byText.set(key, id);
      const file = id.replaceAll('_', '-') + '.mp3';
      lines.push({
        id, file, scene, speaker, text,
        endpoint: 'fal-ai/minimax/speech-2.8-hd',
        input: {
          prompt: text,
          language_boost: 'Chinese',
          voice_setting: { ...voice, vol: 1 },
          audio_setting: { format: 'mp3', sample_rate: 44100, bitrate: 128000, channel: 1 },
          output_format: 'url',
        },
      });
    }
    scenes[scene].push({ speaker, text, asset: id });
  }
}

const spec = {
  story: 'fog_harbor_ledger',
  section: '序章与第一章',
  note: '由 tools/make_voice_spec.mjs 生成；同一人物同一句复用一条录音。',
  scenes,
  lines,
};
const target = fileURLToPath(new URL('./voice_spec.json', import.meta.url));
writeFileSync(target, JSON.stringify(spec, null, 2) + '\n');
console.log(`写入 ${target}：${lines.length} 条唯一台词，${Object.values(scenes).flat().length} 处场景引用`);
