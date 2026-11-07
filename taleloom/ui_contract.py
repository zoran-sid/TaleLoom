"""桌面／网页共用接口 v1；YHT 维护数据，ZQO 维护会话，LQ 维护存储。

本模块只有数据类型与 Protocol，不导入 GUI、文件系统或真实剧本。
现有 Engine / Output 保持兼容；真实会话适配器由 ZQO 实现。
独立开发使用 tests.ui_fakes，具体约定见 docs/contracts.md 第 6 节。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

PROTOCOL_VERSION = 1
JsonObject = dict[str, Any]


@dataclass
class DisplayItem:
    """玩家已知的物品、线索或参数候选；id 用于操作，label 用于显示。"""

    id: str
    label: str
    description: str = ""


@dataclass
class ActionParameter:
    """动作的一个参数；select 候选由插件提供，text 用于自由文字。"""

    key: str
    label: str
    kind: Literal["select", "text"] = "select"
    options: list[DisplayItem] = field(default_factory=list)
    required: bool = True


@dataclass
class ActionSpec:
    """可展示动作；稳定 id 在当前会话中标识操作，不能使用选项序号。"""

    id: str
    label: str
    parameters: list[ActionParameter] = field(default_factory=list)
    enabled: bool = True
    disabled_reason: str = ""


@dataclass
class ResourceView:
    """剧本声明可以向玩家展示的数值；maximum 为空时显示普通数值。"""

    id: str
    label: str
    value: int
    maximum: int | None = None


@dataclass
class ViewSnapshot:
    """完整显示快照；仅含玩家可见数据，读取和修改返回值不能改变游戏。"""

    story_id: str
    story_title: str
    scene_id: str
    scene_title: str
    text: str
    revision: int = 0
    turn: int = 0
    choices: list[ActionSpec] = field(default_factory=list)
    actions: list[ActionSpec] = field(default_factory=list)
    inventory: list[DisplayItem] = field(default_factory=list)
    clues: list[DisplayItem] = field(default_factory=list)
    resources: list[ResourceView] = field(default_factory=list)
    assets: dict[str, str] = field(default_factory=dict)
    ended: bool = False
    ending_id: str | None = None
    ending_title: str | None = None
    protocol_version: int = PROTOCOL_VERSION

    def to_dict(self) -> JsonObject:
        """导出独立的 JSON 可序列化数据，供浏览器消息传递。"""
        return asdict(self)


@dataclass
class ActionRequest:
    """提交动作 ID、所见版本及参数值；会话必须重新验证合法性。"""

    action_id: str
    expected_revision: int
    values: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        """导出浏览器可传递的请求对象，不包含 Python 代码。"""
        return asdict(self)


@dataclass
class SessionResult:
    """操作结果：完整快照、反馈与可机器判断的错误码；失败保留原状态。"""

    view: ViewSnapshot
    messages: list[str] = field(default_factory=list)
    error_code: str | None = None

    @property
    def ok(self) -> bool:
        """本次调用是否成功。"""
        return self.error_code is None

    def to_dict(self) -> JsonObject:
        """导出结果；接收端以 error_code 是否为空判断成功。"""
        return asdict(self)


@runtime_checkable
class GameSession(Protocol):
    """绑定一个已加载剧本的会话；重新开始或切换剧本时创建新实例。

    start 幂等；其余方法在 start 后使用。snapshot 是无副作用读取。
    每次成功修改状态或恢复存档后 revision 单调递增；失败不改变状态。
    expected_revision 过期时返回 stale_revision；动作和参数错误分别返回
    invalid_action / invalid_parameters；读档错误返回 invalid_save。
    对用户可预期的失败通过 SessionResult 返回，未启动属于开发调用错误。
    """

    def start(self) -> SessionResult:
        """开始会话；重复调用不能再次触发开场事件。"""
        ...

    def snapshot(self) -> ViewSnapshot:
        """返回独立快照，不推进回合或随机状态。"""
        ...

    def dispatch(self, request: ActionRequest) -> SessionResult:
        """验证版本、动作及参数后执行一次；拒绝未知或已失效的操作。"""
        ...

    def export_save(self) -> JsonObject:
        """导出标准存档数据，无文件读写；真实实现沿用 save.py 的版本规则。"""
        ...

    def restore(self, payload: JsonObject) -> SessionResult:
        """验证后恢复当前剧本的存档；失败保留当前会话，成功使旧动作失效。"""
        ...


class StorageError(Exception):
    """可展示给玩家的存储错误，例如槽不存在、无法读写或容量不足。"""


@runtime_checkable
class SaveStore(Protocol):
    """存档槽的存储边界；数据编码／版本校验由会话负责。

    read/write 不泄漏可变引用；预期存储失败统一抛 StorageError。
    桌面文件与浏览器持久化各自实现，桥接层可异步完成浏览器操作。
    """

    def list_slots(self) -> list[str]:
        """返回已存在槽的稳定 ID；界面可按 ID 读取存档元数据。"""
        ...

    def read(self, slot: str) -> JsonObject:
        """读取独立数据；不存在或无法读取时抛 StorageError。"""
        ...

    def write(self, slot: str, payload: JsonObject) -> None:
        """成功后存入独立副本；失败时保留已有存档。"""
        ...
