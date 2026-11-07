"""JSON 桥接在创建会话或调用引擎前验证请求结构。"""
import json
import unittest
from web.runtime.bridge import call


class WebBridgeTest(unittest.TestCase):
    def test_invalid_wire_requests_are_rejected_before_engine_calls(self):
        requests = [None, [], {}, {'method': 'start', 'session_id': 's'},
                    {'method': 'start', 'session_id': 's', 'protocol_version': True},
                    {'method': 'action', 'session_id': 's', 'protocol_version': 1,
                     'action': {'action_id': 'choice:x', 'expected_revision': True}},
                    {'method': 'action', 'session_id': 's', 'protocol_version': 1,
                     'action': {'action_id': 'choice:x', 'expected_revision': 0, 'values': {'x': []}}}]
        for request in requests:
            with self.subTest(request=request), self.assertRaises(ValueError):
                call(json.dumps(request))
