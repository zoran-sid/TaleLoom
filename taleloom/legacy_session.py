"""v0 引擎的 GameSession 兼容适配，桌面与网页共用。负责人：ZC（临时）。

ZQO 的正式会话（taleloom/session.py）完成后在 session_factory.py 中替换本类。

本模块不修改 Engine 的公开接口，不承担随机、变体或新插件展示实现。
存档保持 LQ 已有的 v1 文件格式；LQ 提供纯数据编码器后替换这里的兼容代码。
"""

from __future__ import annotations

import copy
import re

from .engine import Engine
from .mechanics.mystery import build_actions as mystery_actions
from .mechanics.puzzle import build_actions as puzzle_actions
from .model import Command, Story
from .save import encode_save, decode_save
from .ui_contract import (
    ActionParameter, ActionRequest, ActionSpec, DisplayItem, ResourceView,
    SessionResult, ViewSnapshot,
)

TEXT_HINTS = {
    '（输入“看”可重读当前场景，“背包”查看物品，“帮助”查看命令。）': '',
    '（试试“使用 物品”。）': '你可以在下方尝试使用背包里的道具。',
}
# 只给命令行玩家看的提示写成“（输入……）”，图形界面用按钮代替，不显示。
CLI_HINT = re.compile(r'（输入[^（）]*）')


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
        return encode_save(self.engine.state, self.story)

    def restore(self, payload: dict) -> SessionResult:
        """验证存档并原子恢复；任何失败均保留当前进度。"""
        self.start()
        old_engine, old_revision = self.engine, self._revision
        try:
            state, notes = decode_save(payload, self.story)
            self.engine = Engine(self.story, state)
            self.engine.start()  # resumed 只描述，不再次执行 on_enter
            self._revision += 1
            self._publish()
        except (KeyError, TypeError, ValueError, AttributeError):
            self.engine, self._revision = old_engine, old_revision
            return self._error('invalid_save', '存档内容无效或与当前剧本不兼容，原进度已保留。')
        return SessionResult(self.snapshot(), notes)

    def _error(self, code, message):
        return SessionResult(self.snapshot(), [message], code)

    def _decode(self, payload):
        return decode_save(payload, self.story)[0]

    def _publish(self):
        state, scene = self.engine.state, self.engine.scene
        inventory = [DisplayItem(i, self.story.items[i].name, self.story.items[i].description)
                     for i in state.inventory]
        clues = self.story.data.get('clues', {})
        found = state.ext.get('mystery', {}).get('clues', [])
        actions = []
        if 'puzzle' in self.story.mechanics:
            actions.extend(puzzle_actions(self.story, state, inventory))
        if 'mystery' in self.story.mechanics:
            actions.extend(mystery_actions(self.story, state, self.engine.registry))
        text = scene.text
        for old, new in TEXT_HINTS.items():
            text = text.replace(old, new)
        text = _strip_cli_hints(text)
        self._view = ViewSnapshot(
            story_id=self.story.id, story_title=self.story.title, scene_id=scene.id,
            scene_title=scene.title, text=text, revision=self._revision, turn=state.turn,
            choices=[ActionSpec(f'choice:{c.id}', c.text) for c in self.engine.available_choices()],
            actions=actions, inventory=inventory,
            clues=[DisplayItem(c, clues.get(c, {}).get('name', c), clues.get(c, {}).get('text', '')) for c in found],
            resources=[ResourceView(r.var, r.name, state.vars.get(r.var, 0), r.maximum)
                       for r in self.story.resources],
            assets=dict(self.story.assets),
            ended=state.ending is not None, ending_id=state.ending,
            ending_title=(scene.ending or {}).get('title'),
        )


def _strip_cli_hints(text: str) -> str:
    """去掉“（输入……）”形式的命令行提示；只含提示的行整行删除，其余换行保留。

    >>> _strip_cli_hints('书房。\\n（输入“问 管家”审问。）')
    '书房。'
    >>> _strip_cli_hints('门开了。（输入“看”重读。）\\n\\n下一段')
    '门开了。\\n\\n下一段'
    """
    kept = []
    for line in text.split('\n'):
        cleaned = CLI_HINT.sub('', line).rstrip()
        if cleaned or not line.strip():
            kept.append(cleaned)
    return '\n'.join(kept)
