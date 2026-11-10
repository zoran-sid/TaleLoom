# TaleLoom 织境

**数据驱动的文字冒险引擎**：剧情写在 JSON 剧本里，玩法写成可插拔的机制插件。同一个引擎运行两个风格完全不同的原创剧本：

- 《雾港旧案》：一九三一年的港口旅馆命案。搜查地点、收集线索，最后指认凶手；证据是否充分决定结局。
- 《深空回声》：在氧气耗尽前逃离故障的太空站。搜集和组合道具，在正确的地方使用它们。

INT6181 应用 Python 程式设计 · 小组项目。

## 交付目标与当前状态

- 桌面：在 VS Code 中运行 `main.py`，弹出简洁 GUI，选择剧本后全程点击游玩。
- 网页：访问网址直接游玩，通过 Pyodide 共用 Python 核心与剧本；桌面与网页共用存档格式。
- 自动发布：Cloudflare 监听本仓库推送，检查与构建成功后自动部署；`main` 更新正式网址，`develop`／成员分支用于开发与验收，自动预览开关见 [部署说明](https://github.com/zoran-sid/TaleLoom/blob/develop/docs/cloudflare-deploy.md)。
- 异步协作：共享接口和固定样例先行，界面、引擎、插件、存档与素材分模块扩展。

独立模块开发入口：`taleloom/ui_contract.py`、`tests/ui_fakes.py`，展示端统一用 `taleloom.session_factory.create_session` 取得会话；可运行 `python -B -m unittest tests.integration.test_ui_contract -v`。

当前状态：命令行可完整游玩两个序章；网页可在线点击游玩：<https://taleloom.zoranzhou.com>；影像模式（互动影像、失败惩罚、关键节点存档）：<https://taleloom.zoranzhou.com/cinematic>，发布 PR 合入 `main` 后由 Cloudflare 自动部署；自动预览当前开关状态见 [部署说明](https://github.com/zoran-sid/TaleLoom/blob/develop/docs/cloudflare-deploy.md)；桌面 GUI 与各成员的正式模块按分工开发中。

《雾港旧案：未结的账》已改为通过剧情选择推进，发现与对质融入场景；九处分支已确认。序章与第一幕已加入场景级配音（旁白、对白与环境声，影像模式控制条可开关），其余幕次沿用现有声音。玩法、存档与声音记录见 [剧本说明](stories/film/fog_harbor_ledger/README.md) 和 [配音工作记录](配音工作记录.md)。

本地网页：安装 Node（版本见 `.node-version`）与 Python 后运行 `npm ci`，再运行 `npm run dev -- --open`。

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
main.py                 入口（无参数打开桌面 GUI，子命令 play / validate / replay / graph）
taleloom/               Python 核心（按成员分模块，见下表）
  mechanics/            机制插件：mystery 推理、puzzle 道具
  session_factory.py    桌面与网页共用的会话入口
stories/<剧本>/          story.json、剧情大纲、walkthroughs/ 通关脚本
tests/<成员缩写>/        各模块单元测试；tests/integration/ 集成测试；tests/browser/ 浏览器测试
web/                    网页：runtime/ 浏览器中运行 Python 的桥接，preview/ 临时试玩界面
tools/                  网页打包与发布检查脚本
```

## 成员分工

| 编号 | 成员 | 负责模块 |
| --- | --- | --- |
| 1 | YHT | 剧本格式、加载与静态校验；展示数据类型 |
| 2 | ZQO | 运行时核心与插件接口；正式会话与展示快照 |
| 3 | ZRS | 命令行与桌面／网页界面；道具谜题插件 |
| 4 | ZC | 推理插件、剧本 A《雾港旧案》、整合与发布 |
| 5 | LQ | 存档与存储、回放与探索测试、剧本 B《深空回声》 |

## 外部资源

Python 核心与桌面端仅使用标准库。网页端使用 Pyodide 在浏览器中运行 Python，版本与许可证见 `web/runtime/THIRD_PARTY_NOTICES.txt`；网页构建与测试工具（Vite、Cloudflare CLI、Playwright）锁定在 `package-lock.json`，只用于开发和发布。剧本 A 的玩法机制参考了剧本杀的通用玩法，剧情、人物与文字为原创。
