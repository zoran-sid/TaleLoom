# 《未结的账》声音设计

本方案以 Python 会话快照的 `story_id`、`scene_id`、`ending_id` 为声音事件依据。`web/cinematic/audio-cues.js` 是可扩展的剧本声音映射；`sound.js` 保留原有 Web Audio 合成、静音、音量记忆、后台暂停和字幕。录音素材统一登记在 `audio-assets.js`，通过独立的 `audio-layers.js` 播放。资源加载失败时继续播放原有合成声。未改动动画、Canvas 或人物 UI。

## 全剧情绪路线

| 段落 | 声音意图 | 阅读时的处理 |
| --- | --- | --- |
| 序章码头、旅馆与饭桌 | 海口雾笛逐渐退到远处；室内有炉火、座钟与碗筷 | 音乐留白，让人物关系先建立 |
| 命案发现 | 环境声收窄，低音和不稳定和声出现 | 证物出现时用一次克制的反馈，不用惊吓音 |
| 顾、阿芸与值房的调查 | 稳定的低干扰思索底层；人物拒答时减少高频与旋律 | 同一地点可随信任变化换音乐，不随镜头特写硬切 |
| 账目调查 C01–C05 | C01 比对数字保持冷静；C02 认责书加压；小册与旧名册带出悲伤；C05 把期限串成共同清晨 | C01 已有一条 BGM、一个账房环境床和一声翻纸；其余暂用合成声 |
| 后厨、水缸与封存 | 水、铜与布料是主要实物声，音乐保持低位 | 发现镇纸时短暂让音乐让位，避免每条线索都响一次 |
| 最终对质 | 四组论证逐步累积低音与节奏密度 | 自白保留停顿，否认用安静表达戒备 |
| 五种结局 | 雾散与交给天亮有开放的晨光；错指与证据不足保留未解决和声 | 结局由 `ending_id` 决定，不根据画面猜测 |

地点层以港口、旅馆、后厨、值房、账房为独立声音空间。交互拟音优先保留翻纸、落笔、铜器入水、封袋、电话；每一声应对应玩家确实看见或完成的动作。持续调查音乐目标为约 40–60 秒可循环的片段；后续制作可加入同调性的替换片段，减少半小时游玩时的疲劳。场景视频和转场可以更丰富：命案、镇纸出水、四组对质和五种结局允许更鲜明的声画层次与主题变化，具体镜头与动作由视觉负责人设计。

## 序章与第一章（2026-11-10 生成）

覆盖 `p01_dock`–`p04_office` 与 `a01_found`–`a04_window`：三首配乐按“靠岸—旅馆夜—命案发现”推进，五条环境声按港口、大堂、饭桌、账房、灯下纸页切换。游戏读 Python 快照的 `scene_id`，不读画面或选项文本。

| 场景 | 配乐 | 环境声 |
| --- | --- | --- |
| `p01_dock` 雾港码头 | `harbor_arrival` 雾港靠岸 | `harbor` 夜港水声 |
| `p02_lobby` 大堂 | `inn_night` 旅馆夜话 | `lobby` 大堂炉火 |
| `p03_dinner` 饭桌 | `inn_night` | `dinner` 一张饭桌 |
| `p04_office` 账房 | `inn_night` | `office` 雨夜账房 |
| `a01_found` 按约取账 | `discovery` 命案发现 | `office` |
| `a02_door` 谁先走进来 | `discovery` | `office` |
| `a03_lamp` 灯下残页 | `discovery` | `ledger` 灯下纸页 |
| `a04_window` 窗与第一份假说 | `discovery` | `office` |

生成与后期由 `tools/audio_pipeline.py` 完成，参数在 `tools/audio_spec.json`。命令：

```bash
python tools/audio_pipeline.py --list
python tools/audio_pipeline.py --only harbor_arrival --only discovery
python tools/audio_pipeline.py --reuse-raw --force     # 只重做后期，不再调用 fal
```

凭据只从 `FAL_KEY` 或仓库根目录 `.fal-key` 读取；原始 WAV 留在 `web/cinematic/audio/raw/`（不入库），成品 MP3 与请求 ID、响度、SHA-256 写入 `web/cinematic/audio/manifest.json`。后期把音乐首尾交叉 3 秒、环境声 2 秒，再按实测响度补增益：音乐目标 −24 LUFS、峰值上限 −2 dB，环境声目标 −30.5 LUFS、峰值上限 −3 dB。`office` 原始素材峰值较高，补增益受峰值限制，成品为 −33.2 LUFS，由 `audio-assets.js` 的播放增益 0.78 补回；其余环境声为 −31 LUFS 左右。

| 文件 | 模型 / 请求 ID | 生成输入 | 估算费用 | 处理后响度 / SHA-256 |
| --- | --- | --- | ---: | --- |
| `harbor_arrival.mp3` | Stable Audio 2.5，fal `01a1c55b-1ac8-7870-acb6-05ad19d7b10e`，seed `19311001` | 55 秒，8 steps，guidance 3；Prompt D | $0.20 | 52 秒，−24.5 LUFS；`df384da07f574090a16e23a2a0ffd580b0df725d155da7f06097e8521cfd52b6` |
| `inn_night.mp3` | Stable Audio 2.5，fal `01a1c55b-5ce2-7173-81a9-d0abea7746f6`，seed `19311002` | 55 秒，8 steps，guidance 3；Prompt E | $0.20 | 52 秒，−24.4 LUFS；`a1146211a347e595166b55acd1c45f5a5e740ee2660152162b33b4478f7e5cbe` |
| `discovery.mp3` | Stable Audio 2.5，fal `01a1c55b-8db4-7e33-8651-b95bcf9a5641`，seed `19311003` | 55 秒，8 steps，guidance 3；Prompt F | $0.20 | 52 秒，−24.4 LUFS；`9f53dc317edbf4109f20ec3f6e64765f833eef12451729af29ec958eef2ed8a2` |
| `harbor.mp3` | Sonilo v1.1，fal `01a1c55b-c7b5-7f53-9ccb-3e44a763b86d` | 42 秒，WAV；Prompt G | $0.0756 | 40 秒，−31.0 LUFS；`b71743b5870d53bb08891e1385b1e46a0953b7ae31c1eb35c6a6f877b83f188c` |
| `lobby.mp3` | Sonilo v1.1，fal `01a1c55c-431f-7383-9044-8f93d97a994c` | 42 秒，WAV；Prompt H | $0.0756 | 40 秒，−31.0 LUFS；`85e4676050901a824bbda39c1c93502e25ae792a7fc45fef5953bff6ccbed058` |
| `dinner.mp3` | Sonilo v1.1，fal `01a1c55c-80f3-7872-846f-ce2a8a5d3519` | 42 秒，WAV；Prompt I | $0.0756 | 40 秒，−30.9 LUFS；`5492cc49bf6771cce9682b0cde2c450510bf26f396e500cfddc05d7952db2258` |
| `office.mp3` | Sonilo v1.1，fal `01a1c55c-acf4-7850-a3d5-c9e220cf1993` | 42 秒，WAV；Prompt J | $0.0756 | 40 秒，−33.2 LUFS；`55591d09876d50d4ef426e429335f625e12ffcc2b82f4e75618ffb825ac2af88` |
| `ledger.mp3` | Sonilo v1.1，fal `01a1c567-66e8-7fd3-b82c-f86c20429ce4` | 42 秒，WAV；Prompt K | $0.0756 | 40 秒，−30.9 LUFS；`bd41a6d73494bbaad4c773b12ea4f34f776b7401f518b7ce7b668f59dd13a573` |

序章与第一章的音色、循环接缝和与字幕的平衡尚待总设计者试听确认。配乐与环境声八条素材加上一次 `ledger` 重生成合计约 **$1.05**（Stable Audio 3 × $0.20，Sonilo 6 × 42 秒 × $0.0018）；再加人物配音约 $0.05，本轮合计约 **$1.10**。第一次 `ledger` 生成几乎全程静音，只有两处纸声，不能作为连续环境床；改用“全程稳定房间底噪、纸声均匀分布”的 Prompt K 后重生成。实际账单以 fal 为准。

**Prompt D**：Original restrained cinematic opening cue for a 1931 foggy Chinese harbor at nightfall. The last ferry nudges the pier, foghorns far out on the water, wet stone and rope. Sparse felt piano over low sustained cello, a lone bass clarinet, faint harmonium air, slow 58 BPM, minor mode with a fragile rising third, long silences. Intimate, humid, patient. No vocals, no drums, no jump scare, no recognizable film or game theme. Seamless sustained ending suitable for looping under Chinese text.

**Prompt E**：Original restrained cinematic underscore for the dining room of a 1931 Chinese harbor inn at night. Warm but uneasy: felt piano, muted harmonium, low cello, soft double bass, a faint clock-like wooden pulse rather than drums, 64 BPM, shifting between minor and its relative major, restrained dynamics. Candlelit, intimate, conversational, with long rests. No vocals, no drums, no jump scare, no recognizable film or game theme. Loop-friendly sustained ending.

**Prompt F**：Original restrained cinematic underscore for the moment a body is found in a 1931 Chinese harbor inn office. Held breath rather than shock: low sustained cello and bowed bass, sparse felt piano notes, a thin high harmonic, a quiet unstable minor-second interval, slow 54 BPM, very quiet dynamics, long gaps. No sting, no jump scare, no drums, no vocals, no recognizable film or game theme. Seamless sustained ending suitable for looping.

**Prompt G**：Continuous naturalistic 1931 Chinese harbor at night: gentle water lapping against wooden pilings, low wind, a distant foghorn every so often, rope creaks, faint rain, no voices, no music, no sudden events, even level, loop-friendly field recording aesthetic.

**Prompt H**：Continuous naturalistic 1931 Chinese inn lobby at night: low fireplace crackle, a wall clock ticking, soft rain outside, old timber creaks, a faint draft, no voices, no music, no sudden events, even level, loop-friendly field recording aesthetic.

**Prompt I**：Continuous naturalistic 1931 Chinese inn dining room at night: quiet room tone, faint clink of porcelain and chopsticks, a wall clock, soft rain, wood settling, no voices, no intelligible conversation, no music, no sudden events, even level, loop-friendly field recording aesthetic.

**Prompt J**：Continuous naturalistic 1931 Chinese inn accounting office at night: rain against a closed wooden window, a clock ticking, faint paper shifts, a low oil lamp, old timber creaks, no voices, no music, no sudden events, even level, loop-friendly field recording aesthetic.

**Prompt K**：Continuous 42-second naturalistic room tone inside a 1931 inn accounting room at night. A steady quiet bed throughout: soft rain on a wooden window, constant low oil-lamp hum, continuous room air and faint old timber creaks, with sparse dry paper rustles distributed evenly across the whole take. No silence, no long gaps, no loud transients, no voices, no music, even level, loop-friendly field recording aesthetic.

## 序章与第一章人物配音（2026-11-10 生成）

覆盖 `p01_dock`–`p04_office` 与 `a01_found`–`a04_window` 中剧本已署名的人物对白。玩家“你”不配音；同一人物同一句只录一次，同一句在不同场景出现时复用同一条录音。共 38 条唯一台词、41 处场景引用；原文仍按 `readingPages` 的段落规则逐句显示，未录制的句子只显示文字。

| 人物 | 声线 / 参数 | 唯一台词 | 场景 |
| --- | --- | ---: | --- |
| 周文 | `Patient_Man`，speed 0.92，pitch −2，neutral | 8 | p02、p03 |
| 阿芸 | `Calm_Woman`，0.88，+1，sad | 7 | p03、p04 |
| 顾先生 | `Elegant_Man`，0.91，−2，sad | 9 | p04、a01–a03 |
| 陈掌柜 | `Deep_Voice_Man`，0.86，−3，neutral | 7 | p03、p04 |
| 阿水 | `Casual_Guy`，0.90，−4，neutral | 6 | p01、p04 |
| 老许 | `Imposing_Manner`，0.84，−3，neutral | 1 | p01 |

生成链：

```bash
node tools/make_voice_spec.mjs                 # 剧本对白 → tools/voice_spec.json
python tools/audio_pipeline.py --voice         # fal MiniMax Speech 2.8 HD
python tools/audio_pipeline.py --voice --reuse-raw --force   # 只重做响度与编码
python tools/render_voice.py                   # → voice-lines.generated.js / voice-assets.generated.js
```

`audio_pipeline.py --voice` 输出单声道 44.1 kHz、128 kbps MP3，响度统一到 −24 LUFS、峰值不超过 −3 dB，与 C01 的三句试听同一量级。每条请求 ID、时长、响度与 SHA-256 写在 `web/cinematic/audio/manifest.json` 的 `voices` 段；`tests/zc/audio-assets.test.mjs` 会比对哈希，文件或记录不一致时失败。生成文件由 `render_voice.py` 覆盖，不要手改。

费用按 MiniMax Speech 2.8 HD 每千字符 $0.10 估算，38 条共 476 字符，合计约 **$0.05**；实际账单以 fal 为准。本轮配乐、环境声与人物配音合计约 **$1.10**。

需要人工试听的重点：阿水与陈掌柜的年龄感是否合适，周文在 p02/p03 的重复句是否一致，阿芸在 p03 饭桌与 p04 账房的语气差别，以及配音与配乐的音量平衡。声线不一致时改 `tools/make_voice_spec.mjs` 的 `VOICES`，重新生成并渲染；不要手改生成文件。

## 账目调查小样

完整场景选 `c01_batch`（“五百八十四与两百”）。玩家阅读 B06 时预取三条素材；首次进入 C01 时，Python 场景 ID 触发翻账纸，随后播放原创调查音乐和账房雨夜环境声。`c02_724` 改用现有紧张合成声，`c03_roster_a/b` 改用现有沉郁合成声，因此即使同是账桌画面，也有明确的剧情层次。总设计者已试听并确认这组三条声音的方向。

四层混音：`bgm`、`ambience`、`sfx`、`voice` 各有增益节点，统一接入现有主音量。配乐与环境声分别渐变；素材解码后缓存，重复场景不叠加，同一场景的过期异步请求不会启动。拟音短暂压低配乐；人物说话时音乐与环境声自动让位。页面进入后台时仍由既有 AudioContext 暂停，用户手势后恢复；音乐与环境素材缺失或解码失败时回到合成声，人物配音失效时保留原文。录音素材使用 MP3，兼容主要桌面和移动浏览器；音乐与拟音的原始生成文件为 WAV。

### 素材来源与处理记录（2026-11-10）

| 文件 | 模型 / 请求 ID | 生成输入 | 估算费用 | 处理后响度 / SHA-256 |
| --- | --- | --- | ---: | --- |
| `ledger-inquiry.mp3` | Stable Audio 2.5，fal `01a1c52e-5b5f-79a2-ba76-9a4a3e6c529a`，seed `1097629166` | 55 秒，8 steps，guidance 3；下方 Prompt A | $0.20 | 52 秒，−24.2 LUFS；`26c662796036d1d8ba75d48f9c492a33dedcdfffbfea1860975c0b0553771583` |
| `ledger-room.mp3` | Sonilo v1.1，fal `01a1c52e-de33-7493-9c1e-abfa2d205642` | 42 秒，WAV；Prompt B | $0.0756 | 40 秒，−30.7 LUFS；`57f5d5f224445b514b9c0e2b5ee715178949eabd964648a6f882234c5b1ef5c7` |
| `ledger-paper.mp3` | Sonilo v1.1，fal `01a1c52f-0fda-7a51-8379-ff97d6f8de2e` | 3 秒，WAV；Prompt C | $0.0054 | 3 秒，−23.2 LUFS；`4238be45d3b94c9916b2c23bfcc073366ff9a9ce9218b25d56ab45164603c256` |

费用按生成时 fal 的公布费率估算：Stable Audio 每条 $0.20，Sonilo 每秒 $0.0018；合计约 **$0.281**。实际账单以 fal 为准。模型输出版本由 endpoint 名称与 request ID 固定，MP3 为本仓库加工版本。原始 WAV 未纳入网页包；可用请求 ID 在生成记录中追溯。三个 Prompt 都要求原创，不使用特定电影、游戏或歌曲的主题。

**Prompt A**：Original restrained cinematic underscore for a 1931 foggy Chinese harbor inn ledger investigation. A clerk and investigator compare 584 yuan against 200 yuan by lamplight. Slow 62 BPM, sparse felt piano, low cello and bowed bass, faint harmonium air, a subtle unresolved minor motif with long rests. Intimate room perspective, warm tape texture, quiet dynamics, seamless sustained ending suitable for looping under Chinese text reading. No vocals, no drums, no jump scare, no recognizable film or game theme.

**Prompt B**：Continuous naturalistic 1931 harbor inn ledger room at night: soft rain against closed wooden window, distant muted harbor water and wind, low candle and old timber creaks, subtle room air, spacious but intimate, no voices, no music, no sudden events, even level, loop-friendly field recording aesthetic.

**Prompt C**：Single close perspective realistic handling of an old thick paper ledger: one page lifted, slowly turned, and laid flat on wooden desk, faint dry fiber rustle, quiet room, no voice, no music, clean isolated foley with brief silence at start and end.

处理流程：BGM 首尾交叉 3 秒并衰减 10.5 dB；环境声首尾交叉 2 秒并增益 16 dB；拟音增益 20 dB 并限幅至 0.89。三条素材编码为 MP3。响度以 FFmpeg `ebur128=peak=true` 测得。后续序章与第一章改用 `tools/audio_pipeline.py` 的循环与增益流程，见上一节。所有素材播出前仍需人工检查循环接缝、音色与混音；数值检测不能代替听感。

### 授权记录

- Stable Audio：Stability 的[声音授权说明](https://kb.stability.ai/knowledge-base/stable-audio-commerical-and-usage-licensing)明确允许生成输出嵌入游戏及网页应用，受其条款约束；[API FAQ](https://platform.stability.ai/faq)说明 API 输出可商用，需尊重第三方权利。
- Sonilo：其[授权页](https://sonilo.com/licensing)说明 API 生成输出可以在产品中商业使用，具体使用受[条款](https://sonilo.com/terms-of-service)约束；本样本经 fal 的 Sonilo endpoint 生成。发布前保留请求记录与本表，若课程项目改为商业发行，再核对届时的服务条款。
- fal：[服务条款](https://fal.ai/legal/terms-of-service)和模型页面共同适用。素材不单独售卖，也不声称生成输出具有排他版权。

## 人物配音首批试听（C01、B03、B05）

序章与第一章的完整配音见上一节；这里保留最早三条试听的声线与生成记录，用于对照。人物配音跟随玩家逐段阅读：只在 Python 快照给出的场景、剧本原句和明确标注的说话人同时匹配时播放。玩家点击继续会停止当前句；声音结束不会自动翻页。未录制的段落继续显示完整文字。为了保留玩家代入，本轮不替“你”指定固定嗓音。

| 人物 | 声音方向与剧情依据 | 本轮接入的原句 |
| --- | --- | --- |
| 周文 | 负责记账、熟悉每一笔数字；发现差额时克制而迟疑，不能把他提前演成已自白的凶手 | C01“也许是记到别处了。” |
| 阿芸 | 工钱未结、正在等试工回信；请求私谈时轻而疲惫，保护隐私时仍有主见 | B03“信里的私事，能不念给他们听吗？” |
| 顾先生 | 欠据与合伙人的催告压在身上；外表整洁，陈述后果时声音逐渐失去从容 | B05“那封信送到我合伙人手里，我后天收不收得到钱都没用了。他会先把信用收回去。” |
| 陈掌柜、老许、阿水 | 分别是待交割旅馆的掌柜、值房见证人与短渡船家 | 暂未生成；后续按各自陈述与出场时长试听 |

最终选用 MiniMax Speech 2.8 HD，fal endpoint `fal-ai/minimax/speech-2.8-hd`，`language_boost=Chinese`，输出 MP3 44.1 kHz / 128 kbps / mono。模型页面标有[商业使用](https://fal.ai/models/fal-ai/minimax/speech-2.8-hd/api)，使用还须遵循 [fal 服务条款](https://fal.ai/legal/terms-of-service)及适用的模型条款。按生成时公布费率每千字符 $0.10 估算，实际账单以 fal 为准。没有克隆真人声音。

| 文件 | 生成请求 / 原句 Prompt | 声线参数 | 估算费用 / SHA-256 |
| --- | --- | --- | --- |
| `voice-zhou-c01.mp3` | `01a1c543-7ad2-7ac3-8153-2822e3a128f3`；也许是记到别处了。 | `Patient_Man`，speed 0.92，pitch −2，neutral，vol 1 | $0.0009；`483f82af43fa6e23b15ebc30e85cfbe022c67f4b16a7a3ecce2223f7f73b448b` |
| `voice-ayun-b03.mp3` | `01a1c545-5b88-7073-8fa1-844d242df4e7`；信里的私事，能不念给他们听吗？ | `Calm_Woman`，speed 0.88，pitch +1，sad，vol 0.8 | $0.0015；`769364142883464957dd885567f0ecc252d025ec560c5584810b9f729ee3c1ce` |
| `voice-gu-b05.mp3` | `01a1c543-e5e8-7750-a2bb-3755103bab7f`；那封信送到我合伙人手里，我后天收不收得到钱都没用了。他会先把信用收回去。 | `Elegant_Man`，speed 0.91，pitch −2，sad，vol 1 | $0.0036；`999a3c60d28ecf686aa36999983fb377e3985d6abbc95ce3ac56af0dc6a4e04c` |

周文第一版 `Decent_Boy`（`01a1c540-a0f3-7212-b63b-76a2af87b8e2`）被总设计者指出“出戏”，改用第二版；阿芸第一版 `Calm_Woman` / speed 0.96 / neutral（`01a1c541-8fe1-7c63-935e-38358d4211f4`）改为更轻、稍显疲惫的第二版。另有周文 C02 两句连读试听（`01a1c541-311e-7d90-9a94-787d5571c016`，`Decent_Boy` / speed 0.9 / pitch −2 / sad，Prompt“今年的放今年。那一年的，放那一年。”）与顾先生不完整句试听（`01a1c541-bed1-79d1-8917-4ee9a27b7959`，`Elegant_Man` / speed 0.91 / pitch −2 / sad，Prompt“那封信送到我合伙人手里，我后天收不收得到钱都没用了。”），均未进入网页包。这四次试听估算费用 $0.0067；本轮七次配音生成总计约 $0.0127，连同音乐和拟音约 **$0.294**。总设计者已确认周文与阿芸的第二版声线；顾先生声线留待后续实机试听。

## 后续验收与分工

继续用耳机和手机扬声器试听 C01 连续阅读、C01→C02 的切换、静音/恢复、退后台再进入、断网时的合成声降级。若循环接缝或拟音不自然，先修这三条；确认后再考虑其他幕。自动测试覆盖剧情映射、加载失败、旧请求取消和不重复播放，浏览器测试负责真实网页状态。

可交给 DeepSeek 的独立工程任务：在不改 `app.js`、`stage.js`、`units.js`、Python 共享接口的前提下，完善 `audio-assets.js` 的素材元数据校验，并在 `tools/` 新增一个只依赖 FFmpeg 的处理命令，输入 WAV，输出 MP3 与响度/峰值/哈希清单；测试写在 `tests/zc/`。交付时提供命令、真实运行结果和失败输入处理。Codex 负责审核与接入。当前环境没有 DeepSeek 接口或凭据，此任务尚未实际委派或合并。
