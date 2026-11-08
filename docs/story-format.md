# 剧本格式 v1（草案）

格式由 YHT 的代码定义。这是 v0 骨架实际支持的格式；模块阶段新增的字段先写在代码文档字符串中，本文件在最终合并阶段统一补全。完整例子见 `stories/fog_harbor/story.json` 与 `stories/deep_space/story.json`。

新增 GUI／网页展示与可选素材方向见 [实施要求](gui-web-plan.md)。当前正文仅描述已支持的剧本字段；素材和插件展示字段在相应接口实现 PR 中补充，保持旧剧本兼容。

写完剧本先运行：

```bash
python main.py validate <剧本目录名>
python main.py replay <剧本目录名>
```

## 1 文件位置

```text
stories/<剧本id>/
  story.json            剧本
  README.md             剧情大纲、人物、结局表（给组员看，不给玩家看）
  walkthroughs/*.txt    通关脚本，每个结局至少一个
```

## 2 顶层字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `format_version` | 整数 | 否 | 固定为 1 |
| `id` | 字符串 | 是 | 与目录名一致；存档用它识别剧本 |
| `title` | 字符串 | 是 | 显示给玩家的标题 |
| `start` | 字符串 | 是 | 起始场景 id |
| `scenes` | 数组 | 是 | 场景列表，见第 3 节 |
| `items` | 数组 | 否 | 物品：`{"id", "name", "description", "aliases"}` |
| `mechanics` | 数组 | 否 | 启用的插件，如 `["mystery"]`、`["puzzle"]` |
| `vars` | 对象 | 否 | 整数变量初值，如 `{"oxygen": 8}` |
| `every_turn` | 效果数组 | 否 | 每消耗一个回合执行一次 |
| `triggers` | 数组 | 否 | `{"id", "when", "effects", "once"}`，每回合结束检查；`once` 默认 true |
| `meta` | 对象 | 否 | 作者、类型、状态等，不影响游戏 |
| 其他 | 任意 | 否 | 插件数据段，见第 6 节 |

## 3 场景

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | 字符串 | 是 | 剧本内唯一 |
| `title` | 字符串 | 否 | 显示为 `== 标题 ==` |
| `text` | 字符串 | 是 | 进入场景时显示，`\n` 换行 |
| `choices` | 数组 | 否 | 选项，见第 4 节 |
| `on_enter` | 效果数组 | 否 | 每次进入时执行 |
| `ending` | 对象 | 否 | 有此字段即为结局场景：`{"id": "truth", "title": "雾散"}` |

## 4 选项

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | 字符串 | 否 | 场景内唯一；省略时为 `c1`、`c2`… 建议填写，通关脚本和存档更稳定 |
| `text` | 字符串 | 是 | 菜单文字；玩家也可以直接输入这段文字 |
| `goto` | 字符串 | 否 | 选择后跳转的场景 |
| `when` | 条件 | 否 | 满足时才显示 |
| `effects` | 效果数组 | 否 | 选择时执行 |
| `once` | 布尔 | 否 | 选过一次后消失 |
| `message` | 字符串 | 否 | 选择后先显示这段文字 |

## 5 条件与效果

每个条件或效果是**只有一个键**的对象。一个条件对象写多个键时表示“全部满足”。

内置条件：

| 写法 | 含义 |
| --- | --- |
| `{"flag": "door_open"}` | 标记已设置 |
| `{"has_item": "tape"}` | 背包里有该物品 |
| `{"visited": "office"}` | 去过该场景 |
| `{"var": ["oxygen", "<=", 3]}` | 变量比较，运算符 `== != < <= > >=`；未设置的变量视为 0 |
| `{"all": [条件, ...]}` / `{"any": [...]}` / `{"not": 条件}` | 组合 |

内置效果：

| 写法 | 含义 |
| --- | --- |
| `{"set_flag": "x"}` / `{"clear_flag": "x"}` | 设置/清除标记 |
| `{"give_item": "tape"}` / `{"take_item": "tape"}` | 获得/失去物品（会提示玩家） |
| `{"set_var": ["oxygen", 8]}` / `{"add_var": ["oxygen", -1]}` | 设置/增减变量 |
| `{"say": "文字"}` | 显示一段文字 |
| `{"goto": "scene_id"}` | 跳转 |

## 6 插件数据段

### `mystery`（ZC）

```json
"clues": {"torn_ledger": {"name": "被撕去的账页", "text": "..."}},
"accusation": {
  "when": {"visited": "office"},
  "suspects": {"gu": {"name": "顾先生", "aliases": ["顾"]}},
  "outcomes": [{"suspect": "gu", "when": {"has_clue": "torn_ledger"}, "goto": "end_truth"}],
  "default": "end_wrong"
}
```

新增条件 `{"has_clue": id}`、效果 `{"add_clue": id}`；玩家命令“线索”“指认 X”。`outcomes` 从上到下取第一个匹配项，都不匹配时去 `default`。

### `puzzle`（ZRS）

```json
"combinations": [{"items": ["broken_wrench", "tape"], "result": "fixed_wrench", "message": "..."}],
"targets": [{"id": "panel", "name": "控制面板", "aliases": ["面板"], "scene": "airlock"}],
"uses": [
  {"item": "fixed_wrench", "target": "panel", "scene": "airlock", "when": {}, "effects": [...], "message": "...", "consume": false},
  {"item": "tape", "scene": "cryo", "effects": [...], "consume": true}
]
```

玩家命令“组合 A B”“使用 A”“把 A 用在 B 上”。

`targets` 声明玩家可以互动的目标；`scene` 省略时该目标在所有场景可用。`uses` 里写 `target` 表示只对这一个目标使用，不写 `target` 则沿用按 `scene` 匹配的旧规则，旧剧本不用改。
界面动作固定为 `puzzle:use`（参数 `item`）、`puzzle:use_on`（参数 `item` 与 `target`）、`puzzle:combine`（参数 `first` 与 `second`）；候选只含背包物品和当前场景声明的目标，不提示正确配方或使用结果。图形界面提交这些 ID，不拼中文命令。
校验会报告不存在的物品、场景与目标，以及重复或空的目标 id。


## 7 通关脚本

纯文本，每行一条玩家输入，与真实游玩时输入的内容相同。`#` 开头为注释，`# expect: <结局id>` 声明预期结局：

```text
# expect: truth
去账房查看现场
翻看桌上的账本
指认 顾先生
```

优先写选项文字而不是编号：选项顺序变化时脚本仍然有效。
