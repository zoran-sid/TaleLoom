/** 把原剧本排成整段旁白与有署名的对白，只处理显示，不推进游戏。 */
import { dialogueSpeakers } from './dialogue-speakers.js';

export function readingPages(text, { storyId, sceneId, fallbackSpeaker = '' } = {}) {
  const speakers = dialogueSpeakers[storyId]?.[sceneId] || {};
  const pages = [];
  const append = (text, speaker = '') => {
    text = text.trim();
    if (text && !/^(?:周|周文|阿芸|顾先生|陈掌柜|阿水|老许)[：:]$/.test(text)) pages.push({ text, speaker });
  };
  for (const paragraph of text.split('\n').map(p => p.trim()).filter(Boolean)) {
    let cursor = 0;
    for (const quote of paragraph.matchAll(/“([^”]+)”/g)) {
      const speaker = speakers[quote[1]];
      if (!speaker) continue;
      append(paragraph.slice(cursor, quote.index));
      append(quote[0], speaker);
      cursor = quote.index + quote[0].length;
    }
    append(paragraph.slice(cursor), cursor ? '' : fallbackSpeaker);
  }
  return pages;
}
