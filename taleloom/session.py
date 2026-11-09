"""正式游戏会话。负责人：ZQO。纯数据交互、失败回滚、版本检查。"""

from __future__ import annotations

import copy

from .engine import Engine
from .model import Command, Story
from .save import encode_save, decode_save
import secrets
from .ui_contract import (
    ActionRequest,
    SessionResult, ViewSnapshot,
)


class GameSession:
    """正式 GameSession v1 会话，所有返回数据均为独立副本。"""

    def __init__(self, story: Story, *, seed: int | None = None):
        self.story = story
        if seed is not None and type(seed) is not int:
            raise ValueError("seed 必须是整数")
        self.engine = Engine(story)
        # JSON 经 JavaScript 传递时整数须精确；新游戏种子限制在 Number 安全范围。
        self.engine.state.random_seed = secrets.randbits(53) if seed is None else seed
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
        self.snapshot()
        if type(request.expected_revision) is not int or request.expected_revision != self._revision:
            return self._error('stale_revision', '画面已更新，请根据当前选项重新操作。')
        action = next((a for a in self._view.choices + self._view.actions
                       if a.id == request.action_id and a.enabled), None)
        if action is None:
            return self._error('invalid_action', '当前无法执行这个操作。')
        values = request.values
        if (not isinstance(values, dict) or not {p.key for p in action.parameters if p.required} <= set(values)
                or not set(values) <= {p.key for p in action.parameters}):
            return self._error('invalid_parameters', '请完整选择操作所需的参数。')
        for parameter in action.parameters:
            if parameter.key not in values:
                continue
            value = values[parameter.key]
            if (not isinstance(value, str) or (parameter.kind == 'select' and value not in {x.id for x in parameter.options})
                    or (parameter.required and not value.strip())):
                return self._error('invalid_parameters', '请从当前可用项目中选择。')
        if action.id == 'puzzle:combine' and values['first'] == values['second']:
            return self._error('invalid_parameters', '请选择两件不同的物品。')
        if action.id.startswith('choice:'):
            command = Command('choose', [action.id.removeprefix('choice:')])
        else:
            command = Command(action.id.split(':', 1)[1], [values.get(p.key, '') for p in action.parameters])
        command.raw = ' '.join([command.verb] + command.args)
        previous_engine = copy.deepcopy(self.engine)
        previous = previous_engine.state
        try:
            output = self.engine.handle(command)
            # 失败尝试不应只因追加 history 而成为一次状态变化。
            before, after = previous.to_dict(), self.engine.state.to_dict()
            before.pop('history')
            after.pop('history')
            if before == after:
                self.engine.state = previous
            else:
                self._revision += 1
            self._publish()
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            self.engine = previous_engine
            self._revision = self._view.revision
            return self._error('invalid_action', '操作未完成：剧本规则或参数无效，原进度已保留。')
        # 场景正文由快照显示，反馈只保留收获、警告和动作结果。
        duplicate = {self.engine.scene.text, self._view.text, f'== {self.engine.scene.title} =='}
        messages = [line for line in output.lines if line not in duplicate and not line.startswith('【结局】')]
        return SessionResult(self.snapshot(), messages)

    def export_save(self) -> dict:
        """导出与现有 CLI 相同的 v1 JSON 信封。"""
        self.snapshot()
        return encode_save(self.engine.state, self.story)

    def restore(self, payload: dict) -> SessionResult:
        """验证存档并原子恢复；任何失败均保留当前进度。"""
        self.snapshot()
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

    def _publish(self):
        from .presentation import build_snapshot
        self._view = build_snapshot(self.engine, self._revision)
