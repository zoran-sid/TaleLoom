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

《雾港旧案：未结的账》已改为通过剧情选择推进，发现与对质融入场景；九处分支已确认。序章与第一幕已有场景配音，字幕会跟随录音翻页；Seed Audio 新录音按时间戳接入，素材进度与动画接口见 [声音交接](stories/film/fog_harbor_ledger/AUDIO_HANDOFF.md)。玩法与存档见 [剧本说明](stories/film/fog_harbor_ledger/README.md)，早期配音记录见 [配音工作记录](配音工作记录.md)。

## 本地安装与运行

### 本地网页版

在新电脑上安装 Python 3.10 或以上，以及 [`.node-version`](.node-version) 指定版本的 Node.js（包含 npm）。用 VS Code 打开项目文件夹，在终端运行：

```bash
npm ci
npm run dev -- --open
```

浏览器会打开本地书架。从书架可进入影像模式，也可以在终端显示的本地地址后加上 `/cinematic` 直接打开。服务运行期间保留终端，按 `Ctrl+C` 停止。

`npm ci` 按 `package-lock.json` 安装网页依赖，首次设置或依赖清单更新后执行。平时打开项目只需运行第二条命令。本地试玩无需登录 Cloudflare。

### 桌面版与命令行

安装 Python 3.10 或以上，在项目根目录运行以下命令。游戏使用 Python 标准库，`requirements.txt` 目前没有第三方包需要安装。若系统的 Python 命令是 `python3`，请用它替换下面的 `python`。

```bash
python -m pip install -r requirements.txt
python main.py
```

桌面版需要 Python 提供 Tkinter（Tcl/Tk）。运行 `python -m tkinter`，弹出测试窗口即可启动桌面版。Windows 和 macOS 可使用 Python 官网安装包。Ubuntu 若使用系统 Python，可通过 `sudo apt install python3-tk` 安装 Tkinter。详见 [Python 的 Tkinter 文档](https://docs.python.org/3/library/tkinter.html)。

VS Code 中可使用“运行和调试”里的 **TaleLoom：启动游戏**。没有 Tkinter 时，也可以通过命令行直接游玩：

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
