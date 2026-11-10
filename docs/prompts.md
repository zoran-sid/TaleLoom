# 开工提示词（第二轮：影像模式 + 失败惩罚）

第二轮的分工、验收与临时约定见 [任务安排第 0 节](team-tasks.md#0-当前进度与第二轮任务)。下面的提示词直接交给各自的 AI；先贴“通用开头”，再贴自己的一段。

## 通用开头

```text
我是 <缩写>，负责 TaleLoom 的 <模块>。第二轮主线是“影像模式 + 失败惩罚”。
请先读 AGENTS.md、docs/team-tasks.md 第 0 节（0.1 我的任务、0.2 临时约定）、docs/contracts.md，
以及 stories/film/fog_harbor_film/README.md；在 https://taleloom.zoranzhou.com/cinematic 实际玩一遍影像版。
从最新 develop 开 <缩写小写>/<主题> 分支，保留已有修改。先写会失败的测试，再实现；只改自己负责的文件，
改共享接口走 contract PR，同一个 PR 里修好受影响的代码和测试。
提交前跑：本模块测试、python -B -m unittest discover -s tests -t .、python main.py validate、
npm run build && npx playwright test。推送后到 <分支名>.taleloom.zoranzhou.com/cinematic 试玩预览，
PR 写清改了什么、真实验证结果、对他人的影响和 AI 使用。
```

## YHT

```text
任务：把影像版的临时约定改成剧本正式字段（与 ZQO 配合，走 contract PR）。
1. 结局 ending.kind：normal（默认）或 failure，取代结局 id 的 fail_ 前缀；
2. 场景 checkpoint：存档点名称，取代 on_enter 里的 {"say": "【存档点】名称"}；
3. 场景 art：画面键（如 lobby、office），取代 web/cinematic/app.js 里的 ART 映射表。
在 model.py／loader.py／validator.py 解析并校验：kind 只能取这两个值；存档点名称在剧本内唯一；
failure 结局必须由选择进入；meta.linear 为 true 的剧本场景图无回路（把 tests/integration/test_film_stories.py
的规则下沉到 validator）。旧剧本不改也要通过；每条规则用迷你剧本写通过例和失败例。
同一个 PR 迁移 stories/film/fog_harbor_film/story.json，并请 ZC 审阅。
```

## ZQO

```text
任务：会话与快照支持新字段，并把“回退”做成会话能力，让桌面和网页共用。
1. ViewSnapshot 增加可选字段：画面键、结局类型、当前存档点；旧前端忽略新字段也能运行；
2. GameSession 提供存档点列表、回到存档点、回到上一个选择（整局机会数可设置，默认 3），
   失误与回退次数随存档保存；快照读取仍不推进回合、不抽随机数；
3. 先在 tests/integration/test_ui_contract.py 的约定测试里加用例，再实现。
完成后由 ZC 把 web/cinematic 改用会话能力、ZRS 接桌面；用 tests/integration/test_film_stories.py
和浏览器测试确认影像版行为不变。
```

## ZRS

```text
任务：文字版与桌面接上影像模式和失败惩罚。
1. 书架（web/ui/、index.html）加“影像模式”入口，链接 /cinematic，卡片标注“互动影像”；
   顺带修手机竖屏时页眉右侧文字折行；
2. 桌面 GUI：失败结局提供“回到上一个选择”和“回到存档点”，显示关键节点自动存档列表，
   规则只经会话接口（ZQO 的能力合入前可先用影像页同样的标准存档导出／恢复实现）；
3. 检查影像模式的键盘操作、减少动态效果、字幕可读性和手机布局，问题写 issue 给 ZC；
4. 与 ZC 一起解决 #15：CI 用 xvfb 运行窗口测试，修好其中失败的用例。
```

## LQ

```text
任务：《深空回声 · 影像版》，以及把自动存档接进正式存储。
1. 新建 stories/film/deep_space_film/（目录名与 id 相同）：线性分支，每个选择都进入下一段剧情；
   氧气、电量是公开资源，耗尽即任务失败（结局 id 以 fail_ 开头，YHT 的字段合入后改用 ending.kind）；
   至少 5 个结局（含 2 个失败结局）、3 个存档点，每个结局一个通关脚本；
   参照 stories/film/fog_harbor_film/README.md 写剧情结构说明；
2. 场景 id 以影像模式已有的飞船画面键开头即可自动套用画面（如 airlock、airlock_jam）：
   bay（休眠舱）、corridor、toolroom、airlock、energy、comms、observatory、space（舰外）；
   用 /cinematic?story=deep_space_film 试玩，氧气、电量会显示在画面左上角；
   需要新画面时开 issue 写清场景和想要的画面，交给 ZC；
3. 关键节点自动存档改存进 web/storage/ 与桌面存储，取代影像页临时使用的 localStorage
   （接口与 ZC 协调）；
4. 随机探索覆盖 stories/film/ 下的剧本。
```

## ZC

```text
任务：影像模式播放器、画面与发布。
1. 飞船场景画面与画面内资源条已完成（/cinematic?story=deep_space 可试玩）；按 LQ 的深空影像版补画面与失败结局；
2. YHT／ZQO 的字段合入后，播放器改读 ending.kind、checkpoint、art，删除 ART 表、fail_ 前缀与
   “【存档点】”提示的解析；改用会话的回退能力；
3. 与 ZRS 解决 #15；
4. develop 验收后开 develop → main 的发布 PR。Cloudflare 生产分支已是 main（2026-11-10 核实），无需重复切换；
5. 《未结的账》按剧本目录的最新版说明维护：已取消交互核验，保留剧情选择；九处分支已确认，音画保留现有方案，外部素材列为后续增强。
```
