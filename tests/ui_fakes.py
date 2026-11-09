"""界面独立开发用的固定测试替身；不用于正式游戏或真实存档。

FakeGameSession 不读取 stories，不调用 Engine，也不启动 GUI。
流程：捡钥匙 → 开门（或选择钥匙并使用）→ 结局。
真实适配器必须另行通过真实剧本和规则测试。
"""

from __future__ import annotations

from copy import deepcopy

from taleloom.ui_contract import (
    CheckpointView, ActionParameter, ActionRequest, ActionSpec, DisplayItem, JsonObject,
    ResourceView, SessionResult, StorageError, ViewSnapshot,
)


class FakeGameSession:
    """三步状态的确定性测试替身，演示快照、参数、错误与恢复约定。"""

    def __init__(self) -> None:
        self._started = False
        self._step = 0
        self._revision = 0
        self._rewinds = 0

    def start(self) -> SessionResult:
        """幂等开始，不重复增加回合。"""
        self._started = True
        return SessionResult(self.snapshot())

    def snapshot(self) -> ViewSnapshot:
        """每次构造独立数据，读取不会改变测试状态。"""
        if not self._started:
            raise RuntimeError("请先调用 start()")
        ended = self._step == 2
        view = ViewSnapshot(
            story_id="ui_demo", story_title="界面测试剧本",
            scene_id="exit" if ended else "hall",
            scene_title="门外" if ended else "门厅",
            text="你走出了房间。" if ended else "门边有一把钥匙。",
            revision=self._revision, turn=self._step,
            resources=[ResourceView("oxygen", "氧气", 8 - self._step, 8)],
            clues=[DisplayItem("note", "门边便条", "钥匙可以开门。")],
            ended=ended, ending_id="out" if ended else None,
            ending_title="出门" if ended else None,
            ending_kind="normal" if ended else None,
            checkpoint=CheckpointView("hall", "开场", "hall", 0), rewinds=self._rewinds,
        )
        if self._step >= 1:
            view.inventory = [DisplayItem("key", "钥匙", "一把铜钥匙。")]
        if self._step == 0:
            view.choices = [ActionSpec("choice:take", "捡起钥匙")]
        elif self._step == 1:
            view.choices = [ActionSpec("choice:open", "打开房门")]
            view.actions = [ActionSpec("puzzle:use", "使用物品", parameters=[
                ActionParameter("item", "物品", options=[DisplayItem("key", "钥匙")])
            ])]
        return view

    def dispatch(self, request: ActionRequest) -> SessionResult:
        """仅接受快照中存在的动作，过期／无效输入保持原状态。"""
        view = self.snapshot()
        if request.expected_revision != self._revision:
            return SessionResult(view, ["画面已更新，请重新选择。"], "stale_revision")
        allowed = {a.id for a in view.choices + view.actions if a.enabled}
        if request.action_id not in allowed:
            return SessionResult(view, ["当前不能执行这个操作。"], "invalid_action")
        expected = {"item": "key"} if request.action_id == "puzzle:use" else {}
        if request.values != expected:
            return SessionResult(view, ["请选择有效的操作参数。"], "invalid_parameters")
        self._step += 1
        self._revision += 1
        return SessionResult(self.snapshot(), ["操作完成。"])

    def export_save(self) -> JsonObject:
        """导出测试专用格式，禁止作为正式游戏存档使用。"""
        self.snapshot()
        return {"fixture": "ui_demo", "step": self._step, "rewinds": self._rewinds}

    def restore(self, payload: JsonObject) -> SessionResult:
        """恢复测试进度并递增会话版本，拒绝损坏的测试数据。"""
        view = self.snapshot()
        if (not isinstance(payload, dict) or payload.get("fixture") != "ui_demo"
                or type(payload.get("step")) is not int or payload["step"] not in (0, 1, 2)
                or type(payload.get("rewinds", 0)) is not int or payload.get("rewinds", 0) < 0):
            return SessionResult(view, ["测试存档无效。"], "invalid_save")
        self._step = payload["step"]
        self._rewinds = payload.get("rewinds", 0)
        self._revision += 1
        return SessionResult(self.snapshot(), ["已恢复测试进度。"])

    def list_checkpoints(self):
        """固定样例只有开场节点，不模拟真实剧本的自动存档。"""
        self.snapshot()
        return [CheckpointView('hall', '开场', 'hall', 0)]

    def restore_checkpoint(self, checkpoint_id, expected_revision):
        """演示免费回开场；失败分支由真实会话约定测试覆盖。"""
        view = self.snapshot()
        if type(expected_revision) is not int or expected_revision != self._revision:
            return SessionResult(view, ['画面已更新。'], 'stale_revision')
        if checkpoint_id != 'hall':
            return SessionResult(view, ['存档点不存在。'], 'invalid_checkpoint')
        return self.restore({'fixture': 'ui_demo', 'step': 0, 'rewinds': self._rewinds + 1})

    def rewind(self, expected_revision):
        """固定样例没有失败结局，因此没有可重试选择。"""
        view = self.snapshot()
        code = 'rewind_unavailable' if type(expected_revision) is int and expected_revision == self._revision else 'stale_revision'
        return SessionResult(view, ['当前没有可回退的失败选择。'], code)


class MemorySaveStore:
    """内存存储测试替身；数据随实例消失，不替代浏览器持久化。"""

    def __init__(self) -> None:
        self._slots: dict[str, JsonObject] = {}

    def list_slots(self) -> list[str]:
        """返回独立且排序后的槽 ID 列表。"""
        return sorted(self._slots)

    def read(self, slot: str) -> JsonObject:
        """读取独立副本，不存在时统一抛存储错误。"""
        if slot not in self._slots:
            raise StorageError(f"存档槽不存在：{slot}")
        return deepcopy(self._slots[slot])

    def write(self, slot: str, payload: JsonObject) -> None:
        """存储独立副本。"""
        self._slots[slot] = deepcopy(payload)
