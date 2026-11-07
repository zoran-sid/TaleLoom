"""ZRS：道具谜题插件。"""

import unittest

from taleloom.engine import Engine
from taleloom.loader import parse_story
from taleloom.model import Command
from taleloom.validator import validate
from tests.fixtures import mini_raw


def puzzle_story(**extra):
    raw = mini_raw(
        mechanics=["puzzle"],
        items=[
            {"id": "rod", "name": "木棍"},
            {"id": "hook", "name": "铁钩"},
            {"id": "pole", "name": "钩竿", "aliases": ["竿"]},
            {"id": "key", "name": "钥匙"},
        ],
        combinations=[{"items": ["rod", "hook"], "result": "pole", "message": "你把铁钩绑在木棍上。"}],
        uses=[{"item": "pole", "scene": "a", "effects": [{"give_item": "key"}], "message": "你钩到了钥匙。", "consume": True}],
    )
    raw["scenes"][0]["choices"] = [
        {"id": "search", "text": "翻找", "once": True, "effects": [{"give_item": "rod"}, {"give_item": "hook"}]},
        {"id": "open", "text": "开门", "goto": "b", "when": {"has_item": "key"}},
    ]
    raw.update(extra)
    return parse_story(raw)


class PuzzleTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(puzzle_story())
        self.engine.start()

    def run_cmd(self, verb, *args):
        return self.engine.handle(Command(verb, list(args), " ".join((verb,) + args)))

    def test_combine_then_use(self):
        self.run_cmd("choose", "1")
        out = self.run_cmd("combine", "木棍", "铁钩")
        self.assertIn("【获得物品】钩竿", out.lines)
        self.assertEqual(self.engine.state.inventory, ["pole"])
        out = self.run_cmd("use", "竿")
        self.assertIn("你钩到了钥匙。", out.lines)
        self.assertEqual(self.engine.state.inventory, ["key"])      # consume: true
        self.assertEqual(out.choices, [(1, "开门")])

    def test_combine_requires_items_in_inventory(self):
        out = self.run_cmd("combine", "木棍", "铁钩")
        self.assertIn("你身上没有“木棍”。", out.lines)

    def test_wrong_pair_does_not_consume_turn(self):
        self.run_cmd("choose", "1")
        turn = self.engine.state.turn
        out = self.run_cmd("combine", "木棍", "木棍")
        self.assertIn("这两样东西组合不到一起。", out.lines)
        self.assertEqual(self.engine.state.turn, turn)

    def test_combine_usage_message(self):
        self.assertIn("用法", self.run_cmd("combine", "木棍").lines[0])

    def test_use_in_wrong_place(self):
        self.engine.state.give("pole")
        self.engine.state.scene = "b"
        self.engine.state.ending = None
        self.assertIn("这里用不上它。", self.run_cmd("use", "钩竿").lines)

    def test_validate_reports_unknown_items(self):
        story = puzzle_story(combinations=[{"items": ["rod", "ghost"], "result": "pole"}])
        self.assertTrue(any("物品不存在：ghost" in str(i) for i in validate(story)))


if __name__ == "__main__":
    unittest.main()
