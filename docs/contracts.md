# 模块接口约定

维护：ZQO（引擎与插件接口）、YHT（数据模型）。本文件描述的是**跨模块接口**；模块内部怎么实现由负责人决定。

## 1 一条命令的处理流程

```text
玩家输入 "指认顾先生"
  → parser.parse(text, out.choices, engine.verb_aliases())  → Command("accuse", ["顾先生"])
  → cli：quit/save/load 自己处理，其余交给引擎
  → engine.handle(cmd)
       ├ choose / look / inventory / help：引擎内置
       └ 其他动词：交给声明了该动词的插件 mechanic.handle(engine, cmd, ctx)
            插件通过 ctx 输出文字、通过 ctx.goto 请求跳转，返回是否消耗回合
  → 消耗回合时：跳转 → 进入场景（on_enter）→ 回合数 +1 → every_turn → triggers
  → 返回 Output(lines, choices, ended, ending)
  → cli.render(out)
```

## 2 共享类型（`taleloom/model.py`，YHT）

| 类型 | 用途 | 生产者 → 消费者 |
| --- | --- | --- |
| `Story` `Scene` `Choice` `Item` `Trigger` | 剧本数据 | loader → engine、validator、插件 |
| `Command(verb, args, raw)` | 解析后的命令 | parser → cli、engine、replay |
| `Output(lines, choices, ended, ending)` | 一次处理的结果 | engine → cli、replay |
| `Issue(level, path, message)` | 校验问题 | validator、插件 → main |

剧本中插件专用的数据段（`clues`、`accusation`、`combinations`、`uses` 等）不进入 `Story` 的固定字段，统一放在 `Story.data` 中，由插件自己解释。这样新插件不需要修改 `model.py`。

## 3 引擎公开接口（`taleloom/engine.py`，ZQO）

```python
engine = Engine(story, state=None)       # state 不为空表示从存档恢复
out = engine.start()                     # 开场或继续游戏的描述
out = engine.handle(command)             # 处理一条命令
engine.state                             # GameState，可序列化
engine.available_choices()               # 当前可选项
engine.verb_aliases()                    # 已启用插件的动词别名，交给 parser
engine.registry                          # 条件/效果注册表，插件可调用 check/apply
```

`GameState`（`state.py`）只含可 JSON 序列化的数据。插件的状态放在 `state.ext["<插件名>"]`，通过 `state.plugin(name)` 取得，**不要给 GameState 增加插件专用字段**。

## 4 插件接口（`taleloom/mechanics/base.py`）

```python
class Mechanic:
    name: str                                  # 剧本 "mechanics" 中的名字
    verbs: dict[str, list[str]]                # 动词 → 玩家可输入的别名
    provides_conditions / provides_effects     # 本插件注册的名字（用于校验提示）

    def register(self, registry): ...          # 注册条件与效果
    def handle(self, engine, cmd, ctx) -> bool # 处理动词；True 表示消耗回合
    def validate(self, story) -> list[Issue]   # 检查自己的数据段
    def help_lines(self) -> list[str]          # “帮助”中显示的说明
```

新插件的步骤：在 `mechanics/` 新建文件，继承 `Mechanic`；在 `mechanics/__init__.py` 的 `_FACTORIES` 登记一行；写 `tests/<缩写>/test_<插件>.py`；在 [剧本格式](story-format.md) 中补充数据段说明。

插件可以：读写 `ctx.state`、调用 `ctx.say`、设置 `ctx.goto`、用 `engine.registry.check/apply` 求值剧本中的条件与效果。
插件不可以：直接调用 `print`/`input`、读写文件、修改其他插件的 `state.ext` 分区、修改 `Story`。

## 5 修改接口的流程（contract PR）

以下改动会影响他人，必须单独开 PR，标题用 `feat(contract): ...` 或 `refactor(contract): ...`，加 `contract` 标签：

- `model.py` 或 `ui_contract.py` 中共享类型、Protocol 及 JSON 字段的增删改；
- `Engine` 公开方法、`Mechanic` 基类、`Registry` 的签名；
- 剧本格式中已有字段的含义变化（新增可选字段不算）。

流程：

1. 在 PR 描述里写清楚：改了什么、为什么、哪些模块受影响、迁移办法。
2. 同一个 PR 内修好仓库中所有受影响的调用和测试，保证 `checks` 全绿。不能留下“等别人来改”的破坏。
3. @ 受影响模块的负责人；24 小时内无异议即可合并（异步协作，不要求所有人在线）。
4. 合并后在群里发一句“已合入 + PR 链接”。

只新增（不改变已有行为）的接口，例如插件新注册的条件，不需要走这个流程。

## 6 桌面／网页共享接口 v1

定义文件：`taleloom/ui_contract.py`。已提供可导入的数据类型、Protocol、固定测试替身和样例测试。网页部署基础采用独立 v0 兼容会话、桥接与单槽持久化；正式会话、GUI 和存储模块继续由对应成员实现，接入点见 [部署指南](cloudflare-deploy.md)。第 1–4 节现有接口不变。修改本节接口或 JSON 结构按第 5 节走 contract PR。

### 数据约定

| 类型 | 字段／作用 |
| --- | --- |
| `DisplayItem` | `id, label, description`：物品、线索和候选的可见数据 |
| `ActionParameter` | `key, label, kind, options, required`：select 候选或 text 文字参数 |
| `ActionSpec` | `id, label, parameters, enabled, disabled_reason`：稳定动作 ID，不使用选项序号 |
| `ResourceView` | `id, label, value, maximum`：公开数值 |
| `ViewSnapshot` | 场景、正文、revision、turn、choices、actions、inventory、clues、resources、assets、结局及 protocol_version |
| `ActionRequest` | `action_id, expected_revision, values`：参数名映射到所选 ID 或文字 |
| `SessionResult` | `view, messages, error_code`：完整快照、操作反馈与错误码 |

快照、请求和结果的 `to_dict()` 返回独立的 JSON 可序列化对象。Python 的 `result.ok` 是便利属性，JSON 接收端以 `error_code` 是否为 null 判断成功。`protocol_version=1` 与存档版本独立。类型注解和 Protocol 不负责外部输入校验；浏览器桥接必须检查消息字段、类型和版本后再构造请求，不能执行来自输入的 Python 代码。

### 调用与行为

```python
class GameSession(Protocol):
    def start(self) -> SessionResult: ...
    def snapshot(self) -> ViewSnapshot: ...
    def dispatch(self, request: ActionRequest) -> SessionResult: ...
    def export_save(self) -> dict: ...
    def restore(self, payload: dict) -> SessionResult: ...

class SaveStore(Protocol):
    def list_slots(self) -> list[str]: ...
    def read(self, slot: str) -> dict: ...
    def write(self, slot: str, payload: dict) -> None: ...
```

- 会话绑定一个已加载剧本。启动层负责选择／加载，重新开始或切换剧本时创建新实例。真实适配器构造参数由 ZQO 确定，界面仅依赖 `GameSession`。
- 先调用 `start()`；重复调用幂等，不重复触发开场。未启动调用属于开发错误。
- `snapshot()` 是纯读取，返回独立数据；查看、缩放和渲染不推进回合、不抽随机数。修改返回值不能修改游戏状态。
- `revision` 是会话界面版本，`turn` 是游戏回合。成功改变状态或恢复存档时 revision 单调递增；读取或失败不递增。恢复旧存档也必须让旧动作失效。
- `dispatch` 先检查版本与动作，再检查参数和规则。过期返回 `stale_revision`，无效动作返回 `invalid_action`，参数错误返回 `invalid_parameters`；失败保留原状态。
- 动作 ID 示例为 `choice:take`、`puzzle:use`。适配器映射到现有 `Command`；UI 不拼接中文命令。参数候选只包含玩家已知内容，不提供正确配方或未发现线索。
- `messages` 是本次反馈，不用于重建场景。每次结果包含完整快照；浏览器消息同时带会话标识与请求 ID，切换故事后丢弃旧会话响应，避免版本从零开始造成混淆。
- 真实 `export_save/restore` 沿用 `save.py` 的存档版本、剧本 ID 与指纹规则，将编码／验证从文件读写中提取复用。恢复失败返回 `invalid_save`；成功不重复执行进入场景事件。
- `SaveStore` 只存取数据，预期失败抛 `StorageError`，不泄漏可变引用。文件端保留原子写入；浏览器端通过 JS 桥接异步完成等价操作，不要求 Python 同步等待浏览器消息。首版不承诺跨设备同步。
- `assets` 为展示角色到剧本相对路径的映射，例如 background／portrait；由 YHT 在素材字段实现时补齐校验，缺失时文字仍可通关。

### 展示端如何取得会话、桌面如何启动

所有展示端只通过一个入口创建会话，不直接实例化具体类：

```python
from taleloom.loader import load_story
from taleloom.session_factory import create_session

session = create_session(load_story("stories/fog_harbor"))   # GameSession
result = session.start()
```

- `taleloom/session_factory.py`（ZC）当前返回 v0 兼容会话 `taleloom/legacy_session.py`。ZQO 的 `taleloom/session.py` 通过本节约定与真实剧本回放后，在这里改一行，桌面、网页和 `tools/web_vectors.py` 同时切换。
- 桌面 GUI（ZRS）以包 `taleloom.gui` 交付，提供 `run(stories_dir: Path, saves_dir: Path) -> int`（返回进程退出码）。`python main.py` 无参数时调用它；包不存在或当前 Python 没有 Tkinter 时，`main.py` 提示后回退命令行，见 `tests/zc/test_main_entry.py`。
- GUI 内部只依赖 `GameSession` 与 `SaveStore`，开发阶段用 `tests/ui_fakes.py` 的替身，不 import `engine.py`。

### 可独立运行的示例

在仓库根目录执行以下 Python 内容，无需窗口、网络或真实剧本：

```python
from taleloom.ui_contract import ActionRequest
from tests.ui_fakes import FakeGameSession, MemorySaveStore

session = FakeGameSession()
first = session.start()
taken = session.dispatch(ActionRequest("choice:take", first.view.revision))
store = MemorySaveStore()
store.write("slot-1", session.export_save())
result = session.restore(store.read("slot-1"))
assert result.view.inventory[0].id == "key"
```

- ZRS 将测试替身注入页面控制器，覆盖动作、参数、物品、资源、错误和结局。
- ZQO 可复用 `tests/integration/test_ui_contract.py` 的 `SessionContractMixin`，用包含 take/open 动作的迷你剧本构造真实会话，再增加插件、随机、存档测试。
- LQ 用 `MemorySaveStore` 隔离文件与浏览器，独立测试真实存储和存档互通。
- YHT 维护数据与 `to_dict()` 结构；ZC 把同一 JSON 数据映射到 Web Worker 消息并验证真实浏览器回放。

运行 `python -B -m unittest tests.integration.test_ui_contract -v` 验证样例。测试替身使用带 fixture 标记的测试存档，内存存储随实例消失，均不属于正式游戏实现。
