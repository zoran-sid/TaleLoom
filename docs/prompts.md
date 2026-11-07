# 开工提示词

当前已有独立的网页部署基础，先读 [部署指南第 5 节](cloudflare-deploy.md#5-与成员任务的边界)。继续各自正式模块任务，不直接重写 `web/preview/` 兼容实现；完成后由 ZC 在明确接入点切换。

本轮目标是共享 Python 核心的桌面 GUI、网页试玩和 Cloudflare 自动部署。各成员把对应部分交给 AI；先区分已经提供的接口／测试替身与尚待实现的正式适配器。

## 通用开头

```text
我是 <缩写>，负责 TaleLoom 的 <模块>。请先读 AGENTS.md、docs/gui-web-plan.md、
docs/team-tasks.md 我的部分、docs/contracts.md（尤其第 6 节）。
运行 git status 和 git log，从最新 develop 创建 <缩写小写>/<主题> 分支，保留已有修改。
查看 taleloom/ui_contract.py 和 tests/ui_fakes.py；先运行
python -B -m unittest tests.integration.test_ui_contract -v。
常规模块做实现、测试、剧本 JSON 和文档字符串；范围／接口变更同步必要指引，最终报告留到最后。
先写失败测试，再实现；按文件归属工作。修改共享类型、协议或公开接口走 contract PR，
同一个 PR 修好受影响调用和测试。引擎不依赖窗口、浏览器和 Cloudflare。
用固定样例独立测试，随后再与真实模块集成；测试替身通过不能记为正式功能完成。
完成后跑本模块、全部测试、剧本校验和回放，推送并开 PR 到 develop，写明真实验证结果和 AI 使用。
```

## YHT

```text
保留已经提交的加载／校验／场景图工作，先检查其 PR 状态，避免重复实现。
维护 ui_contract.py 的数据类型与 JSON 结构；与 ZQO 配合实现展示快照映射。
为公开资源、可选素材和后续展示字段提供数据格式与校验，旧剧本应继续有效。
字段未正式实现前，不把示例字段当作 loader 已支持能力。
用内构迷你数据覆盖正常、缺失和错误字段；不修改真实剧本内容。
```

## ZQO

```text
优先实现符合 GameSession 的真实适配器（计划 session.py / presentation.py），保留现有 Engine API。
接口形状已经在 ui_contract.py，第 6 节约定 start/snapshot/dispatch/export_save/restore。
先用迷你剧本和 SessionContractMixin 验证，再增加插件、随机、存档的行为测试。
快照只读且返回独立数据；动作按 ID/参数提交，版本过期或输入失败不得留下状态变化。
提供插件展示／动作描述接口，普通 UI 不直接读取 state.ext 或解析输出文字。
随机结果在实际操作时产生，存档保存足够随机状态；刷新不得抽随机数。
涉及 LQ 的存档数据函数时，在同一个契约 PR 给出最小兼容实现和测试。
```

## ZRS

```text
优先做简洁 Tkinter + ttk 桌面 GUI，再实现 web/ui、web/styles、web/index.html。
先注入 FakeGameSession 独立开发；统一使用快照、ActionRequest 和 SessionResult。
覆盖剧本进入、场景正文、行动、背包／线索、资源、参数选择、存读档和结局。
所有玩家核心操作可点击；渲染不消耗回合，操作串行，加载／错误可恢复。
道具插件提供使用／组合动作与玩家已知候选；不在 UI 重新实现规则。
网页通过 ZC 的运行时桥接调用同一协议；使用 LQ 的存储适配。
保留原 CLI，终端颜色／补全／复杂自然句式降为可选，不阻塞 GUI 交付。
```

## ZC

```text
负责整体整合、推理展示、启动和网页运行时／部署。
main.py 无参数启动 GUI，补 VS Code 启动配置，保留已合入的 validate/replay/graph 等命令。
先用两个现有序章完成闭环；推理插件提供可见线索、人物、审问／指认参数和动作。
web/runtime 使用 Pyodide 模块型 Web Worker 复用 Python 核心；消息带会话／请求 ID，
校验外部 JSON，丢弃过期会话响应。不要在 JavaScript 重写游戏规则。
锁定运行时，构建只打包所需核心、剧本与素材；验证 Pyodide 兼容及跨端状态一致。
Cloudflare Workers Static Assets 托管，Workers Builds 原生连接本 GitHub 仓库。
固定路线：推送触发检查／构建，成功后自动部署；main 正式，develop／成员分支预览。
按当前官方文档实现 Cloudflare CLI 配置、构建与部署命令，首次账号连接单独完成；
验证一次真实推送发布及失败保留旧版，未配置前不记录为已上线。
```

## LQ

```text
优先把 save.py 的数据编码／解码／版本校验与文件读写分开，保留旧调用和存档兼容。
实现 SaveStore 的桌面文件适配及 web/storage 浏览器持久化与 JSON 导入导出。
先用 MemorySaveStore 隔离依赖测试；测试替身不代表刷新后持久化。
存储错误给出明确提示，失败保留原存档；坏存档不能覆盖当前会话。
验证桌面／网页存档互通、刷新恢复，以及固定操作／随机状态下的跨端结果。
继续随机探索与剧本 B 扩写；每个结局提供通关脚本。
```
