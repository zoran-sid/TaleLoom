"""游戏状态。负责人：ZQO。

GameState 只保存可序列化的数据（字符串、整数、列表、字典），
存档模块（LJ）直接调用 to_dict / from_dict。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GameState:
    story_id: str
    scene: str
    flags: list[str] = field(default_factory=list)
    inventory: list[str] = field(default_factory=list)
    vars: dict[str, int] = field(default_factory=dict)
    visited: list[str] = field(default_factory=list)
    used_choices: list[str] = field(default_factory=list)   # "场景id/选项id"
    fired_triggers: list[str] = field(default_factory=list)
    turn: int = 0
    ending: str | None = None
    history: list[str] = field(default_factory=list)       # 玩家原始输入，供回放
    ext: dict[str, Any] = field(default_factory=dict)       # 机制插件的状态，按插件名分区

    # ---- 便捷操作：保持列表去重且有序，方便存档对比 ----
    def has_flag(self, name: str) -> bool:
        return name in self.flags

    def set_flag(self, name: str) -> None:
        if name not in self.flags:
            self.flags.append(name)

    def clear_flag(self, name: str) -> None:
        if name in self.flags:
            self.flags.remove(name)

    def give(self, item_id: str) -> None:
        if item_id not in self.inventory:
            self.inventory.append(item_id)

    def take(self, item_id: str) -> bool:
        if item_id in self.inventory:
            self.inventory.remove(item_id)
            return True
        return False

    def plugin(self, name: str) -> dict[str, Any]:
        return self.ext.setdefault(name, {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"未知的状态字段：{sorted(unknown)}")
        return cls(**data)
