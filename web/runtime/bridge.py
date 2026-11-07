"""Worker 内固定 JSON 消息入口；网页输入不会作为 Python 代码执行。"""

import json
from pathlib import Path

from taleloom.loader import load_story
from taleloom.ui_contract import ActionRequest, PROTOCOL_VERSION
from taleloom.session_factory import create_session

_session = None
_session_id = None


def _validate(request):
    if not isinstance(request, dict):
        raise ValueError('请求应为 JSON 对象')
    if type(request.get('protocol_version')) is not int or request['protocol_version'] != PROTOCOL_VERSION:
        raise ValueError('网页协议版本不匹配，请刷新页面')
    if not isinstance(request.get('session_id'), str) or not request['session_id']:
        raise ValueError('缺少会话标识')
    method = request.get('method')
    if method not in ('start', 'action', 'restore', 'export'):
        raise ValueError('未知操作')
    if method == 'start' and not isinstance(request.get('story_id'), str):
        raise ValueError('缺少剧本标识')
    if method == 'restore' and 'payload' not in request:
        raise ValueError('缺少存档数据')
    if method == 'action':
        action = request.get('action')
        if not isinstance(action, dict) or not isinstance(action.get('action_id'), str):
            raise ValueError('操作格式无效')
        if type(action.get('expected_revision')) is not int:
            raise ValueError('操作版本应为整数')
        values = action.get('values', {})
        if not isinstance(values, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in values.items()
        ):
            raise ValueError('操作参数应为字符串对象')


def call(request_json: str) -> str:
    """处理 start/action/restore/export；会话标识隔离迟到的旧请求。"""
    global _session, _session_id
    request = json.loads(request_json)
    _validate(request)
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
