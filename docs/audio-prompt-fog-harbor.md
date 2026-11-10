# 《雾港旧案：未结的账》序章与第一章 · 声音生成提示词

这组提示词按“先定选角，再逐场景生成”的方式写。`【】` 是给模型或配音演员的方向，不读出来；引号内是剧本原句。每个场景都能单独生成，也可以按顺序拼成一集。范围是序章 `p01`–`p04` 与第一章 `a01`–`a04`，与已录制的配乐、环境声和人物配音一致。

## 一、选角与声线

先固定这六条声线，所有场景沿用。不要把“你”配成固定角色，保留玩家代入。

| 编号 | 人物 | 年龄 / 身份 | 口音 | 音色与语气 |
| --- | --- | --- | --- | --- |
| 男声 A | 周文 | 二十出头，旅馆记账青年 | 南方口音，吐字清楚 | 嗓音清而偏低，语速偏慢，礼貌、克制；被追问时更轻，句子收得短，不主动解释 |
| 女声 A | 阿芸 | 二十岁上下，旅馆帮工 | 南方口音，尾音轻 | 声音轻、干、带疲惫，不软弱；说到工钱和私事时更慢、更硬，怕被听见但不躲 |
| 男声 B | 顾先生 | 三十多岁，欠债的商人 | 略带北方口音的普通话 | 清亮偏薄，体面，习惯把焦虑压平；被逼到墙角时气息变浅，后期沙哑 |
| 男声 C | 陈掌柜 | 五十岁上下，即将交割旅馆的掌柜 | 南方口音，带笑 | 沙哑、温和、慢，像常年招呼客人；说到欠据和期限时低下去，笑意先收 |
| 男声 D | 阿水 | 四十岁上下，短渡船家 | 地方口音重，短句 | 粗粝、短促，像在风里说话；不热情，但每句都实在 |
| 男声 E | 老许 | 五十多岁，值房看夜人 | 本地口音，干、慢 | 谨慎、低、少起伏；隔着窗或门说话，字与字之间留一点停顿 |
| 旁白 | “你” | 商行调查员 | 不指定 | 游戏内不配音；若做纯音频版，用中性、低沉、克制的旁白，只读动作与叙述，不替角色演 |

**选角提示**：这是 1931 年中国雾港的旅馆，不是现代都市；不要用播音腔、译制片腔或夸张的悬疑腔。所有人说话都像在压低声音，怕吵醒楼上的人。

## 二、全剧声音基调

- 时间与地点：1931 年深秋，雾港，海鸥旅馆。雨刚停，雾从水面涨上来；室内只有炉火、油灯、座钟和旧木头。
- 配乐：以 felt piano（毡音钢琴）、低音大提琴、弓弦低音、簧风琴、低音单簧管为主，慢速 54–64 BPM，小调，留白多；不用鼓、不用现代合成器、不用惊吓音。
- 环境声：雾笛、水拍木桩、雨、座钟、炉火、碗筷、翻纸、木地板、远处的船铃。每一声都要对应画面里真实发生的动作。
- 混音：人物对白最前，环境声退后，配乐在人物说话时自动让位；音乐不抢台词，不用突然的强音。
- 禁止：手机震动、电话按键音、电子鼓、synth lead、电贝斯、现代城市噪音、可识别的电影或游戏主题。

---

## 三、场景提示词

### 1. 雾港码头（`p01_dock`）

【画面】夜，最后一班外海客船靠岸；石阶积水，雾到膝边；提灯、木牌、小艇。
【环境声】水拍木桩、远处雾笛、湿石阶上的脚步、绳索轻响、船身碰垫木。
【配乐】克制的开场：毡音钢琴单音、低音大提琴长音、远处簧风琴，58 BPM，小调，留大量空白；雾笛出现时不加厚，让它自己退远。
【Music prompt】Original restrained cinematic opening cue for a 1931 foggy Chinese harbor at nightfall. Last ferry nudging the pier, distant foghorn, wet stone and rope. Sparse felt piano, low sustained cello, faint harmonium, slow 58 BPM, minor mode, long silences. Intimate, humid, patient. No vocals, no drums, no jump scare, no recognizable film or game theme. Loop-friendly.

【对白】

阿水【中年船家，站在风里，短促、不客套，像顺口提醒】：
“去旅馆，走前头那条路。后院的石阶涨潮淹了，别图近。”

你【看了一眼小艇，没有出声】：（留白）

阿水【补一句，像在解释规矩，平淡】：
“这船只走港里。”

阿水【看向外头的浪，声音更低一点】：
“外头那道浪，换谁坐都一样。”

阿水【自我介绍，语速稍缓，认真】：
“我叫阿水。明早若要过海，先来问风。”

【可选分支】

阿水【抬手指出方向，句子短】：
“沿油灯走，几分钟就到；后窗那边得坐短渡。”

老许【从值房窗内传出，隔着雨，干而慢】：
“电话还通。船什么时候开，要看水上。”

---

### 2. 海鸥旅馆 · 大堂（`p02_lobby`）

【画面】夜，炉火弱；柜台、寄存簿、湿伞、干毛巾；楼梯口的灯。
【环境声】炉火轻响、座钟嘀嗒、门外雨声、纸页翻动、笔尖划纸、湿伞滴水。
【配乐】室内温度上来，但仍不安：毡音钢琴与簧风琴，低音大提琴在句尾托一下，64 BPM；不要旋律性太强。
【Music prompt】Original restrained cinematic underscore for the lobby of a 1931 Chinese harbor inn at night. Warm but uneasy: felt piano, muted harmonium, low cello, soft double bass, a faint clock-like wooden pulse rather than drums, 64 BPM, shifting between minor and its relative major. Candlelit, intimate, conversational, with long rests. No vocals, no drums, no jump scare, no recognizable film or game theme.

【对白】

周文【起身接伞，客气、谨慎，先报身份】：
“商行来的？周文。我替掌柜记账。”

周文【低头翻寄存簿，轻描淡写】：
“邻行串过来的。”

周文【把两张签推过来，认真但不逼人】：
“请你自己对一下。明早换了掌柜，这样的小错就说不清了。”

【可选分支】

周文【试探，语气仍客气】：
“原始流水也带来了？”

你【平静，公事公办】：
“供货商的书面确认在这里，完整流水明早由查验员带来。旧代管款的申请材料也在。”

周文【收住，点头，不再追问】：
“那就齐了。”

周文【很短，像把话收进账本】：
“明早。”

---

### 3. 一张饭桌（`p03_dinner`）

【画面】夜，饭厅；楼梯、饭桌、鱼、汤碗、薄账；顾先生的外套与怀表。
【环境声】楼梯脚步、椅子拖动、瓷碗轻碰、筷子、座钟、窗外雨、怀表盖合上。
【配乐】家常里的不安：毡音钢琴、低音大提琴、簧风琴，62 BPM；阿芸开口时音乐退到只剩低音。
【Music prompt】Original restrained cinematic underscore for the dining room of a 1931 Chinese harbor inn at night. Warm but uneasy: felt piano, muted harmonium, low cello, soft double bass, a faint clock-like wooden pulse rather than drums, 62 BPM, restrained dynamics. Candlelit, intimate, conversational, with long rests. No vocals, no drums, no jump scare, no recognizable film or game theme.

【对白】

陈掌柜【从楼梯下来，先寒暄，温和而有分寸】：
“资料等我整理好，十一点后放在账房。你睡前来取，带回房慢慢看。”

陈掌柜【把鱼往桌心推，家常，像在留客】：
“今晚先吃饭。”

陈掌柜【对阿芸，带笑，但不容拒绝】：
“坐下吃。明天人多。”

阿芸【没有动筷，直接问，压着不安】：
“明天交割完，欠的那半月工钱也一起结吗？”

陈掌柜【笑了一下，轻，像在哄】：
“你还怕我少你？”

周文【把薄账移到手边，插话，眼睛不看人】：
“工钱在另一册，我记着。”

阿芸【平静，带刺，慢】：
“上个月也是你记着。”

阿芸【更慢，像在一笔一笔数】：
“九月下半月。写上日期。”

阿芸【起身，疲惫，不请求】：
“我要走了。工钱关系到路费。”

阿芸【对调查员，克制，把边界说清】：
“你查数就好，不用替我劝他。”

【可选分支】

周文【试探】：“原始流水也带来了？”
你【平静】：“供货商的书面确认在这里，完整流水明早由查验员带来。旧代管款的申请材料也在。”
周文【收住】：“那就齐了。” / “明早。”

---

### 4. 还没有关上的账房（`p04_office`）

【画面】夜，账房；交割清单、铜镇纸、旧合影、待寄的信；门口；廊下。
【环境声】雨打窗、油灯轻响、纸页、脚步、怀表、门轴。
【配乐】低而稳的思索层：低音大提琴、弓弦低音、稀疏钢琴；顾先生开口时不要加悬疑音效，只让低音沉下去。
【Music prompt】Original restrained cinematic underscore for a 1931 Chinese inn accounting office at night. Low sustained cello and bowed bass, sparse felt piano, a quiet room with rain at the window, slow 58 BPM, minor mode, very restrained dynamics. No vocals, no drums, no sting, no jump scare, no recognizable film or game theme.

【对白】

陈掌柜【介绍镇纸，怀旧，带笑】：
“开店那年买的。坏过一次，还能使。”

顾先生【站在门口，声音压低，急切但保持体面】：
“那封信，能不能后天再寄？我的货款后天到。”

陈掌柜【笑收了，一字一句，冷下来】：
“顾兄，我等的是你还钱，不是你每次换一个日子。欠据明早跟信走。”

顾先生【看见你，停住，整理领口，恢复体面】：
“我们另谈。”

阿水【从门口探头，轻声，快】：
“信在值房，老许今夜当班。”

陈掌柜【看着阿水的背影，低声，像自言自语】：
“旧船行的人。”

---

### 5. 按约取账（`a01_found`）

【画面】夜更深；客房灯芯、楼梯口、虚掩的账房门、半扇后窗、伏在桌边的陈掌柜。
【环境声】座钟长针、楼梯脚步、门轴、雨、灯焰被风吹动、纸页、布料轻响。
【配乐】屏住呼吸，不是惊吓：低音大提琴长音、弓弦低音、稀疏钢琴、很细的高频泛音，54 BPM；发现尸体时不要强音，让低频停在那里。
【Music prompt】Original restrained cinematic underscore for the moment a body is found in a 1931 Chinese harbor inn office. Held breath rather than shock: low sustained cello and bowed bass, sparse felt piano notes, a thin high harmonic, a quiet unstable minor-second interval, slow 54 BPM, very quiet dynamics, long gaps. No sting, no jump scare, no drums, no vocals, no recognizable film or game theme.

【对白】

你【在楼梯口，压低声音】：
“还没睡？”

顾先生【按住衣袋，像刚从书里抬头，故作平常】：
“看书，看得忘了时辰。”

顾先生【试探，关心，但更像在确认你看见了什么】：
“掌柜也没歇？”

【其余为动作与发现，不配音；不要给尸体配任何声音。】

---

### 6. 谁先走进来（`a02_door`）

【画面】账房门口；阿芸扶门框、周文从另一头走来、顾先生最后出现；门外的雨。
【环境声】脚步、门框轻响、呼吸、雨、远处座钟、纸被风吹动。
【配乐】几乎撤掉旋律，只留低音脉冲与不稳定的空气声，56 BPM；人物说话时音乐让位。
【Music prompt】Original restrained cinematic underscore for a doorway confrontation in a 1931 Chinese inn at night. Low pulsing bass, sparse cello harmonics, quiet room air, 56 BPM, no melody, no drums, no sting, no jump scare, no vocals, no recognizable film or game theme.

【对白】

周文【从另一头走来，压着慌，先用惯常的安抚语气】：
“别围在这里。掌柜有时候会晕——”

周文【看见血，话停住；这一句不要演，留半句】：
（停顿）

顾先生【望向翻开的簿子，声音断了一下】：
“那张纸……”

你【平静，追问】：
“什么纸？”

顾先生【立刻改口，掩饰，语速略快】：
“我说，桌上的纸别吹散了。”

顾先生【退半步，提议，怕被单独怀疑】：
“一起等吧。谁也别单独进去。”

---

### 7. 灯下残页（`a03_lamp`）

【画面】账房灯下；被撕的凭据簿、待寄的信、纸背浅字；顾先生盯着你的手。
【环境声】翻纸、灯芯、信封、雨、笔尖、远处钟声。
【配乐】极简：钢琴单音、细高频泛音、低音持续音，60 BPM；翻纸声出现时音乐退开。
【Music prompt】Original restrained cinematic underscore for reading a torn ledger by lamplight in a 1931 Chinese inn. Sparse felt piano, a thin high harmonic, low sustained cello, quiet paper sounds, 60 BPM, very restrained, long rests. No vocals, no drums, no sting, no recognizable film or game theme.

【对白】

顾先生【盯着你的手，试探，尽量平静】：
“你要抄多少？”

你【不抬头，平静】：
“先把看见的都抄下。”

顾先生【不安，声音更低】：
“包括没看全的？”

你【肯定，简短】：
“没看全，也会写明。”

---

### 8. 窗与第一份假说（`a04_window`）

【画面】账房窗边；后窗扣、窗台湿泥、地板鞋印、后院水线、岸壁擦痕。
【环境声】雨、窗框、茶碗、脚步、泥水、远处水声。
【配乐】问题开始堆积：低音持续音、稀疏钢琴、很轻的钟摆脉冲，58 BPM；不要给出答案式的收束。
【Music prompt】Original restrained cinematic underscore for examining a window and forming the first hypothesis in a 1931 Chinese inn at night. Low sustained bass, sparse felt piano, faint clock-like pulse, rain at the window, 58 BPM, unresolved minor mode, no drums, no vocals, no sting, no recognizable film or game theme.

【对白】

阿芸【在门口，犹豫，先看了周文一眼】：
“我送茶的时候，后窗只留着一道缝。”

你【平静，追问】：
“几点？”

阿芸【停了一下，低声，像在确认自己没说错】：
“钟响过后。”

---

## 四、如果要合并成一条提示词

给只接受单条提示词的工具时，把下面这段放在最前，再接上对应场景的【对白】：

> 1931 年中国雾港，海鸥旅馆，雨夜。原创中文音频剧，克制、写实、低音量。六条固定声线：周文（青年男声，南方口音，清而偏低，礼貌克制）、阿芸（年轻女声，南方口音，轻而疲惫，有主见）、顾先生（中年男声，略带北方口音，体面、压着焦虑）、陈掌柜（五十岁男声，南方口音，沙哑温和）、阿水（中年男声，船家，粗粝短促）、老许（五十多岁男声，干、慢、谨慎）。“你”不配音。配乐只用毡音钢琴、低音大提琴、弓弦低音、簧风琴、低音单簧管，54–64 BPM，小调，留白；环境声用雾笛、水、雨、座钟、炉火、碗筷、翻纸、木地板；不用鼓、不用现代合成器、不用惊吓音。人物对白最前，音乐在说话时让位。不要念出【】里的方向，不要念出说话人名字。

## 五、使用与验收

- 每个场景单独生成时，先放【环境声】，再进【配乐】，最后进【对白】；对白之间保留 0.4–0.8 秒，让呼吸和动作有位置。
- 同一人物在不同场景的音色、语速、口音要一致；周文在 `p02`/`p03` 的重复句应当听起来是同一个人在同一天晚上说的。
- 生成后先听三件事：阿水与陈掌柜的年龄感是否拉开；阿芸在饭桌与账房的语气是否有差别；人物说话时配乐是否真的退下去了。
- 若用于游戏内播放，仍以 `voice-cues.js` 的“场景 + 人物 + 原句”匹配为准；提示词只用于生成素材，不改变剧情、条件或结局。
