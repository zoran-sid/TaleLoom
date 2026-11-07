"""正式会话的唯一接入点；ZQO 交付后在这里显式替换，不静默探测接口。"""

from taleloom.model import Story
from taleloom.ui_contract import GameSession
from .legacy_session import LegacySession


def create_session(story: Story) -> GameSession:
    """创建当前已验收的 v0 会话。"""
    return LegacySession(story)
