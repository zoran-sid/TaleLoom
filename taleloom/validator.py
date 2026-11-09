"""剧本静态校验。负责人：YHT。

在不运行游戏的情况下发现剧本错误：条件/效果参数类型不对、引用不存在的
场景/物品/线索、未知条件或效果、场景不可达、没有结局、死路、陷阱环、
一次性出口耗尽、未使用物品等。返回 Issue 列表而不是抛异常，方便一次性
列出全部问题；format_report() 把问题按场景整理成可读报告。
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from .mechanics import available, create_mechanic
from .mechanics.mystery import accusation_targets
from .mechanics.puzzle import use_effects
from .model import Issue, Story
from .rules import default_registry
from .walk import expand_condition, iter_conditions, iter_effects

ITEM_CONDITIONS = {"has_item"}
ITEM_EFFECTS = {"give_item", "take_item"}
STRING_CONDITIONS = {"flag", "visited", "has_item"}
STRING_EFFECTS = {"set_flag", "clear_flag", "give_item", "take_item", "goto", "say"}
OPS = {"==", "!=", "<", "<=", ">", ">="}


def validate(story: Story) -> list[Issue]:
    """校验整个剧本，返回按发现顺序排列的 Issue 列表。"""
    issues: list[Issue] = []
    registry = default_registry()
    mechanics = []
    seen_mechanics: set[str] = set()
    for name in story.mechanics:
        if name in seen_mechanics:
            issues.append(Issue(
                "error", "mechanics",
                f"机制插件重复启用：{name}。建议：从 mechanics 中删掉重复的插件名。",
            ))
            continue
        seen_mechanics.add(name)
        try:
            mech = create_mechanic(name)
        except ValueError as exc:
            issues.append(Issue(
                "error", "mechanics",
                f"{exc}。建议：检查 mechanics 中的插件名，可用插件：{', '.join(available())}。",
            ))
            continue
        try:
            mech.register(registry)
        except Exception as exc:   # 插件注册冲突时也要继续校验，而不是崩溃
            issues.append(Issue(
                "error", "mechanics",
                f"机制插件 {name} 无法启用：{exc}。建议：检查插件名是否重复，"
                "或联系插件负责人确认注册的条件/效果。",
            ))
            continue
        mechanics.append(mech)

    if story.start not in story.scenes:
        issues.append(Issue(
            "error", "start",
            f"起始场景不存在：{story.start}。建议：把 start 改成 scenes 中已存在的 id。",
        ))

    issues += _check_parameters(story)
    issues += _check_display(story)
    issues += _check_references(story, registry)
    for mech in mechanics:
        try:
            plugin_issues = mech.validate(story)
        except Exception as exc:   # 插件数据格式错误也不能让 validate 崩溃
            issues.append(Issue(
                "error", "mechanics",
                f"插件 {getattr(mech, 'name', '?')} 校验数据时出错：{exc}。"
                "建议：检查该插件数据段的字段类型。",
            ))
        else:
            issues += plugin_issues
    issues += _check_graph(story)
    issues += _check_structure(story)
    return issues


def errors(issues: list[Issue]) -> list[Issue]:
    """只保留 error 级别的问题。"""
    return [i for i in issues if i.level == "error"]


def format_report(issues: list[Issue], story: Story | None = None) -> str:
    """把 Issue 按场景分组，拼成方便直接阅读的报告；没有问题时返回空字符串。"""
    if not issues:
        return ""

    groups: dict[str, list[Issue]] = {}
    labels: dict[str, str] = {}
    for issue in issues:
        key, label = _group_name(issue.path, story)
        groups.setdefault(key, []).append(issue)
        labels[key] = label

    scene_order = []
    if story is not None:
        scene_order = [f"scene:{sid}" for sid in story.scenes if f"scene:{sid}" in groups]
    for key in sorted(groups):
        if key.startswith("scene:") and key not in scene_order:
            scene_order.append(key)

    other_order = ["global", "mechanics", "items", "display", "plugin"]
    order = scene_order + [k for k in other_order if k in groups]
    lines = []
    for key in order:
        bucket = groups[key]
        bucket.sort(key=lambda i: (i.level != "error", i.path))
        lines.append(f"{labels[key]}（{len(bucket)} 个问题）")
        for issue in bucket:
            headline, suggestion = _split_suggestion(issue)
            lines.append(f"  [{issue.level}] {issue.path}: {headline}")
            if suggestion:
                lines.append(f"      建议：{suggestion}")
    return "\n".join(lines)


def render_mermaid(story: Story) -> str:
    """把场景与跳转导出为 Mermaid flowchart 文本。"""
    lines = ["flowchart TD"]
    if not story.scenes:
        return "\n".join(lines)
    node = {sid: f"n{i}" for i, sid in enumerate(story.scenes)}
    lines.append('    __start__(["开始"])')
    for sid, scene in story.scenes.items():
        label = sid if not scene.title else f"{sid}<br/>{scene.title}"
        lines.append(f'    {node[sid]}["{_escape(label)}"]')

    for sid, scene in story.scenes.items():
        for choice in scene.choices:
            targets = []
            if choice.goto in story.scenes:
                targets.append((choice.goto, ""))
            for effect in choice.effects:
                target = effect.get("goto")
                if isinstance(target, str) and target in story.scenes:
                    targets.append((target, "（效果）"))
            for target, suffix in targets:
                label = _escape(choice.text) + ("（一次性）" if choice.once else "") + suffix
                lines.append(f'    {node[sid]} -->|"{label}"| {node[target]}')
        for effect in scene.on_enter:
            target = effect.get("goto")
            if isinstance(target, str) and target in story.scenes:
                lines.append(f'    {node[sid]} -.->|"进入时"| {node[target]}')

    global_targets = _global_exit_targets(story)
    if global_targets:
        lines.append('    __global__(["任意时刻可用的出口"])')
        for target in sorted(global_targets):
            lines.append(f'    __global__ -.->|"任意时刻"| {node[target]}')

    if story.start in story.scenes:
        lines.append(f"    __start__ --> {node[story.start]}")
    lines.append("    classDef ending fill:#fde68a,stroke:#92400e,stroke-width:2px;")
    ending_nodes = [node[sid] for sid, scene in story.scenes.items() if scene.ending]
    if ending_nodes:
        lines.append(f"    class {','.join(ending_nodes)} ending;")
    return "\n".join(lines)


def _escape(text: str) -> str:
    """转义 Mermaid 标签里的引号与换行。"""
    return text.replace("\\", "\\\\").replace('"', "#quot;").replace("\n", "<br/>")


# ---- 参数类型 ----

def _check_parameters(story: Story) -> list[Issue]:
    issues = _check_plugin_effects(story)
    for path, key, arg in _all_conditions(story):
        problem = _condition_problem(key, arg)
        if problem:
            issues.append(Issue("error", path, problem))
    for path, key, arg in _all_effects(story):
        problem = _effect_problem(key, arg)
        if problem:
            issues.append(Issue("error", path, problem))
    return issues


def _check_display(story: Story) -> list[Issue]:
    """检查公开资源与素材这些可选展示字段。"""
    issues: list[Issue] = []
    seen_vars: set[str] = set()
    for i, resource in enumerate(story.resources):
        path = f"resources[{i}]"
        var = getattr(resource, "var", None)
        name = getattr(resource, "name", None)
        maximum = getattr(resource, "maximum", None)
        if not isinstance(var, str) or not var.strip():
            issues.append(Issue(
                "error", f"{path}.var",
                "公开资源的变量名必须是非空字符串。建议：填写 vars 中的变量名，例如 oxygen。",
            ))
        elif var in seen_vars:
            issues.append(Issue(
                "error", f"{path}.var",
                f"公开资源变量重复：{var}。建议：每个变量只声明一次。",
            ))
        else:
            seen_vars.add(var)
        if not isinstance(name, str) or not name.strip():
            issues.append(Issue(
                "error", f"{path}.name",
                "公开资源的显示名称必须是非空字符串。建议：填写玩家看到的名称，例如 氧气。",
            ))
        if maximum is not None:
            if isinstance(maximum, bool) or not isinstance(maximum, int):
                issues.append(Issue(
                    "error", f"{path}.max",
                    "公开资源的上限必须是整数。建议：填写正整数，或省略 max。",
                ))
            elif maximum <= 0:
                issues.append(Issue(
                    "error", f"{path}.max",
                    "公开资源的上限必须大于 0。建议：填写正整数，或省略 max。",
                ))

    if not isinstance(story.assets, dict):
        issues.append(Issue(
            "error", "assets",
            "素材字段应为角色到路径的对象。建议：写成 {\"background\": \"assets/bg.png\"}。",
        ))
        return issues
    root = Path(story.source_dir) if story.source_dir else None
    for role, asset in story.assets.items():
        path = f"assets.{role}"
        if not isinstance(role, str) or not role.strip():
            issues.append(Issue(
                "error", "assets",
                "素材角色必须是非空字符串。建议：使用 background、portrait 等角色名。",
            ))
            continue
        if not isinstance(asset, str) or not asset.strip():
            issues.append(Issue(
                "error", path,
                "素材路径必须是非空字符串。建议：填写剧本目录内的相对路径。",
            ))
            continue
        if root is not None and not (root / asset).is_file():
            issues.append(Issue(
                "warning", path,
                f"素材文件不存在：{asset}。建议：把文件放到剧本目录下，或删除这个引用；"
                "缺少素材仍可文字通关。",
            ))
    return issues


def _check_plugin_effects(story: Story) -> list[Issue]:
    """检查插件数据段里效果列表的外壳，避免坏数据让后续遍历崩溃。"""
    issues = []
    uses = story.data.get("uses")
    if not isinstance(uses, list):
        return issues
    for i, rule in enumerate(uses):
        if not isinstance(rule, dict):
            continue
        if "when" in rule and not isinstance(rule["when"], dict):
            issues.append(Issue(
                "error", f"uses[{i}].when",
                f"效果使用规则的 when 应为条件对象，实际为 {_type_name(rule['when'])}。"
                "建议：把 when 写成 {\"flag\": \"名称\"} 这样的条件对象。",
            ))
        effects = rule.get("effects")
        if effects is None:
            continue
        if not isinstance(effects, list):
            issues.append(Issue(
                "error", f"uses[{i}].effects",
                f"效果使用规则的 effects 应为数组，实际为 {_type_name(effects)}。"
                "建议：把 effects 写成 [{\"set_flag\": \"名称\"}] 这样的数组。",
            ))
            continue
        for j, effect in enumerate(effects):
            if not isinstance(effect, dict):
                issues.append(Issue(
                    "error", f"uses[{i}].effects[{j}]",
                    f"效果应为对象，实际为 {_type_name(effect)}。"
                    "建议：每个效果写成只有一个键的对象，例如 {\"say\": \"文字\"}。",
                ))
            elif len(effect) != 1:
                issues.append(Issue(
                    "error", f"uses[{i}].effects[{j}]",
                    "每个效果只能有一个键。"
                    "建议：把一个效果拆成多个对象，每个对象只保留一个键。",
                ))
    return issues


def _all_conditions(story: Story):
    """遍历核心字段与插件数据段里的所有条件（含 all / any / not 内部）。"""
    yield from iter_conditions(story)
    accusation = story.data.get("accusation")
    if isinstance(accusation, dict):
        when = accusation.get("when")
        if isinstance(when, dict):
            yield from expand_condition("accusation.when", when)
        outcomes = accusation.get("outcomes")
        if isinstance(outcomes, list):
            for i, outcome in enumerate(outcomes):
                if isinstance(outcome, dict) and isinstance(outcome.get("when"), dict):
                    yield from expand_condition(
                        f"accusation.outcomes[{i}].when", outcome["when"]
                    )
    uses = story.data.get("uses")
    if isinstance(uses, list):
        for i, rule in enumerate(uses):
            if isinstance(rule, dict) and isinstance(rule.get("when"), dict):
                yield from expand_condition(f"uses[{i}].when", rule["when"])


def _all_effects(story: Story):
    """遍历核心字段与插件数据段里的所有效果。"""
    yield from iter_effects(story)
    uses = story.data.get("uses")
    if isinstance(uses, list):
        for i, rule in enumerate(uses):
            if not isinstance(rule, dict):
                continue
            effects = rule.get("effects")
            if isinstance(effects, list):
                for j, effect in enumerate(effects):
                    if isinstance(effect, dict) and len(effect) == 1:
                        ((key, arg),) = effect.items()
                        yield f"uses[{i}].effects[{j}]", key, arg


def _condition_problem(key: str, arg: Any) -> str:
    if key == "var":
        return _var_problem(arg)
    if key in STRING_CONDITIONS:
        if not isinstance(arg, str):
            return f"条件 {key} 的参数应为字符串，实际为 {_type_name(arg)}"
        if key in ("flag", "has_item") and not arg.strip():
            return f"条件 {key} 的参数不能为空"
        if key == "visited" and not arg.strip():
            return "条件 visited 的场景 id 不能为空"
        return ""
    if key in ("all", "any"):
        if not isinstance(arg, list):
            return f"条件 {key} 的参数应为条件数组，实际为 {_type_name(arg)}"
        for i, sub in enumerate(arg):
            if not isinstance(sub, dict):
                return f"条件 {key} 的第 {i + 1} 项应为条件对象，实际为 {_type_name(sub)}"
        return ""
    if key == "not":
        if not isinstance(arg, dict):
            return f"条件 not 的参数应为条件对象，实际为 {_type_name(arg)}"
    return ""


def _var_problem(arg: Any) -> str:
    if not isinstance(arg, (list, tuple)):
        return f"条件 var 的参数应为 [变量名, 比较符, 数值]，实际为 {_type_name(arg)}"
    if len(arg) != 3:
        return f"条件 var 的参数应为 3 项 [变量名, 比较符, 数值]，实际为 {len(arg)} 项"
    name, op, value = arg
    if not isinstance(name, str) or not name.strip():
        return "条件 var 的变量名应为非空字符串"
    if not isinstance(op, str) or op not in OPS:
        return f"条件 var 的运算符 {op!r} 无效，可用：== != < <= > >="
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"条件 var 的比较值应为数值，实际为 {_type_name(value)}"
    return ""


def _effect_problem(key: str, arg: Any) -> str:
    if key in ("set_var", "add_var"):
        if not isinstance(arg, (list, tuple)):
            return f"效果 {key} 的参数应为 [变量名, 整数]，实际为 {_type_name(arg)}"
        if len(arg) != 2:
            return f"效果 {key} 的参数应为 2 项 [变量名, 整数]，实际为 {len(arg)} 项"
        name, value = arg
        if not isinstance(name, str) or not name.strip():
            return f"效果 {key} 的变量名应为非空字符串"
        if isinstance(value, bool) or not isinstance(value, int):
            return f"效果 {key} 的数值应为整数，实际为 {_type_name(value)}"
        return ""
    if key in STRING_EFFECTS:
        if not isinstance(arg, str):
            return f"效果 {key} 的参数应为字符串，实际为 {_type_name(arg)}"
        if key in ("set_flag", "clear_flag", "give_item", "take_item", "goto") and not arg.strip():
            return f"效果 {key} 的参数不能为空"
    return ""


def _type_name(value: Any) -> str:
    if value is None:
        return "缺失"
    if isinstance(value, bool):
        return "布尔值"
    if isinstance(value, (int, float)):
        return "数值"
    if isinstance(value, str):
        return "字符串"
    if isinstance(value, list):
        return "数组"
    if isinstance(value, dict):
        return "对象"
    return type(value).__name__


# ---- 引用与 id ----

def _owner_hint(kind: str, key: str) -> str:
    for name in available():
        mech = create_mechanic(name)
        provided = mech.provides_conditions if kind == "条件" else mech.provides_effects
        if key in provided:
            return f"（需要在 mechanics 中启用 {name}）"
    return ""


def _check_references(story: Story, registry) -> list[Issue]:
    issues = []
    for path, key, arg in _all_conditions(story):
        if key not in registry.conditions:
            issues.append(Issue(
                "error", path,
                f"未知条件：{key}{_owner_hint('条件', key)}。建议：检查拼写，或启用提供该条件的插件。",
            ))
        elif key in ITEM_CONDITIONS and isinstance(arg, str) and arg not in story.items:
            issues.append(Issue(
                "error", path,
                f"物品不存在：{arg}。建议：在 items 中声明该物品，或修正 id。",
            ))
        elif key == "visited" and isinstance(arg, str) and arg not in story.scenes:
            issues.append(Issue(
                "error", path,
                f"场景不存在：{arg}。建议：把 visited 改成已存在的场景 id。",
            ))
    for path, key, arg in _all_effects(story):
        if key not in registry.effects:
            issues.append(Issue(
                "error", path,
                f"未知效果：{key}{_owner_hint('效果', key)}。建议：检查拼写，或启用提供该效果的插件。",
            ))
        elif key in ITEM_EFFECTS and isinstance(arg, str) and arg not in story.items:
            issues.append(Issue(
                "error", path,
                f"物品不存在：{arg}。建议：在 items 中声明该物品，或修正 id。",
            ))
        elif key == "goto" and isinstance(arg, str) and arg not in story.scenes:
            issues.append(Issue(
                "error", path,
                f"跳转目标不存在：{arg}。建议：把 goto 改成已存在的场景 id。",
            ))
    for sid, scene in story.scenes.items():
        seen = set()
        for c in scene.choices:
            if c.id in seen:
                issues.append(Issue(
                    "error", f"scenes.{sid}.choices.{c.id}",
                    "选项 id 重复。建议：同一场景内给每个选项不同的 id。",
                ))
            seen.add(c.id)
            if c.goto and c.goto not in story.scenes:
                issues.append(Issue(
                    "error", f"scenes.{sid}.choices.{c.id}.goto",
                    f"跳转目标不存在：{c.goto}。建议：把 goto 改成已存在的场景 id。",
                ))
    return issues


# ---- 图与结构 ----

def _puzzle_use_effects(story: Story) -> list[tuple[str, dict]]:
    """读取道具使用规则里的效果；插件数据写坏时不让校验器崩溃。"""
    try:
        return use_effects(story)
    except Exception:
        return []


def _global_exit_targets(story: Story) -> set[str]:
    """可能在任意场景发生的出口：every_turn、触发器、道具使用、指认。"""
    targets = {
        arg for path, key, arg in iter_effects(story)
        if key == "goto" and _is_global(path) and isinstance(arg, str)
    }
    for _, effect in _puzzle_use_effects(story):
        if not isinstance(effect, dict):
            continue
        target = effect.get("goto")
        if isinstance(target, str):
            targets.add(target)
    if "mystery" in story.mechanics:
        try:
            targets |= {t for t in accusation_targets(story) if isinstance(t, str)}
        except Exception:
            pass
    return targets & set(story.scenes)


def _scene_edges(story: Story) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {}
    for sid, scene in story.scenes.items():
        out = set()
        for choice in scene.choices:
            if choice.goto in story.scenes:
                out.add(choice.goto)
            for effect in choice.effects:
                target = effect.get("goto")
                if isinstance(target, str) and target in story.scenes:
                    out.add(target)
        for effect in scene.on_enter:
            target = effect.get("goto")
            if isinstance(target, str) and target in story.scenes:
                out.add(target)
        edges[sid] = out
    return edges


def _check_graph(story: Story) -> list[Issue]:
    """只看结构、不看条件：能否从起点走到每个场景，是否有结局。"""
    issues = []
    endings = story.endings()
    if not endings:
        issues.append(Issue(
            "error", "scenes",
            "剧本没有任何结局场景（scene.ending）。建议：至少给一个场景添加 ending。",
        ))

    edges = _scene_edges(story)
    global_exits = _global_exit_targets(story)

    if story.start in story.scenes:
        seen = {story.start} | global_exits
        queue = deque(seen)
        while queue:
            for nxt in edges.get(queue.popleft(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        for sid in story.scenes:
            if sid not in seen:
                level = "error" if sid in endings else "warning"
                issues.append(Issue(
                    level, f"scenes.{sid}",
                    "从起始场景无法到达。建议：添加通往该场景的选项或全局跳转，或删除该场景。",
                ))
    return issues


def _check_structure(story: Story) -> list[Issue]:
    issues = _check_unused_items(story)
    if not story.scenes or story.start not in story.scenes:
        return issues
    edges = _scene_edges(story)
    global_exits = _global_exit_targets(story)
    if global_exits:
        # 全局出口在每个场景都能触发，死路/陷阱环/一次性出口不会真正卡住玩家。
        return issues

    reachable = _reachable(story.start, edges)
    incoming: dict[str, set[str]] = {sid: set() for sid in story.scenes}
    for sid, targets in edges.items():
        if sid not in reachable:
            continue
        for target in targets:
            incoming[target].add(sid)

    for sid, scene in story.scenes.items():
        if scene.ending or sid not in reachable:
            continue
        if not edges.get(sid):
            issues.append(Issue(
                "error", f"scenes.{sid}",
                "非结局场景没有任何出口，玩家进入后会卡住。"
                "建议：添加 goto 选项，或把该场景设为结局。",
            ))
            continue
        exits = [c for c in scene.choices if _choice_has_exit(c)]
        if not exits:
            continue   # 只有 on_enter 自动跳转，不会卡住
        if sid not in incoming:
            continue   # 只进入一次，之后不会再回到这里
        if any(not c.once for c in exits):
            continue
        if any("goto" in effect for effect in scene.on_enter):
            continue
        issues.append(Issue(
            "error", f"scenes.{sid}",
            "该场景的出口全部是一次性选项（once），玩家再次进入时可能无路可走。"
            "建议：保留一个非一次性出口，或在 on_enter 中安排自动跳转。",
        ))

    for component in _strong_components(edges):
        if not component & reachable:
            continue
        if len(component) == 1 and not any(sid in edges.get(sid, ()) for sid in component):
            continue
        if any(story.scenes[sid].ending for sid in component):
            continue
        if any(edges[sid] - component for sid in component):
            continue
        names = "、".join(sorted(component))
        issues.append(Issue(
            "error", f"scenes.{sorted(component)[0]}",
            f"陷阱环：场景 {names} 之间可以互相跳转，但没有通往结局的出口。"
            "建议：给环内至少一个场景添加离开选项或全局出口。",
        ))
    return issues


def _choice_has_exit(choice) -> bool:
    return bool(choice.goto) or any("goto" in effect for effect in choice.effects)


def _reachable(start: str, edges: dict[str, set[str]]) -> set[str]:
    seen = {start}
    queue = deque([start])
    while queue:
        for nxt in edges.get(queue.popleft(), ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _strong_components(edges: dict[str, set[str]]) -> list[set[str]]:
    """Tarjan 强连通分量；只用标准库，场景数量小，递归足够。"""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[set[str]] = []
    counter = [0]

    def visit(node: str) -> None:
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in edges.get(node, ()):
            if nxt not in edges:
                continue
            if nxt not in index:
                visit(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            component = set()
            while True:
                nxt = stack.pop()
                on_stack.discard(nxt)
                component.add(nxt)
                if nxt == node:
                    break
            result.append(component)

    for node in edges:
        if node not in index:
            visit(node)
    return result


def _check_unused_items(story: Story) -> list[Issue]:
    if not story.items:
        return []
    used: set[str] = set()
    for _, key, arg in iter_conditions(story):
        if key in ITEM_CONDITIONS and isinstance(arg, str):
            used.add(arg)
    for _, key, arg in iter_effects(story):
        if key in ITEM_EFFECTS and isinstance(arg, str):
            used.add(arg)
    _scan_data(story.data, used)
    if not used:
        # 整篇都没有引用任何物品：这个剧本只是没有启用物品系统，
        # 逐个提示“未使用”只会制造噪声（例如测试用剧本顺带了物品表）。
        return []
    return [
        Issue(
            "warning", f"items.{item.id}",
            f"物品“{item.name}”没有被任何条件、效果或插件规则使用。"
            "建议：删除它，或在剧本/插件配置中引用。",
        )
        for item in story.items.values()
        if item.id not in used
    ]


def _scan_data(value: Any, used: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ITEM_CONDITIONS | ITEM_EFFECTS and isinstance(item, str):
                used.add(item)
            if key in ("item", "result") and isinstance(item, str):
                used.add(item)
            if key == "items" and isinstance(item, list):
                used.update(x for x in item if isinstance(x, str))
            _scan_data(item, used)
    elif isinstance(value, list):
        for item in value:
            _scan_data(item, used)


def _is_global(path: str) -> bool:
    return path.startswith(("every_turn", "triggers"))


# ---- 报告 ----

def _group_name(path: str, story: Story | None) -> tuple[str, str]:
    parts = path.split(".")
    if len(parts) >= 2 and parts[0] == "scenes":
        sid = parts[1]
        title = ""
        if story is not None and sid in story.scenes:
            title = story.scenes[sid].title
        label = f"场景 {sid}" + (f"《{title}》" if title else "")
        return f"scene:{sid}", label
    if path == "start":
        return "global", "开始与全局"
    if path == "mechanics" or path.startswith("mechanics."):
        return "mechanics", "机制插件"
    if path.startswith("items."):
        return "items", "物品"
    if path.startswith(("resources", "assets")):
        return "display", "展示字段"
    if parts[0].split("[", 1)[0] in ("clues", "accusation", "combinations", "uses"):
        return "plugin", "插件数据"
    return "global", "全局"


def _split_suggestion(issue: Issue) -> tuple[str, str]:
    headline, sep, suggestion = issue.message.partition("建议：")
    if not sep:
        suggestion = _default_suggestion(issue)
    return headline.rstrip(), suggestion.strip()


def _default_suggestion(issue: Issue) -> str:
    message = issue.message
    if "条件 var" in message:
        return "把参数写成 [变量名, 比较符, 数值]，比较符用 ==、!=、<、<=、>、>= 之一。"
    if "效果 set_var" in message or "效果 add_var" in message:
        return "把参数写成 [变量名, 整数]，例如 [\"hp\", 3]。"
    if "条件 all" in message or "条件 any" in message:
        return "把参数写成条件对象数组，例如 [{\"flag\": \"ready\"}]。"
    if "条件 not" in message:
        return "把参数写成单个条件对象，例如 {\"flag\": \"ready\"}。"
    if "参数应为字符串" in message:
        return "把参数改成字符串，例如 \"变量名\" 或 \"场景id\"。"
    if "参数应为条件数组" in message:
        return "把参数改成条件对象数组，例如 [{\"flag\": \"ready\"}]。"
    if "参数应为条件对象" in message:
        return "把参数改成条件对象，例如 {\"flag\": \"ready\"}。"
    if "起始场景不存在" in message:
        return "把 start 改成 scenes 中已存在的场景 id。"
    if "未知条件" in message or "未知效果" in message:
        return "检查拼写；如果它来自插件，请在 mechanics 中启用对应插件。"
    if "物品不存在" in message:
        return "在 items 中声明该物品，或修正引用的 id。"
    if "跳转目标不存在" in message:
        return "把 goto 改成已存在的场景 id。"
    if "选项 id 重复" in message:
        return "同一场景内给每个选项不同的 id。"
    if "没有任何结局" in message:
        return "至少给一个场景添加 ending。"
    if "从起始场景无法到达" in message:
        return "添加通往该场景的选项或全局跳转，或删除该场景。"
    if "插件" in message:
        return "检查该插件数据段的字段类型与引用。"
    return "按提示修正该字段后重新运行 validate。"
