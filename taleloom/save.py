"""存档与读档。负责人：LQ。

存档是 JSON：{"save_version", "story_id", "fingerprint", "state"}。
fingerprint 由剧本结构计算，剧本被修改后读旧档会给出提示而不是崩溃。
"""

from __future__ import annotations

import hashlib
import json
import os
import math
import tempfile
from pathlib import Path

from .model import Story
from .state import GameState

SAVE_VERSION = 1


class SaveError(ValueError):
    """存档无法读取或与当前剧本不匹配。"""


def fingerprint(story: Story) -> str:
    shape = {sid: [c.id for c in s.choices] for sid, s in sorted(story.scenes.items())}
    raw = json.dumps([story.id, story.format_version, shape], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def json_copy(value):
    """复制严格 JSON 数据，拒绝非字符串键、非有限数和 Python 专属对象。"""
    def check(value):
        if value is None or type(value) in (str, bool, int):
            return
        if type(value) is float and math.isfinite(value):
            return
        if type(value) is list:
            for item in value:
                check(item)
            return
        if type(value) is dict and all(type(k) is str for k in value):
            for item in value.values():
                check(item)
            return
        raise SaveError('存档内容必须为有效 JSON 数据')
    try:
        check(value)
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (RecursionError, TypeError, ValueError) as exc:
        raise SaveError(f'存档内容无法编码：{exc}') from exc


def encode_save(state: GameState, story: Story) -> dict:
    """纯数据编码：生成独立的 v1 信封，并验证状态；不读写文件。"""
    payload = {
        "save_version": SAVE_VERSION,
        "story_id": story.id,
        "fingerprint": fingerprint(story),
        "state": state.to_dict(),
    }
    decode_save(payload, story)
    return json_copy(payload)


def decode_save(payload: dict, story: Story) -> tuple[GameState, list[str]]:
    """纯数据解码：返回 (独立状态, 剧本变化提示)，坏档统一抛 SaveError。"""
    payload = json_copy(payload)
    if not isinstance(payload, dict) or type(payload.get('save_version')) is not int or payload['save_version'] != SAVE_VERSION:
        raise SaveError("存档版本不受支持")
    if payload.get("story_id") != story.id:
        raise SaveError(f"这是《{payload.get('story_id')}》的存档，不能用于《{story.title}》")
    try:
        state = GameState.from_dict(payload["state"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SaveError(f"存档内容不完整：{exc}") from exc
    if state.story_id != story.id:
        raise SaveError('存档内部剧本 ID 不匹配')
    if not isinstance(state.scene, str) or state.scene not in story.scenes:
        raise SaveError(f"存档所在场景已不存在：{state.scene}")
    for field in ('flags', 'inventory', 'visited', 'used_choices', 'fired_triggers', 'history'):
        value = getattr(state, field)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise SaveError(f'状态字段 {field} 应为字符串列表')
    if not isinstance(state.vars, dict) or not all(isinstance(k, str) and type(v) is int for k, v in state.vars.items()):
        raise SaveError('资源 vars 应为名称到整数的映射')
    if type(state.turn) is not int or state.turn < 0:
        raise SaveError('回合 turn 应为非负整数')
    if type(getattr(state, 'random_seed', 0)) is not int:
        raise SaveError('random_seed 应为整数')
    if not isinstance(state.ext, dict) or not all(isinstance(v, dict) for v in state.ext.values()):
        raise SaveError('插件 ext 应为名称到对象的映射')
    mystery = state.ext.get('mystery', {})
    for field in ('clues', 'examined', 'asked'):
        value = mystery.get(field, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise SaveError(f'mystery.{field} 应为字符串列表')
    if not isinstance(mystery.get('act', ''), str):
        raise SaveError('mystery.act 应为字符串')
    _validate_unit_progress(mystery.get('units', {}))
    ending = story.scenes[state.scene].ending
    if state.ending != (ending.get('id', state.scene) if ending else None):
        raise SaveError('结局与场景不一致')
    if any(i not in story.items for i in state.inventory):
        raise SaveError('存档包含未知物品')
    notes = []
    if payload.get("fingerprint") != fingerprint(story):
        notes.append("提示：剧本在存档之后被修改过，部分进度可能与当前版本不一致。")
    return state, notes


def _validate_unit_progress(units: object) -> None:
    """检查调查进度的存储结构；允许未开始、旧剧本单元及扩展字段。"""
    if not isinstance(units, dict):
        raise SaveError('mystery.units 应为单元 ID 到进度对象的映射')
    for uid, entry in units.items():
        prefix = f'mystery.units.{uid}'
        if not isinstance(entry, dict):
            raise SaveError(f'{prefix} 应为进度对象')
        spots = entry.get('spots', [])
        if not isinstance(spots, list) or not all(isinstance(s, str) for s in spots):
            raise SaveError(f'{prefix}.spots 应为字符串列表')
        for field in ('tries', 'hints'):
            value = entry.get(field, 0)
            if type(value) is not int or value < 0:
                raise SaveError(f'{prefix}.{field} 应为非负整数')
        if not isinstance(entry.get('grade', ''), str):
            raise SaveError(f'{prefix}.grade 应为字符串')
        last = entry.get('last', {})
        if not isinstance(last, dict) or not all(isinstance(v, str) for v in last.values()):
            raise SaveError(f'{prefix}.last 应为槽位到选项字符串的映射')


def atomic_write(path: str | Path, payload: dict) -> Path:
    """原子保存严格 JSON；失败清理临时文件且保留旧文件，异常由调用者转换。"""
    raw = json.dumps(json_copy(payload), ensure_ascii=False, indent=2)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name, suffix='.tmp', delete=False) as file:
            temporary = Path(file.name)
            file.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return path


def save_game(state: GameState, story: Story, path: str | Path) -> Path:
    """兼容 CLI 文件保存入口，失败时保留旧档并抛 SaveError。"""
    try:
        return atomic_write(path, encode_save(state, story))
    except OSError as exc:
        raise SaveError(f'无法保存存档：{exc}') from exc


def load_game(path: str | Path, story: Story) -> tuple[GameState, list[str]]:
    """兼容 CLI 读取入口；文件端与会话使用相同的纯数据校验。"""
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise SaveError(f'没有找到存档：{path}') from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise SaveError(f'存档已损坏或无法读取：{exc}') from exc
    return decode_save(payload, story)
