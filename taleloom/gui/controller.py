"""桌面界面的状态机。负责人：ZRS。

不导入 Tkinter：只处理「选剧本 → 开始／继续 → 提交动作 → 存读档」的流程，
窗口只负责把 self.view 画出来。开发和测试时注入 tests.ui_fakes 的会话与
存储；正式运行时由 taleloom.session_factory.create_session 与 gui.storage.FileSaveStore 提供。
"""

from __future__ import annotations
import json

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ..loader import StoryFormatError, load_story
from ..model import Story
from ..ui_contract import (
    ActionRequest, GameSession, SaveStore, SessionResult, StorageError, ViewSnapshot,
)
from ..validator import errors, validate
# 统一使用 LQ 接管的文件存储（issue #13）；旧导入路径只保留兼容别名。
from ..storage import FileSaveStore, valid_slot

QUICK_SLOT = "quick"


@dataclass(frozen=True)
class StoryEntry:
    """书架上的一部剧本；目录名与 story.json 中的 id 一致。"""

    id: str
    title: str
    genre: str
    folder: Path


class SessionFactory(Protocol):
    def __call__(self, story: Story) -> GameSession: ...


def load_catalog(stories_dir: str | Path) -> tuple[list[StoryEntry], list[str]]:
    """读取 stories_dir 下所有 story.json，返回可用剧本与逐条错误。

    单部剧本损坏不会挡住其他剧本；错误信息直接给玩家看，不抛异常。
    """
    stories_dir = Path(stories_dir)
    entries: list[StoryEntry] = []
    problems: list[str] = []
    for folder in sorted(p.parent for p in stories_dir.glob("*/story.json")):
        try:
            story = load_story(folder)
        except StoryFormatError as exc:
            problems.append(f"{folder.name}：{exc}")
            continue
        bad = errors(validate(story))
        if bad:
            problems.append(f"{folder.name}：剧本未通过校验（{bad[0].path}: {bad[0].message}）")
            continue
        meta = story.meta or {}
        genre = meta.get("genre") if isinstance(meta.get("genre"), str) else "文字冒险"
        entries.append(StoryEntry(story.id, story.title, genre, folder))
    return entries, problems


class GameController:
    """桌面界面的状态机；窗口只渲染 view、messages 与 error。

    动作串行：submit 在忙时直接拒绝；成功提交后 revision 前进，过期请求由
    会话返回 stale_revision。查看背包、线索与资源只读 self.view，不推进回合。
    存档按剧本隔离：槽名是 <剧本 id>-quick，同一目录下的不同剧本互不覆盖。
    """

    def __init__(
        self,
        stories_dir: str | Path,
        saves_dir: str | Path,
        create_session: SessionFactory,
        make_store: Callable[[str], SaveStore] | None = None,
    ):
        self.stories_dir = Path(stories_dir)
        self.saves_dir = Path(saves_dir)
        self._create_session = create_session
        self._make_store = make_store or FileSaveStore
        self.stories: list[StoryEntry] = []
        self.problems: list[str] = []
        self.session: GameSession | None = None
        self.store: SaveStore | None = None
        self.store_slot = ""
        self.story: StoryEntry | None = None
        self.view: ViewSnapshot | None = None
        self.messages: list[str] = []
        self.error: str | None = None
        self.dirty = False
        self.busy = False

    def load_catalog(self) -> None:
        self.stories, self.problems = load_catalog(self.stories_dir)

    def has_save(self, story_id: str) -> bool:
        try:
            return any(self._slot(story_id, slot) in self._make_store(self.saves_dir).list_slots()
                       for slot in (QUICK_SLOT, "auto"))
        except StorageError:
            return False

    def start(self, story_id: str, resume: bool = False) -> bool:
        """打开剧本；resume 时读取快速存档。返回是否进入游戏。"""
        if self.busy:
            return False
        entry = next((s for s in self.stories if s.id == story_id), None)
        if entry is None:
            self.error = "找不到这个剧本，请返回书架重试。"
            return False
        self.busy = True
        self.error = None
        self.messages = []
        try:
            story = load_story(entry.folder)
            session = self._create_session(story)
            store = self._make_store(self.saves_dir)
            self.story, self.store, self.store_slot = entry, store, self._slot(entry.id)
            result = session.start()
            self.session = session
            self._apply(result)
            payload = None
            if resume:
                try:
                    slots = store.list_slots()
                    candidates = [s for s in (self.store_slot, self._slot(entry.id, 'auto')) if s in slots]
                    selected = candidates[0] if candidates else self.store_slot
                    if hasattr(store, 'describe_slots') and candidates:
                        times = {row['slot']: row.get('saved_at', '') for row in store.describe_slots(entry.id)}
                        selected = max(candidates, key=lambda key: times.get(key, ''))
                    payload = store.read(selected)
                except StorageError as exc:
                    self.error = "没有读取到上次的进度，已从头开始。" if "没有找到" in str(exc) else str(exc)
            if payload is not None:
                result = session.restore(payload)
                self._apply(result)
            self.dirty = payload is None or not result.ok
            return True
        except (StoryFormatError, RuntimeError, ValueError) as exc:
            self._reset()
            self.error = f"无法打开剧本：{exc}。请检查剧本文件后重试。"
            return False
        finally:
            self.busy = False

    def submit(self, action_id: str, values: dict[str, str] | None = None) -> SessionResult | None:
        """串行提交一次动作；忙时或未开始时返回 None，失败保留原状态。"""
        if self.busy or self.session is None or self.view is None:
            return None
        self.busy = True
        self.error = None
        try:
            before_revision = self.view.revision
            result = self.session.dispatch(ActionRequest(action_id, self.view.revision, values or {}))
            self._apply(result)
            if result.ok:
                self.dirty = True
                if result.view.revision != before_revision:
                    try:
                        self.store.write(self._slot(self.story.id, "auto"), self.session.export_save())
                    except StorageError as exc:
                        self.error = f"自动存档失败：{exc}；当前进度仍保留。"
            return result
        except RuntimeError as exc:
            self.error = f"操作没有完成：{exc}。可以继续游戏，或先保存进度。"
            return None
        finally:
            self.busy = False

    def save(self, slot: str = QUICK_SLOT) -> bool:
        """写入所选槽（默认快速存档）；失败时保留旧档与当前进度。"""
        if self.session is None or self.busy:
            return False
        self.busy = True
        try:
            self.store.write(self._slot(self.story.id, slot), self.session.export_save())
        except StorageError as exc:
            self.error = str(exc)
            self.messages = []
            return False
        finally:
            self.busy = False
        self.dirty = False
        self.error = None
        self.messages = ["进度已保存。"]
        return True

    def load(self, slot: str = QUICK_SLOT) -> bool:
        """读取所选槽；失败（含坏档）不影响当前进度。"""
        if self.session is None or self.busy:
            return False
        self.busy = True
        self.error = None
        try:
            result = self.session.restore(self.store.read(self._slot(self.story.id, slot)))
            self._apply(result)
            if result.ok:
                self.dirty = False
            return result.ok
        except StorageError as exc:
            self.error = str(exc)
            return False
        finally:
            self.busy = False

    def restart(self) -> bool:
        if self.story is None:
            return False
        return self.start(self.story.id, resume=False)

    def export_json(self, path: str | Path) -> bool:
        """导出当前存档供网页导入；失败不影响游戏。"""
        from ..save import atomic_write
        if self.session is None or self.busy:
            return False
        try:
            atomic_write(path, self.session.export_save())
            self.messages, self.error = ['存档已导出。'], None
            return True
        except (OSError, ValueError) as exc:
            self.error = f'无法导出存档：{exc}'
            return False

    def import_json(self, path: str | Path) -> bool:
        """验证后导入网页/桌面 JSON；坏档不改变会话和已有文件。"""
        if self.session is None or self.busy:
            return False
        try:
            result = self.session.restore(json.loads(Path(path).read_text(encoding='utf-8')))
            self._apply(result)
            if result.ok:
                self.dirty = True
            return result.ok
        except (OSError, UnicodeError, ValueError) as exc:
            self.error = f'无法导入存档，原进度已保留：{exc}'
            return False

    def home(self) -> None:
        self._reset()

    def list_saves(self) -> list[dict]:
        """列出当前故事的槽元数据，不推进游戏。"""
        if self.story is None or self.store is None:
            return []
        if hasattr(self.store, "describe_slots"):
            return self.store.describe_slots(self.story.id)
        return [{"slot": slot} for slot in self.store.list_slots() if slot.startswith(self.story.id + "-")]

    def _slot(self, story_id: str, slot: str = QUICK_SLOT) -> str:
        if not valid_slot(slot):
            raise StorageError("存档槽名称无效")
        return f"{story_id}-{slot}"

    def _apply(self, result: SessionResult) -> None:
        self.view = result.view
        self.messages = list(result.messages)
        self.error = result.messages[0] if result.error_code is not None else None

    def _reset(self) -> None:
        self.session = None
        self.store = None
        self.store_slot = ""
        self.story = None
        self.view = None
        self.messages = []
        self.error = None
        self.dirty = False
