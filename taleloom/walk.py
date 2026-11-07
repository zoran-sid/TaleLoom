"""遍历剧本中所有条件与效果，供 validator 和各插件的 validate() 使用。负责人：YHT。"""

from __future__ import annotations

from typing import Any, Iterator

from .model import Story


def iter_conditions(story: Story) -> Iterator[tuple[str, str, Any]]:
    """产出 (位置, 条件名, 参数)，会展开 all / any / not。"""
    for sid, scene in story.scenes.items():
        for c in scene.choices:
            if c.when:
                yield from _expand(f"scenes.{sid}.choices.{c.id}.when", c.when)
    for t in story.triggers:
        yield from _expand(f"triggers.{t.id}.when", t.when)


def iter_effects(story: Story) -> Iterator[tuple[str, str, Any]]:
    """产出 (位置, 效果名, 参数)。插件数据段里的效果由插件自己遍历。"""
    for i, e in enumerate(story.every_turn):
        yield (f"every_turn[{i}]", *_single(e))
    for t in story.triggers:
        for i, e in enumerate(t.effects):
            yield (f"triggers.{t.id}.effects[{i}]", *_single(e))
    for sid, scene in story.scenes.items():
        for i, e in enumerate(scene.on_enter):
            yield (f"scenes.{sid}.on_enter[{i}]", *_single(e))
        for c in scene.choices:
            for i, e in enumerate(c.effects):
                yield (f"scenes.{sid}.choices.{c.id}.effects[{i}]", *_single(e))


def expand_condition(path: str, cond: dict | None) -> Iterator[tuple[str, str, Any]]:
    if cond:
        yield from _expand(path, cond)


def _expand(path: str, cond: dict) -> Iterator[tuple[str, str, Any]]:
    for key, arg in cond.items():
        yield (path, key, arg)
        if key in ("all", "any") and isinstance(arg, list):
            for i, sub in enumerate(arg):
                if isinstance(sub, dict):
                    yield from _expand(f"{path}.{key}[{i}]", sub)
        elif key == "not" and isinstance(arg, dict):
            yield from _expand(f"{path}.not", arg)


def _single(effect: dict) -> tuple[str, Any]:
    ((key, arg),) = effect.items()
    return key, arg
