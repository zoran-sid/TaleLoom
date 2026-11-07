# TaleLoom AI 协作指南

本文件适用于整个仓库，供每位成员使用的 AI（Claude Code、Cursor、Codex 等）在开工时读取。人也一样适用。

## 1 开始工作

1. 阅读 `README.md`、`docs/gui-web-plan.md`（GUI／网页与自动发布要求）、`docs/team-tasks.md`（分工）、`docs/contracts.md`（接口）、`docs/collaboration.md`（Git 与测试流程）。课程原文在 `docs/course-requirements.md`。
2. 运行 `git status --short --branch` 和 `git log -5 --oneline`，保留已有修改；从最新 `develop` 创建 `<缩写小写>/<主题>` 分支。
3. 确认当前成员的缩写，只在其负责的文件内工作（`docs/team-tasks.md` 第 1 节）。

## 2 项目共同口径

- 项目：TaleLoom 织境，数据驱动的文字冒险引擎；同一个引擎运行两个原创剧本《雾港旧案》（推理搜证）与《深空回声》（资源与道具解谜）。当前已实现 CLI；目标同时交付简洁桌面 GUI 与网页试玩。
- 桌面目标：VS Code 运行 `main.py` 无参数启动 Tkinter + ttk 窗口，全程点击可通关。Python 核心与桌面保持 Python 3.10+ 标准库依赖，演示环境需具备 Tcl/Tk。标准库限制是项目选型，课程原文要求见 `docs/course-requirements.md`。
- 网页目标：Pyodide 在浏览器 Web Worker 中复用 Python 核心；Cloudflare Workers Static Assets 托管。GitHub 推送由 Workers Builds 自动检查、构建、部署，main 正式发布，develop／成员分支预览。网页运行时与构建依赖单独管理，不能成为桌面依赖。
- 成员：YHT、ZQO、ZRS、ZC、LQ。文档只用缩写，不写全名和学号。
- 剧本内容全部原创。剧本杀资料只借鉴玩法机制，不改编情节、人物或文字。

## 3 写代码的规则

- 常规模块阶段只做代码：实现、测试、剧本 JSON 与通关脚本、文档字符串。PDF、PPT、视频、报告、测试报告与交接记录在最终合并阶段统一完成。总设计者明确要求变更项目范围／共享接口／分工时，及时同步需求、协作规则与开工指引，避免成员继续按旧范围开发；不因此提前生成最终报告。
- 先写会失败的测试，再写实现；测试名称写清楚验证的行为。
- 单元测试放 `tests/<缩写小写>/`，只用 `tests/fixtures.py` 或测试内构造的数据，不读 `stories/`。
- 引擎与插件不调用 `print`/`input`，不读写文件；输出通过 `Output`/`Context` 返回。
- 引擎与插件不依赖 Tkinter、DOM 或 Cloudflare。GUI／网页通过共享会话接口、结构化操作与展示快照交互；新增玩法同时提供图形操作。快照读取不推进回合、不抽取随机数、不触发剧情。
- 共享接口已提供 `ui_contract.py`、`tests/ui_fakes.py` 与样例测试；真实适配器仍需实现。后续接口变更在 contract PR 同步实现、固定样例与兼容测试，再按 `docs/gui-web-plan.md` 第 5 节划分文件异步开发。待实现能力与真实完成状态分开记录。
- 修改 `taleloom/ui_contract.py`、`taleloom/model.py`、`Engine` 公开方法、`Mechanic` 基类或已有剧本字段的含义，按 `docs/contracts.md` 第 5 节走 contract PR，并在同一个 PR 内修好所有受影响的代码和测试。
- 无效输入要给出有意义的提示，不能崩溃（课程“可用性”评分项）。
- 公开函数和类写中文文档字符串；适合的小例子写成 doctest。

## 4 提交前检查

```bash
python -B -m unittest discover -s tests/<缩写小写> -t .
python -B -m unittest discover -s tests -t .
python main.py validate
git diff --check
```

提交信息格式 `<type>(<scope>): <summary>`，见 `docs/collaboration.md` 第 6 节。PR 目标为 `develop`，填写 PR 模板，按 `docs/team-tasks.md` 第 6 节请审阅人。

## 5 记录

- 模块阶段的记录只写在 PR 描述里：改了什么、验证命令与结果、对他人的影响、是否用了 AI 以及人工改了什么（一句话）。最终合并阶段据此统一整理文档。
- 只记录真实完成的工作和真实运行过的测试；不代写其他成员的认可、审阅意见或贡献。
- 审阅他人 PR 时，意见写在 PR 评论中，由他人决定是否修改。
