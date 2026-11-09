"""剧本加载：JSON 文件 → model.Story。

负责人：YHT。这里只做格式解析与字段类型检查；剧情逻辑上的问题
（跳转目标不存在、场景不可达等）由 validator 负责。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .model import FORMAT_VERSION, Choice, Item, Resource, Scene, Story, Trigger

CORE_KEYS = {
    "format_version", "id", "title", "start", "scenes", "items", "mechanics",
    "vars", "every_turn", "triggers", "resources", "assets", "meta",
}

# 公开资源同时接受展示层的命名（id/label/maximum），方便与 ViewSnapshot 对照。
_RESOURCE_FIELDS = {
    "var": "var", "id": "var",
    "name": "name", "label": "name",
    "max": "max", "maximum": "max",
}

_MISSING = object()
_TYPE_NAMES = {dict: "对象", list: "数组", str: "字符串", bool: "布尔值", int: "整数", float: "数值"}
ENDING_KINDS = ("normal", "failure")


class StoryFormatError(ValueError):
    """剧本文件无法解析。message 带有出错位置，例如 $.scenes[2].choices[0]。"""


def find_story_file(path: str | Path) -> Path:
    """把剧本目录（或 story.json 路径）解析成实际文件路径。

    找不到文件时抛 StoryFormatError，而不是让调用方看到 FileNotFoundError。
    """
    p = Path(path)
    if p.is_dir():
        p = p / "story.json"
    if not p.is_file():
        raise StoryFormatError(f"找不到剧本文件：{p}")
    return p


def load_story(path: str | Path) -> Story:
    """读取 UTF-8 的 story.json 并解析成 Story。

    JSON 语法错误会报告行列号，并附上出错行的原文，方便剧本作者定位。
    解析成功后会记录剧本目录，供 validator 检查可选素材是否存在。
    """
    file = find_story_file(path)
    try:
        text = file.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise StoryFormatError(
            f"{file}: 不是有效的 UTF-8 文件（第 {exc.start} 字节）\n"
            "建议：用 UTF-8 编码重新保存剧本文件。"
        ) from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        lines = text.splitlines()
        line = lines[exc.lineno - 1].strip() if 0 < exc.lineno <= len(lines) else ""
        detail = f"{file}: JSON 语法错误，第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}"
        if line:
            detail += f"\n  第 {exc.lineno} 行：{line}"
        detail += "\n建议：检查该行附近的逗号、引号与括号是否配对。"
        raise StoryFormatError(detail) from exc
    story = parse_story(raw)
    story.source_dir = str(file.parent)
    return story


def parse_story(raw: Any) -> Story:
    """把已经解码的 JSON 对象解析成 Story，所有字段都做类型检查。

    出错时抛 StoryFormatError，位置使用 $.scenes[0].choices[1] 这样的路径。
    """
    _expect(raw, dict, "$")
    version = raw.get("format_version", FORMAT_VERSION)
    _expect(version, int, "$.format_version")
    if version != FORMAT_VERSION:
        raise StoryFormatError(f"$.format_version: 引擎支持 {FORMAT_VERSION}，剧本为 {version}")

    for key in ("id", "title", "start"):
        _str(raw, key, "$", non_empty=key in ("id", "start"))

    scenes: dict[str, Scene] = {}
    scene_items = _list(raw, "scenes", "$")
    if not scene_items:
        raise StoryFormatError("$.scenes: 至少需要一个场景")
    for i, s in enumerate(scene_items):
        scene = _scene(s, f"$.scenes[{i}]")
        if scene.id in scenes:
            raise StoryFormatError(f"$.scenes[{i}].id: 场景 id 重复：{scene.id}")
        scenes[scene.id] = scene

    items: dict[str, Item] = {}
    for i, it in enumerate(_list(raw, "items", "$", required=False)):
        item = _item(it, f"$.items[{i}]")
        if item.id in items:
            raise StoryFormatError(f"$.items[{i}].id: 物品 id 重复：{item.id}")
        items[item.id] = item

    triggers = []
    trigger_ids: set[str] = set()
    for i, t in enumerate(_list(raw, "triggers", "$", required=False)):
        trigger = _trigger(t, f"$.triggers[{i}]", i)
        if trigger.id in trigger_ids:
            raise StoryFormatError(f"$.triggers[{i}].id: 触发器 id 重复：{trigger.id}")
        trigger_ids.add(trigger.id)
        triggers.append(trigger)

    mechanics = _list(raw, "mechanics", "$", required=False)
    seen_mechanics: set[str] = set()
    for i, name in enumerate(mechanics):
        _expect(name, str, f"$.mechanics[{i}]")
        if name in seen_mechanics:
            raise StoryFormatError(f"$.mechanics[{i}]: 机制插件重复：{name}")
        seen_mechanics.add(name)
    vars_ = _vars(raw.get("vars", {}))
    resources = []
    resource_vars: set[str] = set()
    for i, value in enumerate(_list(raw, "resources", "$", required=False)):
        resource = _resource(value, f"$.resources[{i}]")
        if resource.var in resource_vars:
            raise StoryFormatError(
                f"$.resources[{i}].var: 公开资源变量重复：{resource.var}"
            )
        resource_vars.add(resource.var)
        resources.append(resource)
    assets = _assets(raw.get("assets", {}), "$.assets")
    meta = raw.get("meta", {})
    _expect(meta, dict, "$.meta")
    if "linear" in meta:
        _expect(meta["linear"], bool, "$.meta.linear")

    return Story(
        id=raw["id"],
        title=raw["title"],
        start=raw["start"],
        scenes=scenes,
        items=items,
        mechanics=list(mechanics),
        initial_vars=vars_,
        every_turn=_effects(raw.get("every_turn", []), "$.every_turn"),
        triggers=triggers,
        resources=resources,
        assets=assets,
        data={k: v for k, v in raw.items() if k not in CORE_KEYS},
        meta=dict(meta),
        format_version=version,
    )


def _resource(value: Any, path: str) -> Resource:
    """解析一项公开资源。

    规范写法为 ``{"var": "oxygen", "name": "氧气", "max": 8}``；为方便
    展示层复用 ``ResourceView`` 的命名，也接受 ``id``／``label``／``maximum``。
    """
    _expect(value, dict, path)
    fields: dict[str, Any] = {}
    for key, item in value.items():
        canonical = _RESOURCE_FIELDS.get(key)
        if canonical is None:
            raise StoryFormatError(
                f"{path}.{key}: 未知的公开资源字段；可用 var/name/max"
                "（也接受 id/label/maximum）"
            )
        if canonical in fields:
            raise StoryFormatError(f"{path}.{canonical}: 同一字段重复指定")
        fields[canonical] = item

    if "var" not in fields:
        raise StoryFormatError(f"{path}.var: 缺少变量名")
    if "name" not in fields:
        raise StoryFormatError(f"{path}.name: 缺少显示名称")
    var = _str(fields, "var", path, non_empty=True)
    name = _str(fields, "name", path, non_empty=True)
    maximum = None
    if "max" in fields:
        _expect(fields["max"], int, f"{path}.max")
        maximum = fields["max"]
        if maximum <= 0:
            raise StoryFormatError(f"{path}.max: 上限必须大于 0")
    return Resource(var=var, name=name, maximum=maximum)


def _assets(value: Any, path: str) -> dict[str, str]:
    """解析素材角色到剧本相对路径的映射，并拒绝越出剧本目录的路径。"""
    _expect(value, dict, path)
    result: dict[str, str] = {}
    for key, asset in value.items():
        if not isinstance(key, str) or not key.strip():
            raise StoryFormatError(f"{path}: 素材角色必须是非空字符串")
        _expect(asset, str, f"{path}.{key}")
        if not asset.strip():
            raise StoryFormatError(f"{path}.{key}: 素材路径不能为空")
        problem = _asset_path_problem(asset)
        if problem:
            raise StoryFormatError(f"{path}.{key}: {problem}")
        result[key] = asset
    return result


def _asset_path_problem(value: str) -> str:
    """返回素材路径的问题说明；合法时返回空字符串。"""
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        return "素材路径必须是剧本目录内的相对路径，不能是绝对路径"
    if "\\" in value:
        return "素材路径请使用 / 分隔，不要使用反斜杠"
    if "://" in value:
        return "素材路径不能是网址"
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "素材路径不能包含空段、. 或 .."
    if "\x00" in value:
        return "素材路径不能包含空字符"
    return ""


def _scene(s: Any, path: str) -> Scene:
    _expect(s, dict, path)
    choices = []
    raw_choices = s.get("choices", [])
    _expect(raw_choices, list, f"{path}.choices")
    for j, c in enumerate(raw_choices):
        choices.append(_choice(c, f"{path}.choices[{j}]", j))

    raw_ending = s.get("ending")
    ending = None
    if raw_ending is not None:
        _expect(raw_ending, dict, f"{path}.ending")
        ending = {"id": _str(raw_ending, "id", f"{path}.ending", non_empty=True)}
        if "title" in raw_ending:
            ending["title"] = _str(raw_ending, "title", f"{path}.ending")
        if "kind" in raw_ending:
            kind = _str(raw_ending, "kind", f"{path}.ending", non_empty=True)
            if kind not in ENDING_KINDS:
                raise StoryFormatError(
                    f"{path}.ending.kind: 结局类型应为 normal 或 failure，实际为 {kind!r}"
                )
            ending["kind"] = kind

    checkpoint = None
    if s.get("checkpoint") is not None:
        _expect(s["checkpoint"], str, f"{path}.checkpoint")
        if not s["checkpoint"].strip():
            raise StoryFormatError(f"{path}.checkpoint: 存档点名称不能为空")
        checkpoint = s["checkpoint"]

    art = None
    if s.get("art") is not None:
        _expect(s["art"], str, f"{path}.art")
        if not s["art"].strip():
            raise StoryFormatError(f"{path}.art: 画面键不能为空")
        art = s["art"]

    variants = s.get('variants', [])
    _expect(variants, list, f'{path}.variants')
    for i, variant in enumerate(variants):
        vp = f'{path}.variants[{i}]'
        _expect(variant, dict, vp)
        _str(variant, 'text', vp)
        if variant.get('mode', 'append') not in ('append', 'replace'):
            raise StoryFormatError(f'{vp}.mode: 应为 append 或 replace')
        if variant.get('when') is not None:
            _expect(variant['when'], dict, f'{vp}.when')
    return Scene(
        variants=variants,
        id=_str(s, "id", path, non_empty=True),
        title=_str(s, "title", path, default=""),
        text=_str(s, "text", path),
        choices=choices,
        on_enter=_effects(s.get("on_enter", []), f"{path}.on_enter"),
        ending=ending,
        checkpoint=checkpoint,
        art=art,
    )


def _choice(c: Any, path: str, index: int) -> Choice:
    _expect(c, dict, path)
    goto = c.get("goto")
    if goto is not None:
        _expect(goto, str, f"{path}.goto")
        if not goto.strip():
            raise StoryFormatError(f"{path}.goto: 跳转目标不能为空")
    when = c.get("when")
    if when is not None:
        _expect(when, dict, f"{path}.when")
    return Choice(
        id=_str(c, "id", path, default=f"c{index + 1}", non_empty=True),
        text=_str(c, "text", path),
        goto=goto,
        when=when,
        effects=_effects(c.get("effects", []), f"{path}.effects"),
        aliases=_aliases(c, path),
        once=_bool(c, "once", path, default=False),
        message=_str(c, "message", path, default=""),
    )


def _item(it: Any, path: str) -> Item:
    _expect(it, dict, path)
    return Item(
        id=_str(it, "id", path, non_empty=True),
        name=_str(it, "name", path),
        description=_str(it, "description", path, default=""),
        aliases=_aliases(it, path),
    )


def _trigger(t: Any, path: str, index: int) -> Trigger:
    _expect(t, dict, path)
    _expect(t.get("when"), dict, f"{path}.when")
    return Trigger(
        when=t["when"],
        effects=_effects(t.get("effects", []), f"{path}.effects"),
        once=_bool(t, "once", path, default=True),
        id=_str(t, "id", path, default=f"trigger{index}", non_empty=True),
    )


def _effects(value: Any, path: str) -> list[dict]:
    _expect(value, list, path)
    for i, e in enumerate(value):
        _expect(e, dict, f"{path}[{i}]")
        if len(e) != 1:
            raise StoryFormatError(f"{path}[{i}]: 每个效果只能有一个键，实际为 {sorted(e)}")
        key = next(iter(e))
        if not isinstance(key, str) or not key.strip():
            raise StoryFormatError(f"{path}[{i}]: 效果名必须是非空字符串")
    return value


def _aliases(obj: dict, path: str) -> list[str]:
    value = obj.get("aliases", [])
    _expect(value, list, f"{path}.aliases")
    for i, alias in enumerate(value):
        _expect(alias, str, f"{path}.aliases[{i}]")
    return list(value)


def _vars(value: Any) -> dict[str, int]:
    _expect(value, dict, "$.vars")
    result = {}
    for key, number in value.items():
        if not isinstance(key, str) or not key.strip():
            raise StoryFormatError("$.vars: 变量名必须是非空字符串")
        _expect(number, int, f"$.vars.{key}")
        result[key] = number
    return result


def _list(obj: dict, key: str, path: str, required: bool = True) -> list:
    if key not in obj:
        if required:
            raise StoryFormatError(f"{path}.{key}: 缺少必填字段")
        return []
    _expect(obj[key], list, f"{path}.{key}")
    return obj[key]


def _str(
    obj: dict,
    key: str,
    path: str,
    default: Any = _MISSING,
    non_empty: bool = False,
) -> str:
    if key in obj:
        value = obj[key]
    elif default is not _MISSING:
        value = default
    else:
        _expect(None, str, f"{path}.{key}")
        raise AssertionError("unreachable")
    _expect(value, str, f"{path}.{key}")
    if non_empty and not value.strip():
        raise StoryFormatError(f"{path}.{key}: 不能为空")
    return value


def _bool(obj: dict, key: str, path: str, default: bool) -> bool:
    value = obj.get(key, default)
    _expect(value, bool, f"{path}.{key}")
    return value


def _expect(value: Any, typ: type, path: str) -> None:
    if typ is int and isinstance(value, bool):
        raise StoryFormatError(f"{path}: 应为整数，实际为 布尔值")
    if not isinstance(value, typ):
        got = "缺失" if value is None else _TYPE_NAMES.get(type(value), type(value).__name__)
        raise StoryFormatError(f"{path}: 应为{_TYPE_NAMES.get(typ, typ.__name__)}，实际为 {got}")
