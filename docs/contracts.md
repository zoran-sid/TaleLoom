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

- `model.py` 中任何类型的字段增删改；
- `Engine` 公开方法、`Mechanic` 基类、`Registry` 的签名；
- 剧本格式中已有字段的含义变化（新增可选字段不算）。

流程：

1. 在 PR 描述里写清楚：改了什么、为什么、哪些模块受影响、迁移办法。
2. 同一个 PR 内修好仓库中所有受影响的调用和测试，保证 `checks` 全绿。不能留下“等别人来改”的破坏。
3. @ 受影响模块的负责人；24 小时内无异议即可合并（异步协作，不要求所有人在线）。
4. 合并后在交接记录里写一行。

只新增（不改变已有行为）的接口，例如插件新注册的条件，不需要走这个流程。
