// 最小单槽存储，仅服务部署试玩；LQ 的正式 web/storage 模块在接入时替换。
const prefix = 'taleloom:v1:';
export function readSave(storyId) {
  try {
    const raw = localStorage.getItem(prefix + storyId);
    return raw ? JSON.parse(raw) : null;
  } catch {
    throw new Error('无法读取本机存档。可以使用导入功能恢复 JSON 存档。');
  }
}
export function writeSave(storyId, payload) {
  try { localStorage.setItem(prefix + storyId, JSON.stringify(payload)); }
  catch { throw new Error('本机存储不可用或空间不足，请导出存档保存进度。'); }
}
