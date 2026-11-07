# 开工提示词

每位成员开工时把自己那一段交给 AI（Claude Code、Cursor 等），AI 在仓库根目录工作。通用规则在 [AGENTS.md](../AGENTS.md)，AI 会自动读取。

## 通用开头（每人都加）

```text
我是 <缩写>，负责 TaleLoom 的 <模块>。请先读 AGENTS.md、docs/team-tasks.md 第 1–4 节中我的部分、
docs/contracts.md、docs/requirements.md 和 docs/handoffs/<缩写小写>.md。
运行 git status、git log -5 --oneline，从最新 develop 创建 <缩写小写>/<主题> 分支。
工作方式：先在 docs/requirements.md 写需求行，再写会失败的测试，再写实现；
只改我负责的文件；需要改共享接口时按 docs/contracts.md 第 5 节走 contract PR。
完成后运行我的模块测试和全部测试，更新交接记录和 docs/ai-usage.md，推送并开 PR 到 develop，
审阅人按 docs/team-tasks.md 第 6 节。
```

## YHT

```text
本轮目标：team-tasks 4.1 必做第 1–2 项。
1. 补全 docs/story-format.md：每个字段的类型、必填、示例，加“剧本作者快速上手”一节。
2. 在 validator 中加入条件/效果参数类型校验（var、add_var、set_var、组合条件等），
   每条规则写通过例和失败例，错误信息给出位置和修改建议。
不要修改两个剧本的 JSON；发现剧本问题开 issue 给 ZC 或 LJ。
```

## ZQO

```text
本轮目标：team-tasks 4.2 必做第 1、3 项，并写架构说明。
1. 文本插值：场景文字中的 {vars.名称} 显示时替换，未知占位符不崩溃。
2. 可复现随机：{"chance": 百分比} 条件，种子保存在 GameState，读档和回放结果一致。
   GameState 新增字段属于 contract 改动，同一个 PR 内修好 save 测试并 @LJ。
3. 在 docs/contracts.md 补充架构图和一次命令的处理时序，供第 1 页幻灯片使用。
```

## ZRS

```text
本轮目标：team-tasks 4.3 必做第 1–2 项。
1. 解析“把A用在B上”“use A on B”“检查 X”等句式，Command.args 带两个参数；
   puzzle 插件支持 use A on B。
2. 歧义时列出候选，拼写接近时用 difflib 给建议。
每种句式写正常、边界、异常测试；parser 中适合的例子写成 doctest。
```

## ZC

```text
本轮目标：team-tasks 4.4 必做第 1 项中的“深入搜证”和“审问”，并规划剧本 A 扩写。
1. mystery 插件：已发现线索可深入调查得到下一级线索；嫌疑人话题列表，出示线索解锁新证词。
   数据段格式写进 docs/story-format.md 第 6 节。
2. 在 stories/fog_harbor/README.md 写扩写大纲（人物秘密、误导线索、≥4 个结局），
   然后扩写剧本，每个结局一个通关脚本。
3. 维护 tests/integration/，保证 develop 始终可演示。
剧情、人物、文字必须原创，只借鉴剧本杀的玩法机制。
```

## LJ

```text
本轮目标：team-tasks 4.5 必做第 1–2 项。
1. 多存档槽（“存档 2”“读档 2”）、自动存档、列出存档；与 ZRS 协商 CLI 中的命令格式。
2. 随机探索测试：从起点随机选择合法命令走 N 步、重复 M 次（固定种子可复现），
   断言不崩溃、状态合法；对两个剧本都跑，把结果写进 docs/testing.md。
3. 在 stories/deep_space/README.md 写扩写大纲（氧气 + 电量、≥3 个结局），然后扩写剧本。
```
