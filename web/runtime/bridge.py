"""Worker 内固定 JSON 消息入口；网页输入不会作为 Python 代码执行。"""

import json
from pathlib import Path, PurePosixPath

from dataclasses import asdict

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
    if method not in ('start', 'action', 'restore', 'export', 'checkpoints', 'restore_checkpoint', 'rewind'):
        raise ValueError('未知操作')
    if method in ('restore_checkpoint', 'rewind') and type(request.get('expected_revision')) is not int:
        raise ValueError('操作版本应为整数')
    if method == 'restore_checkpoint' and not isinstance(request.get('checkpoint_id'), str):
        raise ValueError('缺少存档点标识')
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


def _story_path(story_id: str) -> Path:
    """按游戏包内目录找到剧本文件；影像版剧本登记了 path，其余在 stories/<id>/。"""
    catalog = json.loads(Path('catalog.json').read_text(encoding='utf-8'))
    entry = next((e for e in catalog if isinstance(e, dict) and e.get('id') == story_id), None)
    if entry is None:
        raise ValueError('剧本不存在')
    path = PurePosixPath(entry.get('path') or f'stories/{story_id}/story.json')
    if path.is_absolute() or path.parts[0] != 'stories' or '..' in path.parts or path.name != 'story.json':
        raise ValueError('剧本路径无效')
    return Path(*path.parts)


def call(request_json: str) -> str:
    """处理 start/action/restore/export 与存档点操作；会话标识隔离迟到的旧请求。

    checkpoints 只读取已到达的存档点；restore_checkpoint 与 rewind 都带所见版本，
    画面过期时由会话拒绝，原进度保留。
    """
    global _session, _session_id
    request = json.loads(request_json)
    _validate(request)
    method = request['method']
    if method == 'start':
        candidate = create_session(load_story(_story_path(request['story_id'])))
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
        elif method == 'checkpoints':
            points = [asdict(p) for p in _session.list_checkpoints()]
            return json.dumps({'checkpoints': points, 'view': _session.snapshot().to_dict()}, ensure_ascii=False)
        elif method == 'restore_checkpoint':
            result = _session.restore_checkpoint(request['checkpoint_id'], request['expected_revision'])
        elif method == 'rewind':
            result = _session.rewind(request['expected_revision'])
        else:
            raise ValueError('未知操作')
    return json.dumps(result.to_dict(), ensure_ascii=False)
