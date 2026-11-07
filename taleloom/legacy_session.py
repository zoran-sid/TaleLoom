"""v0 引擎的 GameSession 兼容适配，桌面与网页共用。负责人：ZC（临时）。

ZQO 的正式会话（taleloom/session.py）完成后在 session_factory.py 中替换本类。

本模块不修改 Engine 的公开接口，不承担随机、变体或新插件展示实现。
存档保持 LQ 已有的 v1 文件格式；LQ 提供纯数据编码器后替换这里的兼容代码。
"""

from __future__ import annotations

import copy
import json

from .engine import Engine
from .model import Command, Story
from .rules import Context
from .save import SAVE_VERSION, fingerprint
from .state import GameState
from .ui_contract import (
    ActionParameter, ActionRequest, ActionSpec, DisplayItem, ResourceView,
    SessionResult, ViewSnapshot,
)

# v0 唯一明确公开的资源；其他内部变量不会自动进入展示层。
PUBLIC_RESOURCES = {'deep_space': {'oxygen': '氧气'}}
TEXT_HINTS = {
    '（输入“看”可重读当前场景，“背包”查看物品，“帮助”查看命令。）': '',
    '（试试“使用 物品”。）': '你可以在下方尝试使用背包里的道具。',
    '输入“线索”回顾笔记，输入“指认 名字”说出你的结论（可选：顾先生、周文、阿芸）。':
        '回顾已找到的线索，再在下方选择你要指认的人。',
}


class LegacySession:
    """把现有引擎包装为 GameSession v1，所有返回数据均为独立副本。"""

    def __init__(self, story: Story):
        self.story = story
        self.engine = Engine(story)
        self._view = None
        self._revision = 0

    def start(self) -> SessionResult:
        """首次进入起点，后续调用保持状态。"""
        if self._view is None:
            self.engine.start()
            self._publish()
        return SessionResult(self.snapshot())

    def snapshot(self) -> ViewSnapshot:
        """读取已生成的快照，不查询规则、不触发剧情。"""
        if self._view is None:
            raise RuntimeError('请先调用 start()')
        return copy.deepcopy(self._view)

    def dispatch(self, request: ActionRequest) -> SessionResult:
        """按当前动作候选验证输入，并事务式执行引擎操作。"""
        self.start()
        if type(request.expected_revision) is not int or request.expected_revision != self._revision:
            return self._error('stale_revision', '画面已更新，请根据当前选项重新操作。')
        action = next((a for a in self._view.choices + self._view.actions
                       if a.id == request.action_id and a.enabled), None)
        if action is None:
            return self._error('invalid_action', '当前无法执行这个操作。')
        values = request.values
        if not isinstance(values, dict) or set(values) != {p.key for p in action.parameters}:
            return self._error('invalid_parameters', '请完整选择操作所需的参数。')
        for parameter in action.parameters:
            if not isinstance(values[parameter.key], str) or values[parameter.key] not in {
                x.id for x in parameter.options
            }:
                return self._error('invalid_parameters', '请从当前可用项目中选择。')
        if action.id == 'puzzle:combine' and values['first'] == values['second']:
            return self._error('invalid_parameters', '请选择两件不同的物品。')
        if action.id.startswith('choice:'):
            command = Command('choose', [action.id.removeprefix('choice:')])
        else:
            command = Command(action.id.split(':', 1)[1], [values[p.key] for p in action.parameters])
        command.raw = ' '.join([command.verb] + command.args)
        previous = copy.deepcopy(self.engine.state)
        try:
            output = self.engine.handle(command)
            self._revision += 1
            self._publish()
        except Exception:
            self.engine = Engine(self.story, previous)
            self._revision = self._view.revision
            raise
        # 场景正文由快照显示，反馈只保留收获、警告和动作结果。
        duplicate = {self.engine.scene.text, f'== {self.engine.scene.title} =='}
        messages = [line for line in output.lines if line not in duplicate and not line.startswith('【结局】')]
        return SessionResult(self.snapshot(), messages)

    def export_save(self) -> dict:
        """导出与现有 CLI 相同的 v1 JSON 信封。"""
        self.start()
        return {'save_version': SAVE_VERSION, 'story_id': self.story.id,
                'fingerprint': fingerprint(self.story), 'state': self.engine.state.to_dict()}

    def restore(self, payload: dict) -> SessionResult:
        """验证存档并原子恢复；任何失败均保留当前进度。"""
        self.start()
        old_engine, old_revision = self.engine, self._revision
        try:
            state = self._decode(payload)
            self.engine = Engine(self.story, state)
            self.engine.start()  # resumed 只描述，不再次执行 on_enter
            self._revision += 1
            self._publish()
        except (KeyError, TypeError, ValueError, AttributeError):
            self.engine, self._revision = old_engine, old_revision
            return self._error('invalid_save', '存档内容无效或与当前剧本不兼容，原进度已保留。')
        notes = []
        if payload.get('fingerprint') != fingerprint(self.story):
            notes.append('剧本结构已更新，部分进度可能与当前版本不同。')
        return SessionResult(self.snapshot(), notes)

    def _error(self, code, message):
        return SessionResult(self.snapshot(), [message], code)

    def _decode(self, payload):
        if not isinstance(payload, dict) or type(payload.get('save_version')) is not int:
            raise ValueError('存档信封无效')
        if payload['save_version'] != SAVE_VERSION or payload.get('story_id') != self.story.id:
            raise ValueError('版本或剧本不匹配')
        # 复制也验证 JSON 边界，拒绝 NaN、Python 对象与共享引用。
        data = json.loads(json.dumps(payload['state'], allow_nan=False))
        if not isinstance(data, dict):
            raise ValueError('状态应为对象')
        state = GameState.from_dict(data)
        if state.story_id != self.story.id or state.scene not in self.story.scenes:
            raise ValueError('未知剧本或场景')
        for field in ('flags', 'inventory', 'visited', 'used_choices', 'fired_triggers', 'history'):
            value = getattr(state, field)
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise ValueError(field)
        if not isinstance(state.vars, dict) or not all(
            isinstance(k, str) and type(v) is int for k, v in state.vars.items()
        ):
            raise ValueError('vars')
        if type(state.turn) is not int or state.turn < 0:
            raise ValueError('turn')
        if not isinstance(state.ext, dict) or not all(isinstance(v, dict) for v in state.ext.values()):
            raise ValueError('ext')
        clues = state.ext.get('mystery', {}).get('clues', [])
        if not isinstance(clues, list) or not all(isinstance(c, str) for c in clues):
            raise ValueError('clues')
        ending = self.story.scenes[state.scene].ending
        expected = ending.get('id', state.scene) if ending else None
        if state.ending != expected:
            raise ValueError('ending')
        if any(i not in self.story.items for i in state.inventory):
            raise ValueError('inventory')
        return state

    def _publish(self):
        state, scene = self.engine.state, self.engine.scene
        inventory = [DisplayItem(i, self.story.items[i].name, self.story.items[i].description)
                     for i in state.inventory]
        clues = self.story.data.get('clues', {})
        found = state.ext.get('mystery', {}).get('clues', [])
        actions = []
        if not state.ending:
            if 'puzzle' in self.story.mechanics and inventory:
                actions.append(ActionSpec('puzzle:use', '使用道具', [ActionParameter('item', '物品', options=inventory)]))
                if len(inventory) >= 2:
                    actions.append(ActionSpec('puzzle:combine', '组合道具', [
                        ActionParameter('first', '第一件物品', options=inventory),
                        ActionParameter('second', '第二件物品', options=inventory),
                    ]))
            acc = self.story.data.get('accusation')
            if 'mystery' in self.story.mechanics and acc and self.engine.registry.check(
                Context(self.story, state), acc.get('when')
            ):
                suspects = [DisplayItem(k, v.get('name', k)) for k, v in acc.get('suspects', {}).items()]
                actions.append(ActionSpec('mystery:accuse', '作出指认', [ActionParameter('suspect', '指认对象', options=suspects)]))
        text = scene.text
        for old, new in TEXT_HINTS.items():
            text = text.replace(old, new)
        self._view = ViewSnapshot(
            story_id=self.story.id, story_title=self.story.title, scene_id=scene.id,
            scene_title=scene.title, text=text, revision=self._revision, turn=state.turn,
            choices=[ActionSpec(f'choice:{c.id}', c.text) for c in self.engine.available_choices()],
            actions=actions, inventory=inventory,
            clues=[DisplayItem(c, clues.get(c, {}).get('name', c), clues.get(c, {}).get('text', '')) for c in found],
            resources=[ResourceView(k, label, state.vars[k]) for k, label in PUBLIC_RESOURCES.get(self.story.id, {}).items() if k in state.vars],
            ended=state.ending is not None, ending_id=state.ending,
            ending_title=(scene.ending or {}).get('title'),
        )
