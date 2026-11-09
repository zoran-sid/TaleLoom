"""桌面文件存档（临时实现，最终归属待定）。负责人：ZRS 暂管，归属见 issue #13。

`docs/team-tasks.md` 4.5 节把桌面文件 `SaveStore` 划给 LQ，而 LQ 的
`web/storage/` 与桌面存储尚未合入；为了不让桌面界面继续等待，这里提供一份
满足 `ui_contract.SaveStore` 的最小实现。LQ 交付后只需改 `controller.py`
的一处导入，界面与测试都不用动。

本模块只存取 JSON 数据，编码、版本与指纹校验由会话（`export_save`
/`restore`）负责；读写失败统一转换为 `StorageError`，界面只展示 message。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..ui_contract import JsonObject, StorageError


class FileSaveStore:
    """每个槽一个 JSON 文件；写入先写临时文件再替换，失败保留旧档。

    槽名只允许字母、数字、下划线和短横线，避免槽名拼进路径造成穿越。
    """

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def list_slots(self) -> list[str]:
        if not self.folder.is_dir():
            return []
        return sorted(path.stem for path in self.folder.glob("*.json") if valid_slot(path.stem))

    def read(self, slot: str) -> JsonObject:
        path = self._path(slot)
        if not path.is_file():
            raise StorageError(f"没有找到存档“{slot}”。先保存一次进度再读取。")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageError(f"存档“{slot}”无法读取：{exc}") from exc
        if not isinstance(payload, dict):
            raise StorageError(f"存档“{slot}”内容无效。")
        return payload

    def write(self, slot: str, payload: JsonObject) -> None:
        path = self._path(slot)
        tmp = path.with_suffix(".json.tmp")
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except (OSError, TypeError, ValueError) as exc:
            tmp.unlink(missing_ok=True)
            raise StorageError(f"无法保存到 {self.folder}：{exc}") from exc

    def _path(self, slot: str) -> Path:
        if not valid_slot(slot):
            raise StorageError(f"存档名称无效：{slot!r}")
        return self.folder / f"{slot}.json"


def valid_slot(slot: str) -> bool:
    """槽名直接变成文件名，因此限制字符与长度，避免路径穿越。"""
    return (isinstance(slot, str) and 0 < len(slot) <= 60
            and slot.replace("_", "").replace("-", "").isalnum())
