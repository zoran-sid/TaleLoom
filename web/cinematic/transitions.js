import dockOpening from './media/dock-opening.mp4?url';
import officeNight from './media/office-night.mp4?url';
import waterVat from './media/water-vat.mp4?url';

import officeArrival from './media/office-arrival.mp4?url';
import dutyRoom from './media/duty-room.mp4?url';
import oldLedger from './media/old-ledger.mp4?url';
import dawnTable from './media/dawn-table.mp4?url';
import finalSignature from './media/final-signature.mp4?url';
import echoBayWake from './media/echo-bay-wake.mp4?url';
import echoEnergyReserve from './media/echo-energy-reserve.mp4?url';
import echoAirlockSeal from './media/echo-airlock-seal.mp4?url';
import echoSpaceDepart from './media/echo-space-depart.mp4?url';

import dockOpeningStart from './media/dock-opening-start.jpg?url';
import echoBayWakeStart from './media/echo-bay-wake-start.jpg?url';

const openingStills = {
  fog_harbor_ledger: dockOpeningStart,
  deep_space_film: echoBayWakeStart,
};

const ledgerTransitions = new Map([
  ['p01_dock', dockOpening],
  ['p04_office', officeArrival],
  ['a01_found', officeNight],
  ['b04_duty', dutyRoom],
  ['c01_batch', oldLedger],
  ['d01_kitchen', waterVat],
  ['e01_table', dawnTable],
  ['e04_sign', finalSignature],
]);

const shipTransitions = new Map([
  ['bay_wake', echoBayWake],
  ['energy_reserve', echoEnergyReserve],
  ['airlock_seal', echoAirlockSeal],
  ['space_depart', echoSpaceDepart],
]);

/** 转场跟随正式场景 ID，保留其他剧本原有画面。 */
export function transitionFor(storyId, sceneId) {
  if (storyId === 'fog_harbor_ledger') return ledgerTransitions.get(sceneId);
  if (storyId === 'deep_space_film') return shipTransitions.get(sceneId);
  return undefined;
}

/** 开场视频的第一帧：开始页停在这一帧上，点击开始后从这里接着播放。 */
export function openingStill(storyId) {
  return openingStills[storyId];
}

/** 开始页提前载入开场视频并停在第一帧；playTransition 会从这一帧直接播放。 */
export function primeTransition(video, url, poster) {
  video.muted = true;
  video.preload = 'auto';
  if (poster) video.poster = poster;
  video.src = url;
  video.dataset.primed = url;
  video.dataset.visible = '';
  video.hidden = false;
}

/** 撤掉提前载入的开场视频（例如玩家选择从存档点继续）。 */
export function dropPrimedTransition(video) {
  if (!video.dataset.primed) return;
  delete video.dataset.primed;
  delete video.dataset.visible;
  video.hidden = true;
  video.removeAttribute('poster');
  video.removeAttribute('src');
  video.load();
}

/** 播放无声过场，跳过、超时或加载失败时交回现有剧情画面。 */
export async function playTransition(video, url, { onPlaying, setSkip, fadeTime }) {
  let started = false;
  let timer;
  let finish;
  let reveal;

  video.hidden = false;
  video.muted = true;
  try {
    await new Promise(resolve => {
      finish = resolve;
      reveal = () => {
        started = true;
        video.dataset.visible = '';
        clearTimeout(timer);
        timer = setTimeout(finish, 8_000);
        onPlaying();
      };
      setSkip(finish);
      video.addEventListener('playing', reveal, { once: true });
      video.addEventListener('ended', finish, { once: true });
      video.addEventListener('error', finish, { once: true });
      timer = setTimeout(finish, 2_500);
      // 已经停在第一帧的开场视频直接播放，不重新载入。
      if (video.dataset.primed !== url) video.src = url;
      delete video.dataset.primed;
      video.play().catch(finish);
    });
  } finally {
    clearTimeout(timer);
    setSkip(null);
    video.removeEventListener('playing', reveal);
    video.removeEventListener('ended', finish);
    video.removeEventListener('error', finish);
    video.pause();
    delete video.dataset.visible;
    if (started) await new Promise(resolve => setTimeout(resolve, fadeTime));
    video.hidden = true;
    video.removeAttribute('poster');
    video.removeAttribute('src');
    video.load();
  }
  return started;
}
