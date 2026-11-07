"""剧本加载：JSON 文件 → model.Story。

负责人：YHT。只做格式解析与类型检查；剧情逻辑上的问题（跳转目标不存在、
场景不可达等）由 validator 负责。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import FORMAT_VERSION, Choice, Item, Scene, Story, Trigger

CORE_KEYS = {
    "format_version", "id", "title", "start", "scenes", "items", "mechanics",
    "vars", "every_turn", "triggers", "meta",
}


class StoryFormatError(ValueError):
    """剧本文件无法解析。message 带有出错位置，例如 scenes[2].choices[0]。"""


def find_story_file(path: str | Path) -> Path:
    p = Path(path)
    if p.is_dir():
        p = p / "story.json"
    if not p.is_file():
        raise StoryFormatError(f"找不到剧本文件：{p}")
    return p


def load_story(path: str | Path) -> Story:
    file = find_story_file(path)
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryFormatError(f"{file}: JSON 语法错误，第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}") from exc
    return parse_story(raw)


def parse_story(raw: Any) -> Story:
    _expect(raw, dict, "$")
    version = raw.get("format_version", FORMAT_VERSION)
    if version != FORMAT_VERSION:
        raise StoryFormatError(f"$.format_version: 引擎支持 {FORMAT_VERSION}，剧本为 {version}")
    for key in ("id", "title", "start"):
        _expect(raw.get(key), str, f"$.{key}")

    scenes: dict[str, Scene] = {}
    for i, s in enumerate(_list(raw, "scenes", "$")):
        scene = _scene(s, f"$.scenes[{i}]")
        if scene.id in scenes:
            raise StoryFormatError(f"$.scenes[{i}].id: 场景 id 重复：{scene.id}")
        scenes[scene.id] = scene

    items: dict[str, Item] = {}
    for i, it in enumerate(_list(raw, "items", "$", required=False)):
        path = f"$.items[{i}]"
        _expect(it, dict, path)
        item = Item(
            id=_str(it, "id", path),
            name=_str(it, "name", path),
            description=it.get("description", ""),
            aliases=list(it.get("aliases", [])),
        )
        items[item.id] = item

    triggers = []
    for i, t in enumerate(_list(raw, "triggers", "$", required=False)):
        path = f"$.triggers[{i}]"
        _expect(t, dict, path)
        _expect(t.get("when"), dict, f"{path}.when")
        triggers.append(Trigger(
            when=t["when"],
            effects=_effects(t.get("effects", []), f"{path}.effects"),
            once=bool(t.get("once", True)),
            id=t.get("id", f"trigger{i}"),
        ))

    mechanics = raw.get("mechanics", [])
    _expect(mechanics, list, "$.mechanics")
    vars_ = raw.get("vars", {})
    _expect(vars_, dict, "$.vars")

    return Story(
        id=raw["id"],
        title=raw["title"],
        start=raw["start"],
        scenes=scenes,
        items=items,
        mechanics=[str(m) for m in mechanics],
        initial_vars={str(k): v for k, v in vars_.items()},
        every_turn=_effects(raw.get("every_turn", []), "$.every_turn"),
        triggers=triggers,
        data={k: v for k, v in raw.items() if k not in CORE_KEYS},
        meta=dict(raw.get("meta", {})),
        format_version=version,
    )


def _scene(s: Any, path: str) -> Scene:
    _expect(s, dict, path)
    choices = []
    for j, c in enumerate(s.get("choices", [])):
        cpath = f"{path}.choices[{j}]"
        _expect(c, dict, cpath)
        when = c.get("when")
        if when is not None:
            _expect(when, dict, f"{cpath}.when")
        choices.append(Choice(
            id=c.get("id", f"c{j + 1}"),
            text=_str(c, "text", cpath),
            goto=c.get("goto"),
            when=when,
            effects=_effects(c.get("effects", []), f"{cpath}.effects"),
            aliases=list(c.get("aliases", [])),
            once=bool(c.get("once", False)),
            message=c.get("message", ""),
        ))
    ending = s.get("ending")
    if ending is not None:
        _expect(ending, dict, f"{path}.ending")
    return Scene(
        id=_str(s, "id", path),
        title=s.get("title", ""),
        text=_str(s, "text", path),
        choices=choices,
        on_enter=_effects(s.get("on_enter", []), f"{path}.on_enter"),
        ending=ending,
    )


def _effects(value: Any, path: str) -> list[dict]:
    _expect(value, list, path)
    for i, e in enumerate(value):
        _expect(e, dict, f"{path}[{i}]")
        if len(e) != 1:
            raise StoryFormatError(f"{path}[{i}]: 每个效果只能有一个键，实际为 {sorted(e)}")
    return value


def _list(obj: dict, key: str, path: str, required: bool = True) -> list:
    if key not in obj:
        if required:
            raise StoryFormatError(f"{path}.{key}: 缺少必填字段")
        return []
    _expect(obj[key], list, f"{path}.{key}")
    return obj[key]


def _str(obj: dict, key: str, path: str) -> str:
    value = obj.get(key)
    _expect(value, str, f"{path}.{key}")
    return value


def _expect(value: Any, typ: type, path: str) -> None:
    if not isinstance(value, typ):
        names = {dict: "对象", list: "数组", str: "字符串"}
        got = "缺失" if value is None else type(value).__name__
        raise StoryFormatError(f"{path}: 应为{names.get(typ, typ.__name__)}，实际为 {got}")
