"""存档与读档。负责人：LJ。

存档是 JSON：{"save_version", "story_id", "fingerprint", "state"}。
fingerprint 由剧本结构计算，剧本被修改后读旧档会给出提示而不是崩溃。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .model import Story
from .state import GameState

SAVE_VERSION = 1


class SaveError(Exception):
    """存档无法读取或与当前剧本不匹配。"""


def fingerprint(story: Story) -> str:
    shape = {sid: [c.id for c in s.choices] for sid, s in sorted(story.scenes.items())}
    raw = json.dumps([story.id, story.format_version, shape], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def save_game(state: GameState, story: Story, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "save_version": SAVE_VERSION,
        "story_id": story.id,
        "fingerprint": fingerprint(story),
        "state": state.to_dict(),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)   # 先写临时文件再替换，避免写到一半损坏旧档
    return path


def load_game(path: str | Path, story: Story) -> tuple[GameState, list[str]]:
    """返回 (状态, 提示信息)。存档损坏或属于其他剧本时抛 SaveError。"""
    path = Path(path)
    if not path.is_file():
        raise SaveError(f"没有找到存档：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SaveError(f"存档已损坏：{exc}") from exc
    if not isinstance(payload, dict) or payload.get("save_version") != SAVE_VERSION:
        raise SaveError("存档版本不受支持")
    if payload.get("story_id") != story.id:
        raise SaveError(f"这是《{payload.get('story_id')}》的存档，不能用于《{story.title}》")
    try:
        state = GameState.from_dict(payload["state"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SaveError(f"存档内容不完整：{exc}") from exc
    if state.scene not in story.scenes:
        raise SaveError(f"存档所在场景已不存在：{state.scene}")
    notes = []
    if payload.get("fingerprint") != fingerprint(story):
        notes.append("提示：剧本在存档之后被修改过，部分进度可能与当前版本不一致。")
    return state, notes
