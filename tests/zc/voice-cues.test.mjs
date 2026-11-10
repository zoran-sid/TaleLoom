import { test } from 'node:test';
import assert from 'node:assert/strict';
import { voiceFor, voicesForScene } from '../../web/cinematic/voice-cues.js';
import { readingPages } from '../../web/cinematic/narrative.js';
import { VOICE_LINES } from '../../web/cinematic/voice-lines.generated.js';

test('人物配音只匹配引擎场景、人物和原剧本句子', () => {
  const scene = { story_id: 'fog_harbor_ledger', scene_id: 'c01_batch' };
  assert.equal(voiceFor(scene, { speaker: '周文', text: '“也许是记到别处了。”' }), 'voice_zhou_c01');
  assert.equal(voiceFor(scene, { speaker: '顾先生', text: '“也许是记到别处了。”' }), null);
  assert.equal(voiceFor({ ...scene, scene_id: 'c02_724' }, { speaker: '周文', text: '“也许是记到别处了。”' }), null);
});

test('预取人物句子不改变其他剧本', () => {
  assert.deepEqual(voicesForScene({ story_id: 'fog_harbor_ledger', scene_id: 'c01_batch' }), ['voice_zhou_c01']);
  assert.deepEqual(voicesForScene({ story_id: 'deep_space_film', scene_id: 'c01_batch' }), []);
});

test('阿芸与顾先生的原句按现有段落规则找到已录制配音', () => {
  for (const [sceneId, paragraph, asset] of [
    ['b03_porch', '阿芸压着信说：“信里的私事，能不念给他们听吗？”', 'voice_ayun_b03'],
    ['b05_gu', '“我去拿欠据。”他又说：“那封信送到我合伙人手里，我后天收不收得到钱都没用了。他会先把信用收回去。”', 'voice_gu_b05'],
  ]) {
    const view = { story_id: 'fog_harbor_ledger', scene_id: sceneId };
    const pages = readingPages(paragraph, { storyId: view.story_id, sceneId });
    assert.ok(pages.some((page) => voiceFor(view, page) === asset));
  }
});

test('序章与第一章的每句对白按场景、人物和原句命中', () => {
  for (const [scene, lines] of Object.entries(VOICE_LINES)) {
    const view = { story_id: 'fog_harbor_ledger', scene_id: scene };
    for (const line of lines) {
      assert.equal(voiceFor(view, { speaker: line.speaker, text: `“${line.text}”` }), line.asset);
      assert.equal(voiceFor(view, { speaker: '你', text: `“${line.text}”` }), null);
    }
    assert.deepEqual(new Set(voicesForScene(view)), new Set(lines.map((line) => line.asset)));
  }
});
