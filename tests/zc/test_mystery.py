"""ZC：推理插件（线索与指认）。"""

import unittest

from taleloom.engine import Engine
from taleloom.loader import parse_story
from taleloom.model import Command
from taleloom.validator import validate
from tests.fixtures import mini_raw


def mystery_story(**extra):
    raw = mini_raw(
        mechanics=["mystery"],
        clues={"knife": {"name": "带血的刀", "text": "藏在花盆里。"}, "letter": {"name": "信", "text": "约在午夜。"}},
        accusation={
            "when": {"visited": "a"},
            "suspects": {"butler": {"name": "管家", "aliases": ["老周"]}, "maid": {"name": "女仆"}},
            "outcomes": [{"suspect": "butler", "when": {"has_clue": "knife"}, "goto": "good"}],
            "default": "bad",
        },
    )
    raw["scenes"] = [
        {"id": "a", "text": "书房。", "choices": [
            {"id": "pot", "text": "翻花盆", "once": True, "effects": [{"add_clue": "knife"}]},
            {"id": "desk", "text": "看书桌", "effects": [{"add_clue": "letter"}]},
        ]},
        {"id": "good", "text": "破案。", "ending": {"id": "good"}},
        {"id": "bad", "text": "冤案。", "ending": {"id": "bad"}},
    ]
    raw.update(extra)
    return parse_story(raw)


class MysteryTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(mystery_story())
        self.engine.start()

    def cmd(self, verb, *args):
        return self.engine.handle(Command(verb, list(args), verb))

    def test_clue_added_once_with_message(self):
        out = self.cmd("choose", "desk")
        self.assertIn("【获得线索】信：约在午夜。", out.lines)
        out = self.cmd("choose", "desk")
        self.assertNotIn("【获得线索】信：约在午夜。", out.lines)

    def test_clue_list(self):
        self.assertIn("你的笔记本还是空的。", self.cmd("clues").lines)
        self.cmd("choose", "pot")
        out = self.cmd("clues")
        self.assertIn("已收集线索（1/2）：", out.lines)

    def test_clue_list_does_not_consume_turn(self):
        self.cmd("clues")
        self.assertEqual(self.engine.state.turn, 0)

    def test_accuse_without_target_lists_suspects(self):
        self.assertIn("管家、女仆", self.cmd("accuse").lines[0])

    def test_accuse_correct_with_evidence(self):
        self.cmd("choose", "pot")
        self.assertEqual(self.cmd("accuse", "老周").ending, "good")

    def test_accuse_correct_without_evidence_falls_to_default(self):
        self.assertEqual(self.cmd("accuse", "管家").ending, "bad")

    def test_accuse_unknown_name(self):
        out = self.cmd("accuse", "园丁")
        self.assertIn("嫌疑人里没有“园丁”", out.lines[0])
        self.assertFalse(out.ended)

    def test_accusation_gate(self):
        story = mystery_story()
        story.data["accusation"]["when"] = {"flag": "ready"}
        engine = Engine(story)
        engine.start()
        out = engine.handle(Command("accuse", ["管家"]))
        self.assertIn("现在不是指认的时候", out.lines[0])

    def test_validate_catches_missing_clue_and_scene(self):
        story = mystery_story()
        story.scenes["a"].choices[0].effects = [{"add_clue": "ghost"}]
        story.data["accusation"]["default"] = "nowhere"
        msgs = [str(i) for i in validate(story)]
        self.assertTrue(any("线索不存在：ghost" in m for m in msgs), msgs)
        self.assertTrue(any("场景不存在：nowhere" in m for m in msgs), msgs)

    def test_accusation_endings_count_as_reachable(self):
        self.assertEqual(validate(mystery_story()), [])


if __name__ == "__main__":
    unittest.main()
