# TaleLoom 织境

**数据驱动的文字冒险引擎**：剧情写在 JSON 剧本里，玩法写成可插拔的机制插件。同一个引擎运行两个风格完全不同的原创剧本：

- 《雾港旧案》：一九三一年的港口旅馆命案。搜查地点、收集线索，最后指认凶手；证据是否充分决定结局。
- 《深空回声》：在氧气耗尽前逃离故障的太空站。搜集和组合道具，在正确的地方使用它们。

INT6181 应用 Python 程式设计 · 小组项目。

## 交付目标与当前状态

- 桌面：在 VS Code 中运行 `main.py`，弹出简洁 GUI，选择剧本后全程点击游玩。
- 网页：访问网址直接游玩，通过 Pyodide 共用 Python 核心与剧本；桌面与网页共用存档格式。
- 自动发布：Cloudflare 监听本仓库推送，检查与构建成功后自动部署；`main` 更新正式网址，`develop`／成员分支提供预览。
- 异步协作：共享接口和固定样例先行，界面、引擎、插件、存档与素材分模块扩展。

每人的下一步与接入点见 [任务安排第 0 节](docs/team-tasks.md#0-当前进度与每人下一步)。独立模块开发入口：`taleloom/ui_contract.py`、`tests/ui_fakes.py`，展示端统一用 `taleloom.session_factory.create_session` 取得会话；可运行 `python -B -m unittest tests.integration.test_ui_contract -v`。

当前分支已提供可点击游玩的网页序章、浏览器 Python 运行层和 Cloudflare 构建配置。两个剧本继续使用原有引擎与存档格式。桌面 GUI 和各成员的正式扩展模块继续按分工开发。

本地网页：安装 Node（版本见 `.node-version`）与 Python 后运行 `npm ci`，再运行 `npm run dev -- --open`。发布设置、合并顺序与成员接入点见 [网页试玩与 Cloudflare 自动发布](docs/cloudflare-deploy.md)。账号首次连接／正式网址仍待管理员完成。完整目标见 [GUI／网页实施要求](docs/gui-web-plan.md)。

## 当前版本运行（CLI）

需要 Python 3.10 或以上，无第三方依赖。后续桌面版还需 Python 带 Tcl/Tk；网页运行时与构建依赖单独管理。

```bash
python main.py
```

无参数时打开桌面 GUI；GUI 尚未完成或当前 Python 没有 Tkinter 时，自动改用命令行并列出剧本供选择。VS Code 中可直接用“运行和调试”里的 **TaleLoom：启动游戏**。命令行游玩也可以直接指定剧本：

```bash
python main.py play fog_harbor
```

游戏中输入选项编号或选项文字即可行动。常用命令：

| 命令 | 作用 |
| --- | --- |
| `看` / `look` | 重新查看当前场景 |
| `背包` / `i` | 查看携带的物品 |
| `线索` / `指认 顾先生` | 推理剧本：查看笔记 / 指认嫌疑人 |
| `组合 扳手 胶带` / `使用 扳手` | 解谜剧本：组合 / 使用道具 |
| `存档` / `读档` | 存档保存在 `saves/` |
| `帮助` / `退出` | |

## 开发者命令

```bash
python main.py validate               # 校验 stories/ 下全部剧本
python main.py replay fog_harbor -v   # 回放通关脚本并显示过程
python -B -m unittest discover -s tests -t .        # 全部测试
python -B -m unittest discover -s tests/zrs -t .    # 只跑某位成员的模块测试
```

## 目录

```text
main.py                 入口
taleloom/               引擎源码（按成员分模块，见下表）
  mechanics/            机制插件：mystery 推理、puzzle 道具
stories/<剧本>/          story.json、剧情大纲、walkthroughs/ 通关脚本
tests/<成员缩写>/        各模块单元测试；tests/integration/ 集成测试
docs/                   分工、接口、剧本格式、需求、测试报告、课程要求
```

## 成员分工

| 编号 | 成员 | 负责模块 | 记录 |
| --- | --- | --- | --- |
| 1 | YHT | 剧本格式、加载与静态校验 | [YHT](docs/handoffs/yht.md) |
| 2 | ZQO | 运行时核心与插件接口 | [ZQO](docs/handoffs/zqo.md) |
| 3 | ZRS | 命令解析、命令行界面、道具谜题插件 | [ZRS](docs/handoffs/zrs.md) |
| 4 | ZC | 推理插件、剧本 A《雾港旧案》、整合与发布 | [ZC](docs/handoffs/zc.md) |
| 5 | LQ | 存档、通关回放与探索测试、剧本 B《深空回声》 | [LQ](docs/handoffs/lq.md) |

上表为现有模块归属；GUI、网页与部署新增路径见 [实施要求第 5 节](docs/gui-web-plan.md#5-目录归属与工作量)。具体任务、时间安排与代码审查轮换见 [五人任务安排](docs/team-tasks.md)。常规模块阶段聚焦代码；需求和接口变更及时同步，最终报告、PPT、视频在最终合并阶段统一完成。

## 项目文档

- [网页试玩与 Cloudflare 自动发布](docs/cloudflare-deploy.md)：当前实现、配置参数、发布检查与模块替换入口
- [GUI／网页实施要求](docs/gui-web-plan.md)：最新范围、共享核心、异步分工、Cloudflare 自动部署与验收
- [项目说明](docs/project-brief.md)：为什么做引擎、两个剧本、灵感来源与原创性、范围
- [五人任务安排](docs/team-tasks.md)：分工大纲、必做与加分项、时间线、审阅轮换、最终合并阶段、评分对应
- [接口约定](docs/contracts.md)：模块依赖、引擎与插件接口、修改接口的流程
- [剧本格式](docs/story-format.md)：写剧本的完整字段说明
- [协作流程](docs/collaboration.md)：分支、PR、测试分层、CI、提交信息
- [需求与测试对应表](docs/requirements.md) · [测试报告](docs/testing.md) · [AI 使用记录](docs/ai-usage.md)
- [开工提示词](docs/prompts.md) · [AGENTS.md](AGENTS.md)
- [课程要求全文](docs/course-requirements.md)

## 外部资源

当前运行代码仅使用 Python 标准库。计划中的网页端使用 Pyodide，需在实现时记录锁定版本、许可证和来源。剧本 A 的玩法机制参考了剧本杀的通用玩法，剧情、人物与文字为原创，参考来源见 [项目说明](docs/project-brief.md)。
