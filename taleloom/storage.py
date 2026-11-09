"""LQ：接管 ZRS 临时文件 SaveStore（#13）；不改协议或 v1 存档。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from .save import atomic_write, json_copy, SaveError
from .ui_contract import JsonObject, StorageError


def valid_slot(slot: str) -> bool:
    """槽只能是有限长度的安全文件名，拒绝目录穿越。"""
    return isinstance(slot, str) and re.fullmatch(r'[\w-]{1,60}', slot) is not None


class FileSaveStore:
    """每槽一份 JSON；先成功写临时文件再原子替换，失败保留旧档。"""
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def _path(self, slot: str) -> Path:
        if not valid_slot(slot):
            raise StorageError(f'存档名称无效：{slot!r}')
        path = self.folder / (slot + '.json')
        if path.is_symlink():
            raise StorageError('存档不能是符号链接')
        return path

    def list_slots(self) -> list[str]:
        """返回已存在槽名的独立排序列表。"""
        try:
            if not self.folder.exists():
                return []
            return sorted(p.stem for p in self.folder.iterdir()
                          if p.suffix == '.json' and p.is_file() and not p.is_symlink() and valid_slot(p.stem))
        except OSError as exc:
            raise StorageError(f'无法列出存档：{exc}') from exc

    def read(self, slot: str) -> JsonObject:
        """读取独立 JSON 对象，损坏或不存在时抛 StorageError。"""
        try:
            payload = json_copy(json.loads(self._path(slot).read_text(encoding='utf-8')))
            if not isinstance(payload, dict):
                raise ValueError('存档应为 JSON 对象')
            return payload
        except FileNotFoundError as exc:
            raise StorageError(f'没有找到存档“{slot}”。先保存一次进度再读取。') from exc
        except (OSError, UnicodeError, ValueError) as exc:
            raise StorageError(f'存档“{slot}”无法读取：{exc}') from exc

    def write(self, slot: str, payload: JsonObject) -> None:
        """编码或写入失败时保留旧档，错误统一交给界面展示。"""
        path = self._path(slot)
        try:
            if not isinstance(payload, dict):
                raise SaveError('存档应为 JSON 对象')
            atomic_write(path, payload)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f'无法保存到 {self.folder}：{exc}') from exc

    def describe_slots(self, story_id: str | None = None) -> list[dict]:
        """提供槽 ID、文件时间、场景与回合，单个坏档不会阻挡其他槽。"""
        rows = []
        for slot in self.list_slots():
            try:
                data = self.read(slot)
                if story_id is not None and data.get('story_id', story_id if slot.startswith(story_id + '-') else None) != story_id:
                    continue
                state = data.get('state', {})
                rows.append({'slot': slot, 'story_id': data.get('story_id', story_id),
                             'scene': state.get('scene'), 'turn': state.get('turn'),
                             'saved_at': datetime.fromtimestamp(self._path(slot).stat().st_mtime, timezone.utc).isoformat()})
            except (StorageError, OSError, AttributeError):
                if story_id is None or slot.startswith(story_id + '-'):
                    rows.append({'slot': slot, 'error': '存档损坏或无法读取'})
        return rows


def checkpoint_bundle(story_id: str, entries: list[dict]) -> dict:
    """构造可跨端交换的检查点容器；内部 save 仍为未改变的 v1 标准存档。

    存储层验证容器及身份/元数据一致性；恢复时仍由会话完整校验剧情状态。
    一次写整个容器，回退裁剪不会留下半份索引或已作废的后续节点。
    """
    try:
        if not valid_slot(story_id):
            raise SaveError('剧本 ID 无效')
        data = json_copy(entries)
        if not isinstance(data, list) or len(data) > 64:
            raise SaveError('存档点应为至多 64 项的列表')
        labels = set()
        for entry in data:
            if not isinstance(entry, dict):
                raise SaveError('存档点应为对象')
            label = entry.get('label')
            if not isinstance(label, str) or not label.strip() or len(label) > 120 or label in labels:
                raise SaveError('存档点名称为空、过长或重复')
            labels.add(label)
            if not isinstance(entry.get('scene'), str):
                raise SaveError('存档点场景名称无效')
            for key in ('turn', 'at'):
                if type(entry.get(key)) is not int or not 0 <= entry[key] <= 2 ** 53 - 1:
                    raise SaveError(f'存档点 {key} 应为跨端可精确表示的非负整数')
            save = entry.get('save')
            if not isinstance(save, dict) or type(save.get('save_version')) is not int or save['save_version'] != 1:
                raise SaveError('存档点必须含标准 v1 游戏存档')
            state = save.get('state')
            if (save.get('story_id') != story_id or not isinstance(state, dict)
                    or state.get('story_id') != story_id or not isinstance(state.get('scene'), str)
                    or type(state.get('turn')) is not int or state['turn'] != entry['turn']
                    or state.get('ending') is not None):
                raise SaveError('存档点身份、回合或游戏状态不匹配')
        return {'checkpoint_version': 1, 'story_id': story_id, 'entries': data}
    except (SaveError, TypeError, ValueError) as exc:
        raise StorageError(f'存档点数据无效：{exc}') from exc


class CheckpointStore:
    """桌面检查点容器，适配现有 SaveStore；不接管会话层的回退或机会规则。

    文件端使用 <story_id>-checkpoints 槽，容器可直接导入浏览器
    CinematicSaveStore；每个 entry.save 也能单独作为标准游戏存档恢复。
    """
    def __init__(self, store, story_id: str):
        checkpoint_bundle(story_id, [])
        self.store = store
        self.story_id = story_id
        self.slot = story_id + '-checkpoints'

    def read_entries(self) -> list[dict]:
        """返回独立节点列表；缺失时为空，损坏时明确抛错而不覆盖文件。"""
        if self.slot not in self.store.list_slots():
            return []
        payload = self.store.read(self.slot)
        self._validate_envelope(payload)
        return checkpoint_bundle(self.story_id, payload['entries'])['entries']

    def write_entries(self, entries: list[dict]) -> None:
        """原子替换节点列表，用于新增节点、重新开始或回退后的裁剪。"""
        self.store.write(self.slot, checkpoint_bundle(self.story_id, entries))

    def export_bundle(self) -> dict:
        """导出跨端容器；不会把标准游戏状态改成新格式。"""
        return checkpoint_bundle(self.story_id, self.read_entries())

    def import_bundle(self, payload: dict) -> None:
        """整体验证成功后才替换；错误剧本/版本或坏条目保留已有节点。"""
        self._validate_envelope(payload)
        self.write_entries(payload['entries'])

    def _validate_envelope(self, payload):
        if (not isinstance(payload, dict) or type(payload.get('checkpoint_version')) is not int
                or payload['checkpoint_version'] != 1 or payload.get('story_id') != self.story_id
                or 'entries' not in payload):
            raise StorageError('存档点容器版本或剧本不匹配')
