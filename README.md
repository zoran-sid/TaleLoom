# TaleLoom 织境

**数据驱动的命令行文字冒险引擎**：剧情写在 JSON 剧本里，玩法写成可插拔的机制插件。同一个引擎运行两个风格完全不同的原创剧本：

- 《雾港旧案》：一九三一年的港口旅馆命案。搜查地点、收集线索，最后指认凶手；证据是否充分决定结局。
- 《深空回声》：在氧气耗尽前逃离故障的太空站。搜集和组合道具，在正确的地方使用它们。

INT6181 应用 Python 程式设计 · 小组项目。

## 运行

需要 Python 3.10 或以上，无第三方依赖。

```bash
python main.py
```

会列出剧本供选择。也可以直接指定：

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
| 2 | ZQO | 运行时核心与插件接口；总体架构 | [ZQO](docs/handoffs/zqo.md) |
| 3 | ZRS | 命令解析、命令行界面、道具谜题插件 | [ZRS](docs/handoffs/zrs.md) |
| 4 | ZC | 推理插件、剧本 A《雾港旧案》、整合与发布 | [ZC](docs/handoffs/zc.md) |
| 5 | LJ | 存档、通关回放与测试报告、剧本 B《深空回声》 | [LJ](docs/handoffs/lj.md) |

具体任务、时间安排、代码审查轮换与演示分配见 [五人任务安排](docs/team-tasks.md)。

## 项目文档

- [项目说明](docs/project-brief.md)：为什么做引擎、两个剧本、灵感来源与原创性、范围
- [五人任务安排](docs/team-tasks.md)：分工大纲、必做与加分项、时间线、审阅轮换、演示分配、评分对应
- [接口约定](docs/contracts.md)：模块依赖、引擎与插件接口、修改接口的流程
- [剧本格式](docs/story-format.md)：写剧本的完整字段说明
- [协作流程](docs/collaboration.md)：分支、PR、测试分层、CI、提交信息
- [需求与测试对应表](docs/requirements.md) · [测试报告](docs/testing.md) · [AI 使用记录](docs/ai-usage.md)
- [开工提示词](docs/prompts.md) · [AGENTS.md](AGENTS.md)
- [课程要求全文](docs/course-requirements.md)

## 外部资源

仅使用 Python 标准库。剧本 A 的玩法机制参考了剧本杀的通用玩法，剧情、人物与文字为原创，参考来源见 [项目说明](docs/project-brief.md)。
