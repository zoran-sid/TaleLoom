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


class WebBridgeCheckpointTest(unittest.TestCase):
    """影像页经桥接使用正式会话的存档点、回到存档点和回到上一个选择。"""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        for story_id in ('fog_harbor_ledger', 'fog_harbor_film'):
            target = Path(self.folder.name) / f'stories/film/{story_id}/story.json'
            target.parent.mkdir(parents=True)
            shutil.copyfile(STORIES / 'film' / story_id / 'story.json', target)
        Path(self.folder.name, 'catalog.json').write_text(json.dumps(
            [{'id': i, 'title': i, 'path': f'stories/film/{i}/story.json', 'listed': False}
             for i in ('fog_harbor_ledger', 'fog_harbor_film')]), encoding='utf-8')
        os.chdir(self.folder.name)
        self.sid = uuid.uuid4().hex

    def tearDown(self):
        os.chdir(self.cwd)
        self.folder.cleanup()

    def send(self, method, **extra):
        return json.loads(call(json.dumps({'method': method, 'session_id': self.sid, 'protocol_version': 1, **extra})))

    def choose(self, view, choice):
        return self.send('action', action={'action_id': f'choice:{choice}', 'expected_revision': view['revision']})

    def test_checkpoints_lists_reached_points_without_changing_revision(self):
        view = self.send('start', story_id='fog_harbor_film')['view']
        listed = self.send('checkpoints')
        self.assertEqual([p['label'] for p in listed['checkpoints']], ['开场'])
        self.assertEqual(listed['view']['revision'], view['revision'])

    def test_restore_checkpoint_and_stale_revision(self):
        view = self.send('start', story_id='fog_harbor_film')['view']
        view = self.choose(view, 'office')['view']
        stale = self.send('restore_checkpoint', checkpoint_id='lobby', expected_revision=view['revision'] - 1)
        self.assertEqual(stale['error_code'], 'stale_revision')
        back = self.send('restore_checkpoint', checkpoint_id='lobby', expected_revision=view['revision'])
        self.assertIsNone(back['error_code'])
        self.assertEqual(back['view']['scene_id'], 'lobby')
        self.assertEqual(back['view']['rewinds'], 1)

    def test_rewind_after_failure_uses_session_chances(self):
        view = self.send('start', story_id='fog_harbor_film')['view']
        none = self.send('rewind', expected_revision=view['revision'])
        self.assertEqual(none['error_code'], 'rewind_unavailable')

    def test_bad_checkpoint_requests_are_rejected(self):
        self.send('start', story_id='fog_harbor_ledger')
        for extra in ({}, {'checkpoint_id': 3, 'expected_revision': 0}, {'checkpoint_id': 'x', 'expected_revision': '0'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.send('restore_checkpoint', **extra)
        with self.assertRaises(ValueError):
            self.send('rewind', expected_revision=True)


if __name__ == '__main__':
    unittest.main()
