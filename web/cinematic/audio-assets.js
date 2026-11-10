/** 已审核的录音素材。模型、参数、授权、费用与请求 ID 见 docs/audio-direction.md。 */
import { VOICE_ASSETS } from './voice-assets.generated.js';

const BASE_ASSETS = {
  harbor_arrival: { url: new URL('./audio/harbor_arrival.mp3', import.meta.url).href, layer: 'bgm', gain: 0.85 },
  inn_night: { url: new URL('./audio/inn_night.mp3', import.meta.url).href, layer: 'bgm', gain: 0.8 },
  discovery: { url: new URL('./audio/discovery.mp3', import.meta.url).href, layer: 'bgm', gain: 0.85 },
  harbor: { url: new URL('./audio/harbor.mp3', import.meta.url).href, layer: 'ambience', gain: 0.65 },
  lobby: { url: new URL('./audio/lobby.mp3', import.meta.url).href, layer: 'ambience', gain: 0.6 },
  dinner: { url: new URL('./audio/dinner.mp3', import.meta.url).href, layer: 'ambience', gain: 0.6 },
  office: { url: new URL('./audio/office.mp3', import.meta.url).href, layer: 'ambience', gain: 0.78 },
  ledger: { url: new URL('./audio/ledger.mp3', import.meta.url).href, layer: 'ambience', gain: 0.6 },
  ledger_inquiry: { url: new URL('./audio/ledger-inquiry.mp3', import.meta.url).href, layer: 'bgm', gain: 0.85 },
  ledger_room: { url: new URL('./audio/ledger-room.mp3', import.meta.url).href, layer: 'ambience', gain: 0.65 },
  ledger_paper: { url: new URL('./audio/ledger-paper.mp3', import.meta.url).href, layer: 'sfx', gain: 0.75 },
  voice_zhou_c01: { url: new URL('./audio/voice-zhou-c01.mp3', import.meta.url).href, layer: 'voice', gain: 1 },
  voice_ayun_b03: { url: new URL('./audio/voice-ayun-b03.mp3', import.meta.url).href, layer: 'voice', gain: 1 },
  voice_gu_b05: { url: new URL('./audio/voice-gu-b05.mp3', import.meta.url).href, layer: 'voice', gain: 1 },
};

export const AUDIO_ASSETS = Object.freeze({ ...BASE_ASSETS, ...VOICE_ASSETS });
