# 需求与测试对应表

课程“优良”等级要求“符合规格与测试要求”。每条需求有编号、负责人和验证它的测试。范围变更及时同步需求，最终阶段按真实测试补齐结果。状态：✅ 已实现并通过测试 / 🔲 计划中。

编号前缀：`Y` YHT、`Q` ZQO、`R` ZRS、`C` ZC、`L` LQ、`N` 非功能需求。

## 功能需求

| 编号 | 需求 | 负责 | 验证 | 状态 |
| --- | --- | --- | --- | --- |
| FR-Y1 | 从目录或文件加载 JSON 剧本 | YHT | `tests/yht/test_loader.py::LoadRealStoriesTest`、`FileErrorsTest` | ✅ |
| FR-Y2 | 格式错误给出位置（如 `$.scenes[1].text`）与原因，不抛出未处理异常 | YHT | `test_loader.py::ParseTest` | ✅ |
| FR-Y3 | 校验跳转目标、物品、未知条件/效果（提示需要启用的插件） | YHT | `tests/yht/test_validator.py` | ✅ |
| FR-Y4 | 校验可达性与结局存在性（全局跳转计入可达） | YHT | `test_validator.py` | ✅ |
| FR-Y5 | 条件与效果参数类型校验 | YHT | — | 🔲 |
| FR-Y6 | 陷阱环、用尽后无出口场景、未使用物品检查 | YHT | — | 🔲 |
| FR-Q1 | 按编号或选项 id 选择，条件选项、一次性选项 | ZQO | `tests/zqo/test_engine.py::EngineFlowTest` | ✅ |
| FR-Q2 | 内置条件与效果；插件可注册新条件/效果，重名拒绝 | ZQO | `tests/zqo/test_rules.py` | ✅ |
| FR-Q3 | 每回合效果与触发器；只有消耗回合的操作推进回合 | ZQO | `test_engine.py::TurnRulesTest` | ✅ |
| FR-Q4 | 跳转循环检测，结局后拒绝继续操作 | ZQO | `test_engine.py` | ✅ |
| FR-Q5 | 文本插值 `{vars.x}` | ZQO | — | 🔲 |
| FR-Q6 | 条件化场景文字 `variants` | ZQO | — | 🔲 |
| FR-Q7 | 可复现随机（种子存于状态） | ZQO | — | 🔲 |
| FR-R1 | 全角/半角、大小写统一；编号、选项文字、唯一子串匹配 | ZRS | `tests/zrs/test_parser.py`（含 doctest） | ✅ |
| FR-R2 | 中英文动词别名；中文动词可不加空格 | ZRS | `test_parser.py` | ✅ |
| FR-R3 | 命令行界面：编号菜单、存档/读档/退出、EOF 正常退出 | ZRS | `tests/zrs/test_cli.py` | ✅ |
| FR-R4 | 道具组合与使用（`puzzle` 插件） | ZRS | `tests/zrs/test_puzzle.py` | ✅ |
| FR-R5 | 可选：“把 A 用在 B 上”/“use A on B” 句式 | ZRS | — | 🔲 |
| FR-R6 | 可选：歧义输入列出候选；拼写接近时给建议 | ZRS | — | 🔲 |
| FR-R7 | 可选：状态栏、按显示宽度换行、可关闭颜色 | ZRS | — | 🔲 |
| FR-C1 | 线索获取、笔记查看（`mystery` 插件） | ZC | `tests/zc/test_mystery.py` | ✅ |
| FR-C2 | 指认：时机条件、别名、按证据决定结局、默认结局 | ZC | `test_mystery.py` | ✅ |
| FR-C3 | 深入搜证、审问、分幕、指认理由 | ZC | — | 🔲 |
| FR-C4 | 剧本 A 全部结局可通关 | ZC | `tests/integration/test_stories.py`、`stories/fog_harbor/walkthroughs/` | ✅（序章 3/3） |
| FR-L1 | 存档读档；损坏、缺字段、其他剧本的存档给出明确错误 | LQ | `tests/lq/test_save.py` | ✅ |
| FR-L2 | 剧本修改后读旧档给出提示 | LQ | `test_save.py` | ✅ |
| FR-L3 | 通关脚本回放与结局覆盖率 | LQ | `tests/lq/test_replay.py` | ✅ |
| FR-L4 | 多存档槽、自动存档、存档列表 | LQ | — | 🔲 |
| FR-L5 | 随机探索测试 | LQ | — | 🔲 |
| FR-L6 | 剧本 B 全部结局可通关 | LQ | `tests/integration/test_stories.py`、`stories/deep_space/walkthroughs/` | ✅（序章 2/2） |

## 非功能需求

| 编号 | 需求 | 负责 | 验证 | 状态 |
| --- | --- | --- | --- | --- |
| NFR-1 | Python 核心与桌面使用标准库，GUI 需 Tcl/Tk；网页依赖独立管理 | 全体 | CLI 已通过 CI；GUI／网页隔离待验证 | ✅ CLI；🔲 新端 |
| NFR-2 | 任何玩家输入都不导致程序崩溃 | ZRS、LQ | `test_cli.py`；随机探索（FR-L5） | ✅ 部分 |
| NFR-3 | 每条命令的处理在 100 ms 内完成（演示电脑） | ZQO | 计划在 LQ 的随机探索中计时 | 🔲 |
| NFR-4 | 存档写入中断不损坏旧存档（先写临时文件再替换） | LQ | `test_save.py::test_no_temp_file_left_behind` | ✅ |
| NFR-5 | 新增剧本无需修改 Python 代码 | YHT、ZQO | 两个剧本共用引擎；`test_stories.py::test_two_stories_on_one_engine` | ✅ |
| NFR-6 | 首次使用有操作提示，所有命令可通过“帮助”查到 | ZRS | 组外试玩记录 | 🔲 |

## 新增 GUI／网页／异步协作需求

依据：[GUI／网页实施要求](gui-web-plan.md)。下列尚未实现项的验证列为验收计划；样例测试通过不等于真实界面已实现。

| 编号 | 需求 | 负责 | 验证 | 状态 |
| --- | --- | --- | --- | --- |
| FR-G1 | VS Code 运行 main.py 无参数弹出 GUI | ZC、ZRS | Windows／macOS 启动与中文显示 | 🔲 |
| FR-G2 | 两个剧本全部核心操作可点击完成 | ZRS、ZC | 桌面真实剧本通关 | 🔲 |
| FR-G3 | 共享展示／动作／会话／存储接口和独立测试替身 | YHT、ZQO、LQ、ZC | `test_ui_contract.py`，10 项样例测试 | ✅ 接口与样例 |
| FR-G4 | 真实会话适配：纯读取、稳定 ID、版本检查、失败保留状态 | ZQO | 真实适配器与随机状态测试 | 🔲 |
| FR-G5 | 插件提供可见信息、参数候选与图形动作 | ZC、ZRS | 插件与界面集成 | 🔲 |
| FR-G6 | 可选素材／主题，缺少素材仍可通关 | YHT、ZRS、剧本作者 | 有／无／无效素材路径 | 🔲 |
| FR-W1 | Pyodide 运行同一 Python 核心和剧本 | ZC、ZQO | 浏览器回放、跨端状态一致 | 🔲 |
| FR-W2 | 桌面与手机宽度下完整网页游玩 | ZRS | 浏览器真实剧本通关与布局检查 | 🔲 |
| FR-W3 | 浏览器持久化、刷新恢复、JSON 导入导出和桌面存档互通 | LQ | 刷新／损坏／容量失败／跨端恢复 | 🔲 |
| FR-W4 | Cloudflare 监听 GitHub 推送自动检查、构建与部署 | ZC | 分支预览、main 自动更新固定 URL | 🔲 |
| FR-W5 | 失败构建保留正式版本，预览与正式分开 | ZC | 失败构建与正式版本检查 | 🔲 |
| NFR-G1 | 核心不依赖 Tkinter／DOM／Cloudflare，模块独立测试 | 全体 | 真实适配器导入与隔离测试 | 🔲 |
| NFR-G2 | 纯查看不耗回合／资源／随机状态；拒绝重复和旧响应 | ZQO、ZRS、ZC | 真实会话与浏览器交互测试 | 🔲 |
