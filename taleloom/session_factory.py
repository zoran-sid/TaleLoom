"""会话的唯一创建入口，桌面 GUI 与网页共用。负责人：ZC。

所有展示端（Tkinter、网页 Worker、测试工具）都通过 create_session 取得
GameSession，不直接实例化某个具体类。ZQO 的正式会话（taleloom/session.py）
通过接口与真实剧本回放测试后，只需修改本文件一处即可全局切换。
"""

from __future__ import annotations

from .model import Story
from .ui_contract import GameSession


def create_session(story: Story) -> GameSession:
    """为已加载、已通过校验的剧本创建一个新会话。

    当前返回 v0 兼容会话 LegacySession。
    """
    from .legacy_session import LegacySession

    return LegacySession(story)
