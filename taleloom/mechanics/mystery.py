"""推理机制：线索收集与指认结局。负责人：ZC。

剧本数据段：
    "clues": {"<线索id>": {"name": "...", "text": "..."}}
    "accusation": {
        "when": <条件，可省略>,
        "suspects": {"<嫌疑人id>": {"name": "...", "aliases": [...]}},
        "outcomes": [{"suspect": "<id>", "when": <条件>, "goto": "<结局场景>"}],
        "default": "<没有匹配时的结局场景>"
    }

v0 只实现最小闭环。ZC 的任务见 docs/team-tasks.md 4.4（深入搜证、分轮线索、审问对话等）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..model import Command, Issue, Story
from ..rules import Context, Registry
from ..walk import expand_condition, iter_conditions, iter_effects
from .base import Mechanic

if TYPE_CHECKING:
    from ..engine import Engine


class MysteryMechanic(Mechanic):
    name = "mystery"
    verbs = {
        "clues": ["线索", "笔记", "clues", "notes"],
        "accuse": ["指认", "指控", "accuse"],
    }
    provides_conditions = ("has_clue",)
    provides_effects = ("add_clue",)

    def register(self, registry: Registry) -> None:
        registry.register_condition("has_clue", lambda ctx, cid: cid in self._found(ctx))
        registry.register_effect("add_clue", self._add_clue)

    # ---- 状态 ----
    @staticmethod
    def _found(ctx: Context) -> list[str]:
        return ctx.state.plugin("mystery").setdefault("clues", [])

    def _add_clue(self, ctx: Context, clue_id: str) -> None:
        found = self._found(ctx)
        if clue_id in found:
            return
        found.append(clue_id)
        clue = ctx.story.data.get("clues", {}).get(clue_id, {})
        ctx.say(f"【获得线索】{clue.get('name', clue_id)}：{clue.get('text', '')}".rstrip("："))

    # ---- 命令 ----
    def handle(self, engine: "Engine", cmd: Command, ctx: Context) -> bool:
        if cmd.verb == "clues":
            self._list_clues(ctx)
            return False
        return self._accuse(engine, cmd.target, ctx)

    def _list_clues(self, ctx: Context) -> None:
        found = self._found(ctx)
        if not found:
            ctx.say("你的笔记本还是空的。")
            return
        clues = ctx.story.data.get("clues", {})
        ctx.say(f"已收集线索（{len(found)}/{len(clues)}）：")
        for cid in found:
            clue = clues.get(cid, {})
            ctx.say(f"  · {clue.get('name', cid)}：{clue.get('text', '')}")

    def _accuse(self, engine: "Engine", target: str, ctx: Context) -> bool:
        acc = ctx.story.data.get("accusation")
        if not acc:
            ctx.say("这个故事里不需要指认任何人。")
            return False
        if not engine.registry.check(ctx, acc.get("when")):
            ctx.say("你还没有足够的把握，现在不是指认的时候。")
            return False
        suspects: dict[str, Any] = acc.get("suspects", {})
        names = "、".join(s.get("name", sid) for sid, s in suspects.items())
        if not target:
            ctx.say(f"你要指认谁？可选：{names}")
            return False
        sid = _resolve(suspects, target)
        if sid is None:
            ctx.say(f"嫌疑人里没有“{target}”。可选：{names}")
            return False
        ctx.say(f"你指认了{suspects[sid].get('name', sid)}。")
        for outcome in acc.get("outcomes", []):
            if outcome.get("suspect") == sid and engine.registry.check(ctx, outcome.get("when")):
                ctx.goto = outcome["goto"]
                return True
        ctx.goto = acc.get("default")
        return True

    def help_lines(self) -> list[str]:
        return ["推理命令：线索（查看笔记）、指认 <嫌疑人>（给出你的结论）。"]

    # ---- 校验 ----
    def validate(self, story: Story) -> list[Issue]:
        issues: list[Issue] = []
        clues = story.data.get("clues", {})
        refs = [(p, a) for p, k, a in iter_effects(story) if k == "add_clue"]
        refs += [(p, a) for p, k, a in iter_conditions(story) if k == "has_clue"]
        acc = story.data.get("accusation")
        if acc:
            refs += [(p, a) for p, k, a in expand_condition("accusation.when", acc.get("when")) if k == "has_clue"]
            suspects = acc.get("suspects", {})
            for i, o in enumerate(acc.get("outcomes", [])):
                path = f"accusation.outcomes[{i}]"
                refs += [(p, a) for p, k, a in expand_condition(f"{path}.when", o.get("when")) if k == "has_clue"]
                if o.get("suspect") not in suspects:
                    issues.append(Issue("error", path, f"嫌疑人不存在：{o.get('suspect')}"))
                if o.get("goto") not in story.scenes:
                    issues.append(Issue("error", path, f"结局场景不存在：{o.get('goto')}"))
            if acc.get("default") not in story.scenes:
                issues.append(Issue("error", "accusation.default", f"场景不存在：{acc.get('default')}"))
        for path, cid in refs:
            if cid not in clues:
                issues.append(Issue("error", path, f"线索不存在：{cid}"))
        return issues


def accusation_targets(story: Story) -> list[str]:
    """指认可能到达的场景，validator 用它计算可达性。"""
    acc = story.data.get("accusation") or {}
    targets = [o.get("goto") for o in acc.get("outcomes", [])]
    if acc.get("default"):
        targets.append(acc["default"])
    return [t for t in targets if t]


def _resolve(suspects: dict[str, Any], text: str) -> str | None:
    text = text.strip().lower()
    for sid, s in suspects.items():
        names = [sid, s.get("name", "")] + list(s.get("aliases", []))
        if text in (n.lower() for n in names if n):
            return sid
    return None
