"""道具谜题机制：使用道具、组合道具。负责人：ZRS。

剧本数据段：
    "combinations": [{"items": ["a", "b"], "result": "c", "message": "..."}]
    "uses": [{"item": "a", "scene": "<可省略>", "when": <条件>, "effects": [...],
              "message": "...", "consume": false}]

v0 只实现最小闭环。ZRS 的任务见 docs/team-tasks.md 4.3（“把A用在B上”句式、模糊匹配等）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..model import Command, Issue, Story
from ..rules import Context
from ..state import GameState
from .base import Mechanic

if TYPE_CHECKING:
    from ..engine import Engine


class PuzzleMechanic(Mechanic):
    name = "puzzle"
    verbs = {
        "use": ["使用", "用", "use"],
        "combine": ["组合", "合成", "combine"],
    }

    def handle(self, engine: "Engine", cmd: Command, ctx: Context) -> bool:
        if cmd.verb == "combine":
            return self._combine(cmd.args, ctx)
        return self._use(engine, cmd.target, ctx)

    def _combine(self, args: list[str], ctx: Context) -> bool:
        if len(args) != 2:
            ctx.say("用法：组合 <物品1> <物品2>")
            return False
        ids = [resolve_item(ctx.story, ctx.state, a) for a in args]
        for raw, iid in zip(args, ids):
            if iid is None:
                ctx.say(f"你身上没有“{raw}”。")
                return False
        for combo in ctx.story.data.get("combinations", []):
            if sorted(combo["items"]) == sorted(ids):
                for iid in ids:
                    ctx.state.take(iid)
                if combo.get("message"):
                    ctx.say(combo["message"])
                ctx.state.give(combo["result"])
                item = ctx.story.items.get(combo["result"])
                ctx.say(f"【获得物品】{item.name if item else combo['result']}")
                return True
        ctx.say("这两样东西组合不到一起。")
        return False

    def _use(self, engine: "Engine", target: str, ctx: Context) -> bool:
        if not target:
            ctx.say("用法：使用 <物品>")
            return False
        iid = resolve_item(ctx.story, ctx.state, target)
        if iid is None:
            ctx.say(f"你身上没有“{target}”。")
            return False
        for rule in ctx.story.data.get("uses", []):
            if rule["item"] != iid:
                continue
            if rule.get("scene") and rule["scene"] != ctx.state.scene:
                continue
            if not engine.registry.check(ctx, rule.get("when")):
                continue
            if rule.get("message"):
                ctx.say(rule["message"])
            if rule.get("consume"):
                ctx.state.take(iid)
            engine.registry.apply(ctx, rule.get("effects", []))
            return True
        ctx.say("这里用不上它。")
        return False

    def help_lines(self) -> list[str]:
        return ["道具命令：使用 <物品>、组合 <物品1> <物品2>。"]

    def validate(self, story: Story) -> list[Issue]:
        issues: list[Issue] = []
        for i, combo in enumerate(story.data.get("combinations", [])):
            for iid in list(combo.get("items", [])) + [combo.get("result")]:
                if iid not in story.items:
                    issues.append(Issue("error", f"combinations[{i}]", f"物品不存在：{iid}"))
        for i, rule in enumerate(story.data.get("uses", [])):
            if rule.get("item") not in story.items:
                issues.append(Issue("error", f"uses[{i}].item", f"物品不存在：{rule.get('item')}"))
            if rule.get("scene") and rule["scene"] not in story.scenes:
                issues.append(Issue("error", f"uses[{i}].scene", f"场景不存在：{rule['scene']}"))
        return issues


def use_effects(story: Story) -> list[tuple[str, dict]]:
    """道具使用规则里的效果，validator 用它计算可达性与引用检查。"""
    return [
        (f"uses[{i}].effects[{j}]", e)
        for i, rule in enumerate(story.data.get("uses", []))
        for j, e in enumerate(rule.get("effects", []))
    ]


def resolve_item(story: Story, state: GameState, text: str) -> str | None:
    """按 id、名称或别名在背包中查找物品。"""
    text = text.strip().lower()
    for iid in state.inventory:
        item = story.items.get(iid)
        names = [iid] + ([item.name] + item.aliases if item else [])
        if text in (n.lower() for n in names):
            return iid
    return None
