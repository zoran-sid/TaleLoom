/** Seed Audio requests derived from the same pages that the cinematic player renders. */
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { readingPages } from '../web/cinematic/narrative.js';

const scenes = JSON.parse(readFileSync(new URL('../stories/film/fog_harbor_ledger/story.json', import.meta.url))).scenes;
const storyId = 'fog_harbor_ledger';
const voice = {
  '旁白': '声音低沉的中年男子，冷静克制，语速适中',
  '你': '沉稳清晰的成年男子，耐心而审慎',
  '陈掌柜': '中年男子，温和而有威严',
  '周文': '成熟男子，克制沉稳，语速稍慢',
  '顾先生': '中年男子，礼貌但带戒备',
  '阿芸': '年轻女性，女声，音色清亮偏轻、略带疲惫，语速稍慢，有主见；不要用男声',
  '阿水': '年轻清亮的男子，干练诚恳',
  '老许': '苍老沉稳的男子',
};

const CAST = '固定声线：阿芸是年轻女声；旁白、你、陈掌柜、周文、顾先生、阿水、老许是男声。以下每句必须由括号内的人物用对应性别和声线朗读，不得互换。';

function promptFor(text, sceneId) {
  const lines = readingPages(text, { storyId, sceneId }).map(page => {
    const who = page.speaker || '旁白';
    const spoken = page.speaker ? page.text.replace(/^“|”$/g, '') : page.text.replaceAll('“', '「').replaceAll('”', '」');
    return `${who}（${voice[who] || voice['旁白']}）说道：“${spoken}”`;
  }).join(' ');
  return CAST + ' ' + lines;
}

const jobs = [];
for (const scene of scenes) {
  if (scene.text) {
    jobs.push({ id: `scene_${scene.id}`, kind: 'scene', scene_id: scene.id,
      source_text: scene.text, pages: readingPages(scene.text, { storyId, sceneId: scene.id }),
      prompt: promptFor(scene.text, scene.id) });
  }
  for (const choice of scene.choices || []) {
    const message = (choice.message || '').trim();
    if (!message || message.startsWith('【')) continue;
    const digest = createHash('sha256').update(`${scene.id}\0${message}`).digest('hex').slice(0, 12);
    jobs.push({ id: `choice_${digest}`, kind: 'choice', scene_id: scene.id,
      source_text: message, pages: readingPages(message, { storyId, sceneId: scene.id }),
      prompt: promptFor(message, scene.id) });
  }
}
process.stdout.write(JSON.stringify(jobs));
