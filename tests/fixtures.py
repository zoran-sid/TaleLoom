"""测试共用的小剧本。各模块测试只依赖 model / loader.parse_story，不依赖真实剧本内容，
剧本作者改剧情不会导致其他人的单元测试失败。"""

from __future__ import annotations

import copy
from pathlib import Path

from taleloom.loader import parse_story
from taleloom.model import Story

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "stories"

MINI = {
    "format_version": 1,
    "id": "mini",
    "title": "迷你剧本",
    "start": "a",
    "items": [{"id": "key", "name": "钥匙", "aliases": ["铜钥匙"]}],
    "scenes": [
        {"id": "a", "title": "门厅", "text": "一扇锁着的门。", "choices": [
            {"id": "take", "text": "捡起钥匙", "once": True, "effects": [{"give_item": "key"}]},
            {"id": "open", "text": "开门", "goto": "b", "when": {"has_item": "key"}},
        ]},
        {"id": "b", "title": "门后", "text": "你出来了。", "ending": {"id": "out", "title": "出门"}},
    ],
}


def mini_raw(**overrides) -> dict:
    raw = copy.deepcopy(MINI)
    raw.update(overrides)
    return raw


def mini_story(**overrides) -> Story:
    return parse_story(mini_raw(**overrides))
