"""正式游戏会话。负责人：ZQO。纯数据交互、失败回滚、版本检查。"""

from __future__ import annotations

import copy

from .engine import Engine
from .model import Command, Story
from .session_history import SessionHistory
from .presentation import checkpoint_label
from .state import GameState
from .save import encode_save, decode_save
import secrets
from .ui_contract import (
    ActionRequest,
    SessionResult, ViewSnapshot,
)


class GameSession:
    """正式 GameSession v1 会话，所有返回数据均为独立副本。"""

    def __init__(self, story: Story, *, seed: int | None = None, rewind_limit: int = 3):
        self._history = SessionHistory(rewind_limit)
        self._default_limit = rewind_limit
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
            self._history.capture(self.engine.state, checkpoint_label(self.engine.scene) or '开场')
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
        old_history = copy.deepcopy(self._history)
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
                if command.verb == 'choose':
                    self._history.previous = {'state': previous.to_dict(),
                                              'checkpoints': copy.deepcopy(self._history.points)}
                if previous.scene != self.engine.state.scene:
                    self._history.capture(self.engine.state, checkpoint_label(self.engine.scene))
            self._publish()
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            self.engine = previous_engine
            self._history = old_history
            self._revision = self._view.revision
            return self._error('invalid_action', '操作未完成：剧本规则或参数无效，原进度已保留。')
        # 场景正文由快照显示，反馈只保留收获、警告和动作结果。
        duplicate = {self.engine.scene.text, self._view.text, f'== {self.engine.scene.title} =='}
        messages = [line for line in output.lines if line not in duplicate and not line.startswith('【结局】')]
        return SessionResult(self.snapshot(), messages)

    def export_save(self) -> dict:
        """导出与现有 CLI 相同的 v1 JSON 信封。"""
        self.snapshot()
        state = copy.deepcopy(self.engine.state)
        state.ext['session'] = self._history.to_dict()
        return encode_save(state, self.story)

    def restore(self, payload: dict) -> SessionResult:
        """验证存档并原子恢复；任何失败均保留当前进度。"""
        self.snapshot()
        try:
            state, notes = decode_save(payload, self.story)
            data = state.ext.pop('session', None)
            if data is None:
                history = SessionHistory(self._default_limit)
                history.capture(state, checkpoint_label(self.story.scenes[state.scene]) or '读档位置')
            else:
                history = SessionHistory.decode(data, payload, self.story)
            self._replace(state, history)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            return self._error('invalid_save', '存档内容无效或与当前剧本不兼容，原进度已保留。')
        return SessionResult(self.snapshot(), notes)

    def list_checkpoints(self):
        """按到达顺序返回已记录节点的独立摘要；纯读取。"""
        self.snapshot()
        return self._history.summaries()

    def restore_checkpoint(self, checkpoint_id: str, expected_revision: int) -> SessionResult:
        """免费回到已到达节点；累计回退次数，保留失误并丢弃后续节点。"""
        self.snapshot()
        if not self._matches_revision(expected_revision):
            return self._error('stale_revision', '画面已更新，请重新选择存档点。')
        index = next((i for i, p in enumerate(self._history.points) if p['id'] == checkpoint_id), None)
        if index is None:
            return self._error('invalid_checkpoint', '这个存档点不存在或已经作废。')
        history = copy.deepcopy(self._history)
        history.points = history.points[:index + 1]
        history.previous = None
        history.rewinds += 1
        try:
            self._replace(GameState.from_dict(history.points[-1]['state']), history)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            return self._error('invalid_checkpoint', '无法恢复该节点，原进度已保留。')
        return SessionResult(self.snapshot(), ['已回到存档点。'])

    def rewind(self, expected_revision: int) -> SessionResult:
        """失败后回到最近一次选择之前；成功时扣一次机会并记一次失误。"""
        view = self.snapshot()
        if not self._matches_revision(expected_revision):
            return self._error('stale_revision', '画面已更新，请重新操作。')
        if view.ending_kind != 'failure' or self._history.previous is None:
            return self._error('rewind_unavailable', '当前没有可回退的失败选择。')
        if self._history.mistakes >= self._history.limit:
            return self._error('rewind_exhausted', '回到上一个选择的机会已经用完。')
        history = copy.deepcopy(self._history)
        previous = history.previous
        history.points = previous['checkpoints']
        history.previous = None
        history.mistakes += 1
        try:
            self._replace(GameState.from_dict(previous['state']), history)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            return self._error('rewind_unavailable', '无法恢复上一个选择，原进度已保留。')
        return SessionResult(self.snapshot(), ['已回到上一个选择。'])

    def _matches_revision(self, revision):
        return type(revision) is int and revision == self._revision

    def _replace(self, state, history):
        # 只在新快照完整生成后提交，恢复不重新执行 on_enter 或任何剧情命令。
        from .presentation import build_snapshot
        engine = Engine(self.story, state)
        view = build_snapshot(engine, self._revision + 1)
        self._decorate(view, history)
        self.engine, self._history = engine, history
        self._revision += 1
        self._view = view

    @staticmethod
    def _decorate(view, history):
        points = history.summaries()
        view.checkpoint = points[-1] if points else None
        view.mistakes = history.mistakes
        view.rewinds = history.rewinds
        view.rewind_limit = history.limit
        view.rewinds_remaining = history.limit - history.mistakes

    def _error(self, code, message):
        return SessionResult(self.snapshot(), [message], code)

    def _publish(self):
        from .presentation import build_snapshot
        view = build_snapshot(self.engine, self._revision)
        self._decorate(view, self._history)
        self._view = view
