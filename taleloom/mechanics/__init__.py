"""机制插件注册表。新增插件时在 _FACTORIES 中登记一行。"""

from __future__ import annotations

from typing import Callable

from .base import Mechanic


def _mystery() -> Mechanic:
    from .mystery import MysteryMechanic
    return MysteryMechanic()


def _puzzle() -> Mechanic:
    from .puzzle import PuzzleMechanic
    return PuzzleMechanic()


_FACTORIES: dict[str, Callable[[], Mechanic]] = {
    "mystery": _mystery,   # ZC：线索、搜证、指认
    "puzzle": _puzzle,     # ZRS：道具使用与组合
}


def available() -> list[str]:
    return sorted(_FACTORIES)


def create_mechanic(name: str) -> Mechanic:
    try:
        return _FACTORIES[name]()
    except KeyError:
        raise ValueError(f"未知的机制插件：{name}（可用：{', '.join(available())}）") from None
