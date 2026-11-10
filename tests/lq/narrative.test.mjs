import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readingPages } from '../../web/cinematic/narrative.js';

test('旁白保持整段，证物名称及未知引文不推测说话人', () => {
  const text = '签上写着“海鸥”和“叁佰”。\n一个没有标注人物的“引用”。';
  assert.deepEqual(readingPages(text), text.split('\n').map(text => ({ text, speaker: '' })));
});
test('按原剧本拆开对白和旁白，准确区分同场的不同人物', () => {
  const pages = readingPages('“你还怕我少你？”\n周文把薄账移到手边：“工钱在另一册，我记着。”\n“上个月也是你记着。”',
    { storyId: 'fog_harbor_ledger', sceneId: 'p03_dinner' });
  assert.deepEqual(pages, [
    { text: '“你还怕我少你？”', speaker: '陈掌柜' },
    { text: '周文把薄账移到手边：', speaker: '' },
    { text: '“工钱在另一册，我记着。”', speaker: '周文' },
    { text: '“上个月也是你记着。”', speaker: '阿芸' },
  ]);
});
test('同一句被叙述引用时不冒充对白；标注按剧本与场景隔离', () => {
  assert.deepEqual(readingPages('“你还怕我少你？”', { storyId: 'other', sceneId: 'p03_dinner' }),
    [{ text: '“你还怕我少你？”', speaker: '' }]);
  assert.deepEqual(readingPages('背面还有一句：“今夜给答复，明早须说清。”',
    { storyId: 'fog_harbor_ledger', sceneId: 'c02_724' }),
  [{ text: '背面还有一句：“今夜给答复，明早须说清。”', speaker: '' }]);
});
test('旧样片与飞船广播使用各自的说话人，审问反馈沿用已知人物', () => {
  assert.equal(readingPages('“我一整晚都在房里看书，哪儿也没去。”',
    { storyId: 'fog_harbor_film', sceneId: 'gu_first' })[0].speaker, '顾先生');
  assert.equal(readingPages('“别把所有电力都交给导航。”',
    { storyId: 'deep_space_film', sceneId: 'bay_wake' })[0].speaker, '警报录音');
  assert.deepEqual(readingPages('我没有离开。', { fallbackSpeaker: '顾先生' }),
    [{ text: '我没有离开。', speaker: '顾先生' }]);
});

test('选择后的对话反馈也有署名，跨场反馈不把提问者和回答者混淆', () => {
  assert.equal(readingPages('值房里的老许接话：“电话还通。船什么时候开，要看水上。”',
    { storyId: 'fog_harbor_ledger', sceneId: 'p01_dock' })[1].speaker, '老许');
  const pages = readingPages('“原始流水也带来了？”\n“供货商的书面确认在这里，完整流水明早由查验员带来。旧代管款的申请材料也在。”',
    { storyId: 'fog_harbor_ledger', sceneId: 'p03_dinner' });
  assert.deepEqual(pages.map(p => p.speaker), ['周文', '你']);
});
