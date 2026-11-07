"""条件与效果的解释器。负责人：ZQO。

剧本里的条件写成 ``{"has_item": "lamp"}``，效果写成 ``{"add_var": ["oxygen", -1]}``。
Registry 把键名映射到 Python 函数；机制插件通过 register_condition /
register_effect 扩展，不需要改引擎核心。
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any, Callable

from .model import Story
from .state import GameState


class RuleError(ValueError):
    """剧本里出现了无法执行的条件或效果。"""


@dataclass
class Context:
    """一次效果执行的上下文：效果函数通过它修改状态、输出文字或请求跳转。"""

    story: Story
    state: GameState
    lines: list[str] = field(default_factory=list)
    goto: str | None = None

    def say(self, text: str) -> None:
        self.lines.append(text)


ConditionFn = Callable[[Context, Any], bool]
EffectFn = Callable[[Context, Any], None]

_OPS = {
    "==": operator.eq, "!=": operator.ne, "<": operator.lt,
    "<=": operator.le, ">": operator.gt, ">=": operator.ge,
}


class Registry:
    def __init__(self) -> None:
        self.conditions: dict[str, ConditionFn] = {}
        self.effects: dict[str, EffectFn] = {}

    def register_condition(self, name: str, fn: ConditionFn) -> None:
        if name in self.conditions:
            raise RuleError(f"条件 {name} 已被注册")
        self.conditions[name] = fn

    def register_effect(self, name: str, fn: EffectFn) -> None:
        if name in self.effects:
            raise RuleError(f"效果 {name} 已被注册")
        self.effects[name] = fn

    # ---- 求值 ----
    def check(self, ctx: Context, cond: dict | None) -> bool:
        """空条件为真；一个字典里有多个键时视为全部满足（隐式 all）。"""
        if not cond:
            return True
        for key, arg in cond.items():
            fn = self.conditions.get(key)
            if fn is None:
                raise RuleError(f"未知条件：{key}")
            if not fn(ctx, arg):
                return False
        return True

    def apply(self, ctx: Context, effects: list[dict]) -> None:
        for effect in effects:
            ((key, arg),) = effect.items()
            fn = self.effects.get(key)
            if fn is None:
                raise RuleError(f"未知效果：{key}")
            fn(ctx, arg)


def _var_compare(ctx: Context, arg: Any) -> bool:
    name, op, value = arg
    if op not in _OPS:
        raise RuleError(f"var 条件不支持运算符 {op}")
    return _OPS[op](ctx.state.vars.get(name, 0), value)


def _set_var(ctx: Context, arg: Any) -> None:
    name, value = arg
    ctx.state.vars[name] = value


def _add_var(ctx: Context, arg: Any) -> None:
    name, delta = arg
    ctx.state.vars[name] = ctx.state.vars.get(name, 0) + delta


def _give(ctx: Context, item_id: str) -> None:
    ctx.state.give(item_id)
    item = ctx.story.items.get(item_id)
    ctx.say(f"【获得物品】{item.name if item else item_id}")


def _take(ctx: Context, item_id: str) -> None:
    if ctx.state.take(item_id):
        item = ctx.story.items.get(item_id)
        ctx.say(f"【失去物品】{item.name if item else item_id}")


def _goto(ctx: Context, scene_id: str) -> None:
    ctx.goto = scene_id


def default_registry() -> Registry:
    r = Registry()
    r.register_condition("all", lambda ctx, conds: all(r.check(ctx, c) for c in conds))
    r.register_condition("any", lambda ctx, conds: any(r.check(ctx, c) for c in conds))
    r.register_condition("not", lambda ctx, cond: not r.check(ctx, cond))
    r.register_condition("flag", lambda ctx, name: ctx.state.has_flag(name))
    r.register_condition("has_item", lambda ctx, item: item in ctx.state.inventory)
    r.register_condition("visited", lambda ctx, scene: scene in ctx.state.visited)
    r.register_condition("var", _var_compare)

    r.register_effect("set_flag", lambda ctx, name: ctx.state.set_flag(name))
    r.register_effect("clear_flag", lambda ctx, name: ctx.state.clear_flag(name))
    r.register_effect("give_item", _give)
    r.register_effect("take_item", _take)
    r.register_effect("set_var", _set_var)
    r.register_effect("add_var", _add_var)
    r.register_effect("say", lambda ctx, text: ctx.say(text))
    r.register_effect("goto", _goto)
    return r
