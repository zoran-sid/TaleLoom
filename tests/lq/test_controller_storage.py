"""LQ：存档槽与自动存档接入桌面，使用既有迷你数据。"""
import tempfile
import unittest
import json
from pathlib import Path
from taleloom.gui.controller import GameController
from tests.ui_fakes import FakeGameSession


def catalog_controller(root):
    folder = root / 'stories/ui_demo'
    folder.mkdir(parents=True, exist_ok=True)
    data = {'id': 'ui_demo', 'title': '测试', 'start': 'hall', 'scenes': [
        {'id': 'hall', 'text': '门厅', 'choices': [{'id': 'out', 'text': '离开', 'goto': 'out'}]},
        {'id': 'out', 'text': '门外', 'ending': {'id': 'out'}}]}
    (folder / 'story.json').write_text(json.dumps(data), encoding='utf-8')
    return GameController(root / 'stories', root / 'saves', lambda story: FakeGameSession())


class ControllerStorageTest(unittest.TestCase):
    def test_json_roundtrip_and_corrupt_import_keeps_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            c = catalog_controller(Path(folder))
            c.load_catalog(); c.start('ui_demo'); c.submit('choice:take')
            path = Path(folder) / 'export.json'
            self.assertTrue(c.export_json(path))
            c.restart()
            self.assertTrue(c.import_json(path))
            self.assertEqual(c.view.turn, 1)
            before = c.view.to_dict()
            path.write_text('{bad json')
            self.assertFalse(c.import_json(path))
            self.assertEqual(c.view.to_dict(), before)

    def test_multiple_slots_and_auto_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            c = catalog_controller(Path(folder))
            c.load_catalog()
            c.start('ui_demo')
            c.save('1')
            c.submit('choice:take')
            self.assertIn('ui_demo-auto', c.store.list_slots())
            c.save('2')
            self.assertEqual(c.list_saves()[0]['story_id'], 'ui_demo')
            c.load('1')
            self.assertEqual(c.view.turn, 0)
            c.load('2')
            self.assertEqual(c.view.turn, 1)

    def test_bad_action_does_not_overwrite_autosave(self):
        with tempfile.TemporaryDirectory() as folder:
            c = catalog_controller(Path(folder))
            c.load_catalog(); c.start('ui_demo'); c.submit('choice:take')
            before = c.store.read('ui_demo-auto')
            c.submit('missing')
            self.assertEqual(c.store.read('ui_demo-auto'), before)
