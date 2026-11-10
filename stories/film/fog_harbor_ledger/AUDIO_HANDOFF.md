# 《未结的账》声音与动画交接

更新：2026-11-11。此文件是动画成员从本次 `main` 推送继续制作镜头的工作说明。

## 播放规则

- 序章和第一幕原有的八条整场 MP3 仍可播放。配音从第一张字幕出现时开始，字幕按音频播放进度自动翻页；点击可跳过当前页，同时把音频移到下一页。八条旧整场录音已用 Whisper 转写按剧本原文对齐出每页结束时间（`legacy-cues.json`），不再按字数估算。
- 新录音由 Seed Audio 1.0 返回的字级字幕生成每页结束时间。原文与识别字幕匹配度低于 0.95 的录音不进入游戏。暂停笔记、切后台、静音及重新开启配音时保留当前播放位置。
- 录制的环境声覆盖同名代码环境声；加载失败会恢复代码环境声。环境声提示每种只显示一次。配音时环境声自动压低，主音量与静音同时控制配音和环境声。
- 场景文字、选择反馈和说话人仍来自 Python 剧本与会话。前端只按场景 ID 和原文匹配素材；原文变动后，旧素材不会误配到新句子。

## 动画成员可用的接口

`document` 会发出两个只读事件，可监听而不修改声音模块：

| 事件 | `detail` | 用途 |
| --- | --- | --- |
| `taleloom:reading-page` | `sceneId`, `text`, `speaker`, `audioId` | 一张文字页出现时切换镜头或人物状态 |
| `taleloom:audio-progress` | `id`, `time`, `duration`（秒） | 用真实播放时间驱动动作和口型；`id` 是场景 ID 或选择反馈音频 ID |

新素材的每页结束时间见 `web/cinematic/seed-runtime.json`；八条旧素材见 `web/cinematic/legacy-cues.json`。动画应以播放事件和场景 ID 为准。点击跳页后，音频进度会跳到下一页；关闭配音或换场后，旧音频不再发送进度事件。动画实现不需要改动 Python 剧本、存档或声音生成工具。

### 接入示例

在新动画模块中监听事件，不要为镜头另设固定的字幕计时器：

```js
let activeAudioId = null;

document.addEventListener('taleloom:reading-page', ({ detail }) => {
  activeAudioId = detail.audioId;
  // detail.sceneId 决定场景；detail.speaker 决定人物；detail.text 决定镜头重点。
  // 每次进入新文字页时结束上一页的动作，再开始本页的动作。
});

document.addEventListener('taleloom:audio-progress', ({ detail }) => {
  if (detail.id !== activeAudioId) return;
  // detail.time / detail.duration 是实际播放进度，可驱动口型或证物特写。
});
```

`audioId` 为 `null` 时表示这一页没有录音，镜头仍应由 `reading-page` 驱动。打开笔记或切到后台后音频进度暂停；点击跳页会改变音频位置。回到存档点或换场时，应清理旧镜头的计时器和动画实例。页面已有减少动态效果设置，新增动画须尊重 `prefers-reduced-motion`。

### 镜头与素材定位

| 段落 | 场景 ID | 动画重点 |
| --- | --- | --- |
| 序章与第一幕 | `p01_*` 至 `p04_*`、`a01_*` 至 `a04_*` | 抵港、旅馆、饭桌、命案发现；八条旧录音按对齐时间翻页，口型宜使用低精度表现 |
| 调查 | `b01_*` 至 `d04_*` | 纸片、账簿、袖口、值房与证词；用文字页事件切近景，保留玩家主动翻页空间 |
| 对质与结局 | `e01_*` 至 `f05_*` | 人物戒备、自白或否认，以及五种结局的情绪区别；按场景 ID 区分分支 |

场景的 `art`、原文与分支条件在 `story.json`；新录音文件在 `web/cinematic/audio/seed/`；每页结束秒数在 `web/cinematic/seed-runtime.json` 的 `scenes[sceneId].cues`。`choices` 中的键是 `[sceneId, 原文]` 的 JSON 字符串，选择反馈可以用 `reading-page.audioId` 关联，无需动画代码解析该键。`manifest.json` 是制作溯源，不应在运行时加载。

动画成员可以在独立模块中开发和测试镜头，音频事件与画面绘制分开。接入后用 `npm run build` 和 `npx playwright test tests/browser/cinematic-audio-sync.spec.js` 核对文字与声音同步；本地正常速度试玩时不要加 `?fast=1`，该参数仅缩短转场以便测试。当前不要求截图，由项目负责人自行检查画面。

## 声音修正（2026-11-11）

- 阿芸曾被生成成男声的 10 页（`b02_kitchen`、`c04_book_a`、`c04_book_b`、`d04_seal`、`e01_table`）已用 Seed Audio 1.0 重新生成：以女声参考音 `@Audio1` 固定阿芸声线，其余角色保持男声。复测基频均在 220–250 Hz，确认是女声。
- 10 条环境声循环已按场景重写提示并重新生成，统一 40 秒、约 −34 LUFS，替换 `web/cinematic/audio/seed/ambience_*.mp3`。
- 火山引擎凭据在当前环境被拒（`45000000`/`45000010`），因此本次改用 fal 托管的 `bytedance/seed-audio-1.0`（同一模型）；参考音与生成记录在 `web/cinematic/audio/seed/manifest.json`，估算费用约 2 美元。
- 场景每页结束时间重新按 Seed Audio 台词对齐；`tests/zc/test_seed_runtime.py` 校验时间单调且不超出音频。

## 生成与审校

- 生成工具：`tools/seed_audio.py`；素材计划从 `tools/seed_audio_plan.mjs` 读取与播放器相同的 `readingPages`。运行 `python3 tools/seed_audio.py --list` 可查看剩余数量和预计费用，不会调用 API。
- 接口：火山引擎 Seed Audio 1.0 的 `POST /api/v3/tts/create`。本账号使用 App ID 与 Bearer 方式。令牌只从本机权限为 `0600` 的 `/private/tmp/taleloom-volcengine.key` 读取，不进入仓库。
- 每条素材在 `web/cinematic/audio/seed/manifest.json` 记录模型、提示词、参数、生成时间、原始时长、按官方费率估算的费用、字幕和 SHA-256。环境声经过响度整理，原文件哈希及处理参数一并保留。
- 已完成 **42 个新增场景、44 段选择反馈、10 种环境声**。八次不合格生成及重做过程保存在清单的 `rejected` 中；这些文件不进入网页。所有合格配音已统一到约 −18 LUFS，环境声约 −34 LUFS。
- 上线前须逐条核对角色声线、断句和环境声循环；文字匹配检查只负责拦截漏读与添词，不能代替试听。

本次获批的批量生成及两轮重做合计约 **40.14 元**，低于批准的 **60 元**上限；此前小样费用另记在清单中，实际结算以火山账单为准。`python3 tools/seed_audio.py --list` 现在显示待生成数为零。生成工具支持 `--max-cost-cny` 限额，并为每个进行中的请求预留最多 2 元。

服务资料：[接口与字幕字段](https://docs.volcengine.com/docs/doubao-voice/audio-generation-http?lang=zh)、[模型时长与文本限制](https://docs.volcengine.com/docs/doubao-voice/model-list?lang=zh)、[计费](https://docs.volcengine.com/docs/DoubaoVoice/Billinginstructions-21?lang=zh)、[生成式模型服务条款](https://docs.volcengine.com/docs/DoubaoVoice/Generativemodelservicespecificterms-1?lang=zh)。正式公开分发前，项目负责人应按账号的服务订单确认生成音频的使用地区和授权条件。
