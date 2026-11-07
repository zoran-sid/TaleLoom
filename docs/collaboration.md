# GitHub 异步协作与测试流程

## 1 分支

| 分支 | 含义 | 写入方式 |
| --- | --- | --- |
| `main` | 可演示、可提交的稳定版本 | 只从 `develop` 合并发布 PR，`checks` 全绿，小组确认后由 ZC 合并并打标签 |
| `develop` | 日常集成 | 只合并成员分支的 PR；保持 `checks` 全绿 |
| `<缩写小写>/<主题>` | 个人工作，例如 `zrs/use-on-syntax`、`lq/save-slots` | 从最新 `develop` 创建，PR 到 `develop`，合并后删除 |

标签：`v0.1-skeleton`（当前骨架）、`v1.0-rc.N`（候选）、`v1.0-submission`（最终提交）。

## 2 一次完整的工作循环

```bash
# 1. 同步
git fetch origin
git switch develop && git pull --ff-only
git switch -c zrs/use-on-syntax

# 2. 先写测试（会失败），再写实现，直到本模块测试通过
python -B -m unittest discover -s tests/zrs -t .

# 3. 提交前跑全部测试和剧本检查
python -B -m unittest discover -s tests -t .
python main.py validate

# 4. 推送并开 PR（目标 develop）
git push -u origin zrs/use-on-syntax
gh pr create --base develop --fill
```

PR 模板会列出检查清单。审阅人按 [任务安排](team-tasks.md) 第 6 节的轮换指定。`checks` 全绿 + 审阅人批准（或 24 小时内无异议的小改动）后，作者自己用 **merge commit** 合并，保留每个人的提交记录（最终阶段的个人报告要引用）。

## 3 什么时候会冲突，怎么避免

- 每人只改自己负责的文件（[任务安排](team-tasks.md) 第 1 节）。需要改别人的文件时，先在 PR 里说明并 @ 对方。
- 共享接口（`model.py`、`Engine` 公开方法、`Mechanic` 基类）的改动走 [contract PR](contracts.md)。
- 剧本 JSON 只由剧本负责人修改；别人发现剧本问题开 issue。
- PR 保持小而完整：一个 PR 做一件能独立测试的事，最好 1–3 天内合并，避免长期分支。
- 开 PR 前 `git pull --rebase origin develop` 或在 GitHub 上点 “Update branch”，保证基于最新 `develop`。

## 4 测试分层

| 层次（课件 V 模型） | 本项目 | 位置 | 谁写 |
| --- | --- | --- | --- |
| 单元测试 | 每个模块的函数和类，含 doctest | `tests/<缩写>/` | 模块负责人 |
| 集成测试 | 真实剧本经过加载 → 校验 → 引擎 → 插件 → 解析 | `tests/integration/` | ZC |
| 系统/验收测试 | 通关脚本回放、结局覆盖、随机探索 | `stories/*/walkthroughs/`、LQ 的探索工具 | 剧本作者、LQ |
| 可用性测试 | 组外同学试玩记录（最终合并阶段） | [测试报告](testing.md) | 全体 |

测试规则：

- 单元测试只用 `tests/fixtures.py` 的迷你剧本或在测试里自己构造的数据，**不读 `stories/`**，剧本改动不影响他人的单元测试。
- 每个功能至少有正常、边界、异常输入三类测试。
- 只用标准库 `unittest`（课程要求标准 Python 环境）。本地想用 `pytest` 运行也可以，它能直接识别这些测试。

## 5 CI

`.github/workflows/checks.yml` 在每次推送到 `main`/`develop` 和每个 PR 时运行：

| 检查项 | 内容 |
| --- | --- |
| `tests (yht)` … `tests (lq)` | 五个成员模块的测试，分项显示 |
| `tests (integration)` | 集成测试 |
| `stories` | 校验所有剧本、回放所有通关脚本 |
| `full suite (Python 3.10/3.13)` | 兼容性；PR 上额外检查行尾空白 |

## 6 提交信息

```text
<type>(<scope>): <summary>
```

`type`：`feat` 新功能、`fix` 修复、`test` 测试、`docs` 文档、`refactor` 重构、`chore` 仓库维护、`ci` 持续集成、`story` 剧本内容。`scope` 用模块名：`parser`、`engine`、`validator`、`mystery`、`puzzle`、`save`、`replay`、`cli`、`fog-harbor`、`deep-space`、`contract`。summary 用英文动词开头，不加句号。例：

```text
feat(parser): parse "use A on B" sentences
test(save): cover corrupted save files
story(fog-harbor): add the second act and two endings
```

## 7 异步沟通

- 进度看 GitHub，不靠群聊：PR 描述和 CI 结果。模块阶段不需要另写交接文档。
- 合并影响他人的 PR 后在群里发一句“已合入 + PR 链接”。
- 阻塞问题开 issue 并 @ 负责人；对方不在线时，先用最小替代（例如在自己的测试里构造假数据）继续推进，不停下来等。

## 8 GUI／网页协作与自动发布

- 新方向以 [GUI／网页实施要求](gui-web-plan.md) 为准。`ui_contract.py` 的类型、Protocol 与 JSON 结构是共享契约，变更按 contract PR 流程同步固定样例和受影响调用。
- 各成员先使用 `tests/ui_fakes.py` 独立开发和测试，再接入真实适配器；新增目录按实施要求第 5 节归属，避免多人修改同一个入口。
- 总设计者要求的范围／接口／分工调整及时同步文档；最终报告、PPT、视频仍在最终阶段制作。
- 发布链路确定为 GitHub 推送 → Cloudflare Workers Builds 检查／构建 → 自动部署。main 为正式网址，develop／成员分支为预览；首次账号连接和项目配置完成后日常只需提交代码。
- Cloudflare 构建自身执行测试与网页检查，全部成功才部署；不假设独立的 GitHub Actions 已完成。失败保留上次成功版本，预览不覆盖正式版本。
- 仍通过 PR 合入 develop，再由发布 PR 合入 main。自动部署不等于自动合并或绕过现有审阅。当前提供要求、接口与测试替身，真实适配器、网站与流水线待实施并记录部署证据。
