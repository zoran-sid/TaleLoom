import dockOpening from './media/dock-opening.mp4?url';
import officeNight from './media/office-night.mp4?url';
import waterVat from './media/water-vat.mp4?url';

import officeArrival from './media/office-arrival.mp4?url';
import dutyRoom from './media/duty-room.mp4?url';
import oldLedger from './media/old-ledger.mp4?url';
import dawnTable from './media/dawn-table.mp4?url';
import finalSignature from './media/final-signature.mp4?url';

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

/** 转场跟随正式场景 ID，保留其他剧本原有画面。 */
export function transitionFor(storyId, sceneId) {
  return storyId === 'fog_harbor_ledger' ? ledgerTransitions.get(sceneId) : undefined;
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
      video.src = url;
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
    video.removeAttribute('src');
    video.load();
  }
  return started;
}
