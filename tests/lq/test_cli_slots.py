"""LQ：CLI 多槽、自动保存与纯查看行为，不读取真实剧本。"""
import json
import tempfile
import unittest
from pathlib import Path
from taleloom.cli import play
from tests.fixtures import mini_story


class CliSlotsTest(unittest.TestCase):
    def test_manual_slots_auto_and_list_are_connected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'game.json'
            inputs = iter(['存档 1', '1', '存档 2', '读档 1', '背包', '存档列表', '退出'])
            output = []
            play(mini_story(), path, lambda prompt: next(inputs), output.append)
            first = json.loads((path.parent / 'game-1.json').read_text())
            second = json.loads((path.parent / 'game-2.json').read_text())
            auto = json.loads((path.parent / 'game-auto.json').read_text())
            self.assertEqual(first['state']['inventory'], [])
            self.assertEqual(second['state']['inventory'], ['key'])
            self.assertEqual(auto['state']['turn'], 1)
            self.assertIn('你身上什么也没有', '\n'.join(output))

    def test_reading_does_not_create_an_autosave(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'game.json'
            inputs = iter(['看', '背包', '退出'])
            play(mini_story(), path, lambda prompt: next(inputs), lambda text: None)
            self.assertEqual(list(path.parent.iterdir()), [])
