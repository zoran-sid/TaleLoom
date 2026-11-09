"""生成玩家可见数据。负责人：ZQO；所有规则查询使用状态副本。"""
from __future__ import annotations

import copy
import re

from .rules import Context
from .ui_contract import ActionSpec, DisplayItem, ResourceView, ViewSnapshot


def interpolate(text, story, state):
    """替换变量、物品名称；未知或不受支持的表达式显示清楚提示，不执行代码。"""
    def replace(match):
        key = match.group(1)
        if key.startswith('vars.') and key[5:] in state.vars:
            return str(state.vars[key[5:]])
        if key.startswith('item:') and key[5:] in story.items:
            return story.items[key[5:]].name
        return f'【未知占位符：{key}】'
    return re.sub(r'\{([^{}]+)\}', replace, text)


def scene_text(engine, scene):
    """按声明顺序应用追加或替换变体，再展开占位符。"""
    ctx = Context(engine.story, copy.deepcopy(engine.state))
    text = scene.text
    for index, variant in enumerate(scene.variants):
        ctx.condition_path = f"variant:{scene.id}/{index}"
        if engine.registry.check(ctx, variant.get('when')):
            text = variant['text'] if variant.get('mode', 'append') == 'replace' else text + '\n' + variant['text']
    return interpolate(text, engine.story, ctx.state)


def build_snapshot(engine, revision):
    """生成独立快照；插件展示函数在深拷贝上运行，避免修改真实状态或剧本。"""
    view_engine = copy.deepcopy(engine)
    state, story, scene = view_engine.state, view_engine.story, view_engine.scene
    inventory = [DisplayItem(i, story.items[i].name, story.items[i].description) for i in state.inventory]
    actions, clues = [], []
    for mechanic in view_engine.mechanics.values():
        clues.extend(mechanic.clues(view_engine))
        if state.ending is None:
            actions.extend(mechanic.actions(view_engine))
    resources = [ResourceView(r.var, r.name, state.vars.get(r.var, 0), r.maximum)
                 for r in story.resources]
    from .legacy_session import TEXT_HINTS, _strip_cli_hints
    text = scene_text(view_engine, scene)
    for old, new in TEXT_HINTS.items():
        text = text.replace(old, new)
    text = _strip_cli_hints(text)
    return ViewSnapshot(
        story_id=story.id, story_title=story.title, scene_id=scene.id, scene_title=scene.title,
        text=text, revision=revision, turn=state.turn,
        choices=[ActionSpec('choice:' + c.id, interpolate(c.text, story, state)) for c in view_engine.available_choices()],
        actions=actions, inventory=inventory, clues=clues, resources=resources, assets=dict(story.assets),
        art=getattr(scene, "art", None), ending_kind=ending_kind(scene) if state.ending else None,
        ended=state.ending is not None, ending_id=state.ending, ending_title=(scene.ending or {}).get('title'),
    )


def ending_kind(scene):
    """优先读取正式 kind；迁移期间兼容旧影像版 fail_ 前缀。"""
    if not scene.ending:
        return None
    return scene.ending.get('kind', 'failure' if scene.ending.get('id', scene.id).startswith('fail_') else 'normal')


def checkpoint_label(scene):
    """读取正式存档点名称；旧剧本暂兼容进入提示标记。"""
    label = getattr(scene, 'checkpoint', None)
    if label is not None:
        return label
    for effect in scene.on_enter:
        text = effect.get('say')
        if isinstance(text, str) and text.startswith('【存档点】'):
            return text[len('【存档点】'):].strip() or None
    return None
