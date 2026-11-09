"""道具谜题机制：使用道具、组合道具、把道具用在某处。负责人：ZRS。

剧本数据段：
    "combinations": [{"items": ["a", "b"], "result": "c", "message": "..."}]
    "targets": [{"id": "panel", "name": "控制面板", "aliases": ["面板"], "scene": "airlock"}]
    "uses": [{"item": "a", "target": "panel", "scene": "<可省略>", "when": <条件>,
              "effects": [...], "message": "...", "consume": false}]

玩家命令："使用 扳手"（在当前场景直接使用）、"把 扳手 用在 控制面板 上"、
"组合 扳手 胶带"。没有 target 的使用规则仍按场景匹配，旧剧本不用改。

界面候选与说明由 build_actions 生成：只含玩家已知的物品和当前场景声明的
目标，不提示正确配方或使用结果。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..model import Command, Issue, Story
from ..rules import Context
from ..state import GameState
from ..ui_contract import ActionParameter, ActionSpec, DisplayItem
from .base import Mechanic

if TYPE_CHECKING:
    from ..engine import Engine


class PuzzleMechanic(Mechanic):
    name = "puzzle"
    verbs = {
        "use": ["使用", "用", "use"],
        "use_on": [],          # 只由图形界面的 puzzle:use_on 动作提交，不占用文字命令
        "combine": ["组合", "合成", "combine"],
    }

    def handle(self, engine: "Engine", cmd: Command, ctx: Context) -> bool:
        if cmd.verb == "combine":
            return self._combine(cmd.args, ctx)
        return self._use(engine, cmd.args, ctx)

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

    def _use(self, engine: "Engine", args: list[str], ctx: Context) -> bool:
        if not args:
            ctx.say("用法：使用 <物品>，或“把 <物品> 用在 <目标> 上”。")
            return False
        if len(args) > 2:
            ctx.say("一次只能对一件物品或一个目标使用。")
            return False
        iid = resolve_item(ctx.story, ctx.state, args[0])
        if iid is None:
            ctx.say(f"你身上没有“{args[0]}”。")
            return False
        target = None
        if len(args) == 2:
            target = resolve_target(ctx.story, args[1], ctx.state.scene)
            if target is None:
                ctx.say(f"这里没有可以这样用“{args[1]}”的东西。")
                return False
        for rule in ctx.story.data.get("uses", []):
            if rule["item"] != iid or rule.get("target") != target:
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
        return ["道具命令：使用 <物品>、把 <物品> 用在 <目标> 上、组合 <物品1> <物品2>。"]

    def validate(self, story: Story) -> list[Issue]:
        issues: list[Issue] = []
        for i, combo in enumerate(story.data.get("combinations", [])):
            for iid in list(combo.get("items", [])) + [combo.get("result")]:
                if iid not in story.items:
                    issues.append(Issue("error", f"combinations[{i}]", f"物品不存在：{iid}"))
        target_ids: set[str] = set()
        for i, target in enumerate(target_data(story)):
            if not isinstance(target, dict) or not isinstance(target.get("id"), str) or not target["id"].strip():
                issues.append(Issue("error", f"targets[{i}].id", "目标 id 应为非空字符串"))
                continue
            if target["id"] in target_ids:
                issues.append(Issue("error", f"targets[{i}].id", f"目标 id 重复：{target['id']}"))
            target_ids.add(target["id"])
            if target.get("scene") and target["scene"] not in story.scenes:
                issues.append(Issue("error", f"targets[{i}].scene", f"场景不存在：{target['scene']}"))
        for i, rule in enumerate(story.data.get("uses", [])):
            if rule.get("item") not in story.items:
                issues.append(Issue("error", f"uses[{i}].item", f"物品不存在：{rule.get('item')}"))
            if rule.get("scene") and rule["scene"] not in story.scenes:
                issues.append(Issue("error", f"uses[{i}].scene", f"场景不存在：{rule['scene']}"))
            if rule.get("target") is not None and rule["target"] not in target_ids:
                issues.append(Issue(
                    "error", f"uses[{i}].target",
                    f"目标不存在：{rule['target']}。建议：在 targets 中声明该目标，或删掉 target 字段。",
                ))
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


def resolve_target(story: Story, text: str, scene: str) -> str | None:
    """按 id、名称或别名查找当前场景可用的目标。"""
    text = text.strip().lower()
    for target in available_targets(story, scene):
        names = [target["id"], target.get("name", "")] + list(target.get("aliases", []))
        if text in (n.lower() for n in names if isinstance(n, str)):
            return target["id"]
    return None


def available_targets(story: Story, scene: str) -> list[dict]:
    """当前场景可以互动的目标；未声明 scene 的目标在所有场景可用。"""
    return [
        target for target in target_data(story)
        if isinstance(target, dict) and isinstance(target.get("id"), str)
        and (not target.get("scene") or target.get("scene") == scene)
    ]


def build_actions(story: Story, state: GameState, inventory: list[DisplayItem]) -> list[ActionSpec]:
    """生成道具动作及候选；只使用玩家已知的物品与当前场景目标。

    背包为空或故事已结束时不生成动作；组合需要至少两件物品；
    “用在某处”只在当前场景声明了目标时出现。动作 ID 固定为
    puzzle:use / puzzle:use_on / puzzle:combine，界面提交 ID 而不是中文命令。
    """
    if not inventory or state.ending:
        return []
    actions = [ActionSpec("puzzle:use", "使用道具", [ActionParameter("item", "物品", options=inventory)])]
    targets = [
        DisplayItem(target["id"], target.get("name", target["id"]), target.get("description", ""))
        for target in available_targets(story, state.scene)
    ]
    if targets:
        actions.append(ActionSpec("puzzle:use_on", "把道具用在某处", [
            ActionParameter("item", "物品", options=inventory),
            ActionParameter("target", "目标", options=targets),
        ]))
    if len(inventory) >= 2:
        actions.append(ActionSpec("puzzle:combine", "组合道具", [
            ActionParameter("first", "第一件物品", options=inventory),
            ActionParameter("second", "第二件物品", options=inventory),
        ]))
    return actions


def target_data(story: Story) -> list:
    """剧本声明的目标列表；数据写坏时返回空列表，由 validate 报告问题。"""
    targets = story.data.get("targets", [])
    return targets if isinstance(targets, list) else []
