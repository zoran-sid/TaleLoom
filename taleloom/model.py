"""共享数据模型（模块接口约定的一部分）。

负责人：YHT。其他模块只读取这些类型；需要新增或修改字段时按
docs/contracts.md 第 5 节走 contract PR。

条件（condition）和效果（effect）在剧本中写成只有一个键的字典，
例如 ``{"has_item": "lamp"}``、``{"add_var": ["oxygen", -1]}``，
具体含义由 rules.Registry 解释，机制插件可以注册新的键。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FORMAT_VERSION = 1

Condition = dict[str, Any]
Effect = dict[str, Any]


@dataclass
class Choice:
    """场景中的一个可选行动。"""

    id: str
    text: str
    goto: str | None = None
    when: Condition | None = None
    effects: list[Effect] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    once: bool = False
    message: str = ""


@dataclass
class Scene:
    id: str
    title: str
    text: str
    choices: list[Choice] = field(default_factory=list)
    on_enter: list[Effect] = field(default_factory=list)
    # 结局场景：{"id": "true_end", "title": "真相大白"}；普通场景为 None
    ending: dict[str, str] | None = None
    # 条件文字列表：每项含 text、可选 when 与 mode（append/replace）；默认空列表。
    variants: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Item:
    id: str
    name: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class Resource:
    """剧本主动公开给玩家查看的数值资源。

    变量名指向 ``Story.initial_vars`` 或效果创建的变量；``maximum`` 为空时
    只显示当前值，不显示上限。
    """

    var: str
    name: str
    maximum: int | None = None


@dataclass
class Trigger:
    """每回合结束后检查一次的规则，例如氧气耗尽时跳到结局。"""

    when: Condition
    effects: list[Effect] = field(default_factory=list)
    once: bool = True
    id: str = ""


@dataclass
class Story:
    id: str
    title: str
    start: str
    scenes: dict[str, Scene]
    items: dict[str, Item] = field(default_factory=dict)
    mechanics: list[str] = field(default_factory=list)
    initial_vars: dict[str, int] = field(default_factory=dict)
    every_turn: list[Effect] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)
    # 机制插件读取的扩展段，例如 "clues"、"accusation"、"combinations"
    data: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    format_version: int = FORMAT_VERSION
    # 剧本可选的展示字段；不参与剧情判定。放在末尾，保持旧的位置参数兼容。
    resources: list[Resource] = field(default_factory=list)
    assets: dict[str, str] = field(default_factory=dict)
    # load_story 填充的剧本目录，用于检查素材文件是否存在；parse_story 为 None
    source_dir: str | None = field(default=None, compare=False, repr=False)

    def endings(self) -> dict[str, Scene]:
        return {sid: s for sid, s in self.scenes.items() if s.ending}


@dataclass
class Command:
    """解析器（ZRS）的输出、引擎（ZQO）的输入。

    verb 取值：choose / look / inventory / help / quit / save / load /
    noop / unknown，以及机制插件声明的动词（clues、accuse、use、combine…）。
    """

    verb: str
    args: list[str] = field(default_factory=list)
    raw: str = ""

    @property
    def target(self) -> str:
        return self.args[0] if self.args else ""


@dataclass
class Output:
    """引擎每处理一条命令返回的结果，界面只负责显示。"""

    lines: list[str] = field(default_factory=list)
    choices: list[tuple[int, str]] = field(default_factory=list)
    ended: bool = False
    ending: str | None = None


@dataclass
class Issue:
    """校验发现的问题。level 为 "error" 或 "warning"，path 指向剧本位置。"""

    level: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.path}: {self.message}"
