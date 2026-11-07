# TaleLoom AI 协作指南

本文件适用于整个仓库，供每位成员使用的 AI（Claude Code、Cursor、Codex 等）在开工时读取。人也一样适用。

## 1 开始工作

1. 阅读 `README.md`、`docs/team-tasks.md`（分工）、`docs/contracts.md`（接口）、`docs/collaboration.md`（Git 与测试流程）和自己的 `docs/handoffs/<缩写小写>.md`。课程原文在 `docs/course-requirements.md`。
2. 运行 `git status --short --branch` 和 `git log -5 --oneline`，保留已有修改；从最新 `develop` 创建 `<缩写小写>/<主题>` 分支。
3. 确认当前成员的缩写，只在其负责的文件内工作（`docs/team-tasks.md` 第 1 节）。

## 2 项目共同口径

- 项目：TaleLoom 织境，数据驱动的命令行文字冒险引擎；同一个引擎运行两个原创剧本《雾港旧案》（推理搜证）与《深空回声》（资源与道具解谜）。
- 运行环境：Python 3.10+，**只用标准库**（课程要求标准 Python 环境）。入口 `main.py`。
- 成员：YHT、ZQO、ZRS、ZC、LJ。文档只用缩写，不写全名和学号。
- 剧本内容全部原创。剧本杀资料只借鉴玩法机制，不改编情节、人物或文字。

## 3 写代码的规则

- 先写需求（`docs/requirements.md`），再写会失败的测试，再写实现。
- 单元测试放 `tests/<缩写小写>/`，只用 `tests/fixtures.py` 或测试内构造的数据，不读 `stories/`。
- 引擎与插件不调用 `print`/`input`，不读写文件；输出通过 `Output`/`Context` 返回。
- 修改 `taleloom/model.py`、`Engine` 公开方法、`Mechanic` 基类或已有剧本字段的含义，按 `docs/contracts.md` 第 5 节走 contract PR，并在同一个 PR 内修好所有受影响的代码和测试。
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

- 完成实质任务后更新 `docs/handoffs/<缩写小写>.md`：成果路径、需求编号、验证命令与结果、对他人的影响。
- 每次有实质性的 AI 协助，在 `docs/ai-usage.md` 加一行，写明人工核验和修改了什么。
- 只记录真实完成的工作和真实运行过的测试；不代写其他成员的认可、审阅意见或贡献。
- 审阅他人 PR 时，意见写在 PR 评论中，由他人决定是否修改。
