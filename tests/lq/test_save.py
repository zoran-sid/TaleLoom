"""LQ：存档与读档。"""

import json
import tempfile
import unittest
from pathlib import Path

from taleloom.engine import Engine
from taleloom.model import Command
from taleloom.save import SaveError, load_game, save_game
from tests.fixtures import mini_story


class SaveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "slot.json"
        self.story = mini_story()
        self.engine = Engine(self.story)
        self.engine.start()
        self.engine.handle(Command("choose", ["1"], "1"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_restores_state(self):
        save_game(self.engine.state, self.story, self.path)
        state, notes = load_game(self.path, self.story)
        self.assertEqual(state, self.engine.state)
        self.assertEqual(notes, [])

    def test_resumed_engine_continues(self):
        save_game(self.engine.state, self.story, self.path)
        state, _ = load_game(self.path, self.story)
        engine = Engine(self.story, state)
        self.assertIn("继续游戏", engine.start().lines[0])
        self.assertTrue(engine.handle(Command("choose", ["1"])).ended)

    def test_missing_file(self):
        with self.assertRaisesRegex(SaveError, "没有找到存档"):
            load_game(self.path, self.story)

    def test_corrupted_file(self):
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(SaveError, "损坏"):
            load_game(self.path, self.story)

    def test_save_from_other_story(self):
        save_game(self.engine.state, mini_story(id="other", title="别的故事"), self.path)
        with self.assertRaisesRegex(SaveError, "不能用于"):
            load_game(self.path, self.story)

    def test_missing_state_fields(self):
        save_game(self.engine.state, self.story, self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        del data["state"]["scene"]
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(SaveError, "不完整"):
            load_game(self.path, self.story)

    def test_story_changed_after_save_gives_note(self):
        save_game(self.engine.state, self.story, self.path)
        changed = mini_story()
        changed.scenes["a"].choices[0].id = "renamed"
        _, notes = load_game(self.path, changed)
        self.assertTrue(notes and "修改过" in notes[0])

    def test_no_temp_file_left_behind(self):
        save_game(self.engine.state, self.story, self.path)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["slot.json"])


if __name__ == "__main__":
    unittest.main()
