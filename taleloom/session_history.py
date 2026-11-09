"""会话回退记录与纯数据校验。负责人：ZQO；不读写存档文件。"""

from copy import deepcopy

from .save import decode_save
from .ui_contract import CheckpointView


class SessionHistory:
    """保存已到达节点及一个选择前的状态；嵌套状态不再携带回退记录。"""

    def __init__(self, limit=3):
        if type(limit) is not int or limit < 0:
            raise ValueError('rewind_limit 必须是非负整数')
        self.limit = limit
        self.mistakes = 0
        self.rewinds = 0
        self.points = []
        self.previous = None

    def summaries(self):
        """返回独立、可展示的存档点摘要。"""
        return [CheckpointView(p['id'], p['label'], p['state']['scene'], p['state']['turn'])
                for p in self.points]

    def capture(self, state, label):
        """记录当前节点；重访同一节点时替换它并舍弃之后的旧分支。"""
        if state.ending or not label:
            return
        index = next((i for i, p in enumerate(self.points) if p['id'] == state.scene), len(self.points))
        self.points[index:] = [{'id': state.scene, 'label': label, 'state': state.to_dict()}]

    def to_dict(self):
        """导出无共享引用的回退记录，放在标准状态 ext.session 中。"""
        return deepcopy({'version': 1, 'rewind_limit': self.limit, 'mistakes': self.mistakes,
                         'rewinds': self.rewinds, 'checkpoints': self.points, 'previous_choice': self.previous})

    @classmethod
    def decode(cls, data, envelope, story):
        """严格校验全部嵌套节点，再返回独立记录；损坏时不部分恢复。"""
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
            raise ValueError('回退记录版本无效')
        history = cls(data['rewind_limit'])
        for name in ('mistakes', 'rewinds'):
            value = data[name]
            if type(value) is not int or value < 0:
                raise ValueError('回退次数必须是非负整数')
            setattr(history, name, value)
        if history.mistakes > history.limit:
            raise ValueError('已使用机会超过上限')

        def checked_state(raw):
            if not isinstance(raw, dict) or not isinstance(raw.get('ext', {}), dict) or 'session' in raw.get('ext', {}):
                raise ValueError('回退节点不能嵌套回退记录')
            state, _ = decode_save({**envelope, 'state': raw}, story)
            if state.ending or state.random_seed != envelope['state'].get('random_seed', 0):
                raise ValueError('回退节点必须是同局未结束状态')
            return state.to_dict()

        def checked_points(points, turn):
            if not isinstance(points, list):
                raise ValueError('存档点应为列表')
            result, seen, last_turn = [], set(), -1
            for point in points:
                if not isinstance(point, dict) or not isinstance(point.get('id'), str):
                    raise ValueError('存档点格式无效')
                raw = checked_state(point['state'])
                if point['id'] != raw['scene'] or point['id'] in seen:
                    raise ValueError('存档点 ID 无效或重复')
                if not isinstance(point.get('label'), str) or not point['label'].strip():
                    raise ValueError('存档点名称无效')
                if not last_turn <= raw['turn'] <= turn:
                    raise ValueError('存档点时间顺序无效')
                last_turn = raw['turn']
                seen.add(point['id'])
                result.append({'id': point['id'], 'label': point['label'], 'state': raw})
            return result

        history.points = checked_points(data['checkpoints'], envelope['state']['turn'])
        previous = data['previous_choice']
        if previous is not None:
            if not isinstance(previous, dict):
                raise ValueError('上一个选择格式无效')
            raw = checked_state(previous['state'])
            if raw['turn'] > envelope['state']['turn']:
                raise ValueError('上一个选择不能在未来')
            points = checked_points(previous['checkpoints'], raw['turn'])
            history.previous = {'state': raw, 'checkpoints': points}
        return history
