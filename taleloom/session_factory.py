"""会话的唯一创建入口，桌面 GUI 与网页共用。负责人：ZC。

所有展示端（Tkinter、网页 Worker、测试工具）都通过 create_session 取得
GameSession，不直接实例化某个具体类。当前统一返回 ZQO 的正式会话（taleloom/session.py）。
"""

from __future__ import annotations

from .model import Story
from .ui_contract import GameSession


def create_session(story: Story, *, seed: int | None = None, rewind_limit: int = 3) -> GameSession:
    """为已加载、已通过校验的剧本创建一个新会话。

    返回 ZQO 的正式会话。
    """
    from .session import GameSession

    return GameSession(story, seed=seed, rewind_limit=rewind_limit)
