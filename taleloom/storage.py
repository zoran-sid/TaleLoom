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
