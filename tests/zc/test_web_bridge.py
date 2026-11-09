"""JSON 桥接在创建会话或调用引擎前验证请求结构。"""
import json
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from tests.fixtures import STORIES
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

    def test_start_uses_catalog_path_for_unlisted_film_story(self):
        source = next((STORIES / 'film').glob('*/story.json'))
        story_id = source.parent.name
        relative = f'stories/film/{story_id}/story.json'
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(source, target)
            Path(folder, 'catalog.json').write_text(json.dumps(
                [{'id': story_id, 'title': 'x', 'path': relative, 'listed': False}]), encoding='utf-8')
            cwd = os.getcwd()
            os.chdir(folder)
            try:
                result = json.loads(call(json.dumps({'method': 'start', 'story_id': story_id, 'protocol_version': 1,
                                                     'session_id': uuid.uuid4().hex})))
                self.assertEqual(result['view']['story_id'], story_id)
                Path('catalog.json').write_text(json.dumps(
                    [{'id': story_id, 'title': 'x', 'path': '../outside/story.json'}]), encoding='utf-8')
                with self.assertRaises(ValueError):
                    call(json.dumps({'method': 'start', 'story_id': story_id, 'protocol_version': 1,
                                     'session_id': uuid.uuid4().hex}))
            finally:
                os.chdir(cwd)


if __name__ == '__main__':
    unittest.main()
