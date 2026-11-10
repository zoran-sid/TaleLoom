/** 角色配音按 Python 场景、原句与已标明的说话人精确匹配；未录制的文字只显示。 */
const LINES = {
  c01_batch: [{ speaker: '周文', text: '“也许是记到别处了。”', asset: 'voice_zhou_c01' }],
  b03_porch: [{ speaker: '阿芸', text: '“信里的私事，能不念给他们听吗？”', asset: 'voice_ayun_b03' }],
  b05_gu: [{ speaker: '顾先生', text: '“那封信送到我合伙人手里，我后天收不收得到钱都没用了。他会先把信用收回去。”', asset: 'voice_gu_b05' }],
};

/** 返回当前完整段落的配音素材 ID；原文不匹配时保持文字阅读。 */
export function voiceFor(view, page) {
  if (view?.story_id !== 'fog_harbor_ledger') return null;
  return LINES[view.scene_id]?.find((line) => line.speaker === page.speaker && line.text === page.text)?.asset || null;
}

/** 进入场景时预取当前场景已经录制的原句。 */
export function voicesForScene(view) {
  if (view?.story_id !== 'fog_harbor_ledger') return [];
  return (LINES[view.scene_id] || []).map((line) => line.asset);
}
