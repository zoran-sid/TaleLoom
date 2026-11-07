"""剧本静态校验。负责人：YHT。

在不运行游戏的情况下发现剧本错误：引用不存在的场景/物品/线索、未知条件或效果、
场景不可达、没有结局、非结局场景无路可走等。返回 Issue 列表而不是抛异常，
方便一次性列出全部问题。
"""

from __future__ import annotations

from collections import deque

from .mechanics import available, create_mechanic
from .mechanics.mystery import accusation_targets
from .mechanics.puzzle import use_effects
from .model import Issue, Story
from .rules import default_registry
from .walk import iter_conditions, iter_effects

ITEM_CONDITIONS = {"has_item"}
ITEM_EFFECTS = {"give_item", "take_item"}


def validate(story: Story) -> list[Issue]:
    issues: list[Issue] = []
    registry = default_registry()
    mechanics = []
    for name in story.mechanics:
        try:
            mech = create_mechanic(name)
        except ValueError as exc:
            issues.append(Issue("error", "mechanics", str(exc)))
            continue
        mech.register(registry)
        mechanics.append(mech)

    if story.start not in story.scenes:
        issues.append(Issue("error", "start", f"起始场景不存在：{story.start}"))

    issues += _check_references(story, registry)
    for mech in mechanics:
        issues += mech.validate(story)
    issues += _check_graph(story)
    return issues


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]


def _owner_hint(kind: str, key: str) -> str:
    for name in available():
        mech = create_mechanic(name)
        provided = mech.provides_conditions if kind == "条件" else mech.provides_effects
        if key in provided:
            return f"（需要在 mechanics 中启用 {name}）"
    return ""


def _check_references(story: Story, registry) -> list[Issue]:
    issues = []
    for path, key, arg in iter_conditions(story):
        if key not in registry.conditions:
            issues.append(Issue("error", path, f"未知条件：{key}{_owner_hint('条件', key)}"))
        elif key in ITEM_CONDITIONS and arg not in story.items:
            issues.append(Issue("error", path, f"物品不存在：{arg}"))
    for path, key, arg in iter_effects(story):
        if key not in registry.effects:
            issues.append(Issue("error", path, f"未知效果：{key}{_owner_hint('效果', key)}"))
        elif key in ITEM_EFFECTS and arg not in story.items:
            issues.append(Issue("error", path, f"物品不存在：{arg}"))
        elif key == "goto" and arg not in story.scenes:
            issues.append(Issue("error", path, f"跳转目标不存在：{arg}"))
    for sid, scene in story.scenes.items():
        seen = set()
        for c in scene.choices:
            if c.id in seen:
                issues.append(Issue("error", f"scenes.{sid}.choices.{c.id}", "选项 id 重复"))
            seen.add(c.id)
            if c.goto and c.goto not in story.scenes:
                issues.append(Issue("error", f"scenes.{sid}.choices.{c.id}.goto", f"跳转目标不存在：{c.goto}"))
    return issues


def _check_graph(story: Story) -> list[Issue]:
    """只看结构、不看条件：能否从起点走到每个场景，是否有结局。"""
    issues = []
    endings = story.endings()
    if not endings:
        issues.append(Issue("error", "scenes", "剧本没有任何结局场景（scene.ending）"))

    # 全局出口：每回合效果、触发器、道具使用、指认，可能在任何场景发生
    global_exits = {a for p, k, a in iter_effects(story) if k == "goto" and _is_global(p)}
    global_exits |= {e["goto"] for _, e in use_effects(story) if "goto" in e}
    if "mystery" in story.mechanics:
        global_exits |= set(accusation_targets(story))

    edges: dict[str, set[str]] = {}
    for sid, scene in story.scenes.items():
        out = set()
        for c in scene.choices:
            if c.goto:
                out.add(c.goto)
            out |= {e["goto"] for e in c.effects if "goto" in e}
        out |= {e["goto"] for e in scene.on_enter if "goto" in e}
        edges[sid] = out

    if story.start in story.scenes:
        seen = {story.start} | (global_exits & set(story.scenes))
        queue = deque(seen)
        while queue:
            for nxt in edges.get(queue.popleft(), ()):
                if nxt in story.scenes and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        for sid in story.scenes:
            if sid not in seen:
                level = "error" if sid in endings else "warning"
                issues.append(Issue(level, f"scenes.{sid}", "从起始场景无法到达"))

    for sid, scene in story.scenes.items():
        if not scene.ending and not edges[sid] and not global_exits:
            issues.append(Issue("warning", f"scenes.{sid}", "非结局场景没有任何出口"))
    return issues


def _is_global(path: str) -> bool:
    return path.startswith(("every_turn", "triggers"))
