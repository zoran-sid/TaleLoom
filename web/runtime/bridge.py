"""Worker 内固定 JSON 消息入口；网页输入不会作为 Python 代码执行。"""

import json
from pathlib import Path

from taleloom.loader import load_story
from taleloom.ui_contract import ActionRequest
from .factory import create_session

_session = None
_session_id = None


def call(request_json: str) -> str:
    """处理 start/action/restore/export；会话标识隔离迟到的旧请求。"""
    global _session, _session_id
    request = json.loads(request_json)
    method = request['method']
    if method == 'start':
        story_id = request['story_id']
        catalog = json.loads(Path('catalog.json').read_text(encoding='utf-8'))
        if story_id not in {entry['id'] for entry in catalog}:
            raise ValueError('剧本不存在')
        candidate = create_session(load_story(Path('stories') / story_id / 'story.json'))
        result = candidate.start()
        _session, _session_id = candidate, request['session_id']
    else:
        if _session is None or request.get('session_id') != _session_id:
            raise ValueError('会话已切换，请重新打开剧本')
        if method == 'action':
            data = request['action']
            result = _session.dispatch(ActionRequest(data['action_id'], data['expected_revision'], data.get('values', {})))
        elif method == 'restore':
            result = _session.restore(request['payload'])
        elif method == 'export':
            return json.dumps(_session.export_save(), ensure_ascii=False)
        else:
            raise ValueError('未知操作')
    return json.dumps(result.to_dict(), ensure_ascii=False)
