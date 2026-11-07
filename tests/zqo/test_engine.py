"""ZQO：引擎核心流程。直接构造 Command，不依赖解析器。"""

import unittest

from taleloom.engine import Engine
from taleloom.loader import parse_story
from taleloom.model import Command
from taleloom.rules import RuleError
from tests.fixtures import mini_raw, mini_story


def choose(engine, target):
    return engine.handle(Command("choose", [str(target)], str(target)))


class EngineFlowTest(unittest.TestCase):
    def test_start_describes_first_scene(self):
        out = Engine(mini_story()).start()
        self.assertIn("== 门厅 ==", out.lines)
        self.assertEqual(out.choices, [(1, "捡起钥匙")])   # “开门”需要钥匙

    def test_condition_gated_choice_appears(self):
        engine = Engine(mini_story())
        engine.start()
        out = choose(engine, 1)
        self.assertEqual(out.choices, [(1, "开门")])        # once 选项已消失

    def test_choose_by_id_and_reach_ending(self):
        engine = Engine(mini_story())
        engine.start()
        choose(engine, "take")
        out = choose(engine, "open")
        self.assertTrue(out.ended)
        self.assertEqual(out.ending, "out")
        self.assertIn("【结局】出门", out.lines)

    def test_invalid_choice_does_not_advance_turn(self):
        engine = Engine(mini_story())
        engine.start()
        out = choose(engine, 9)
        self.assertIn("没有编号为“9”的选项。", out.lines)
        self.assertEqual(engine.state.turn, 0)

    def test_after_ending_actions_are_refused(self):
        engine = Engine(mini_story())
        engine.start()
        choose(engine, 1)
        choose(engine, 1)
        out = choose(engine, 1)
        self.assertIn("故事已经结束", out.lines[0])

    def test_unknown_verb_message(self):
        engine = Engine(mini_story())
        engine.start()
        out = engine.handle(Command("dance", [], "跳舞"))
        self.assertIn("无法理解", out.lines[0])

    def test_history_records_raw_input(self):
        engine = Engine(mini_story())
        engine.start()
        choose(engine, 1)
        engine.handle(Command("look", [], "看"))
        self.assertEqual(engine.state.history, ["1", "看"])


class TurnRulesTest(unittest.TestCase):
    def countdown_story(self):
        raw = mini_raw(
            vars={"air": 2},
            every_turn=[{"add_var": ["air", -1]}],
            triggers=[{"id": "gone", "when": {"var": ["air", "<=", 0]}, "effects": [{"goto": "dead"}]}],
        )
        raw["scenes"][0]["choices"].append({"id": "wait", "text": "等待"})
        raw["scenes"].append({"id": "dead", "text": "窒息。", "ending": {"id": "dead"}})
        return parse_story(raw)

    def test_every_turn_and_trigger(self):
        engine = Engine(self.countdown_story())
        engine.start()
        engine.handle(Command("choose", ["wait"]))
        self.assertEqual(engine.state.vars["air"], 1)
        out = engine.handle(Command("choose", ["wait"]))
        self.assertEqual(out.ending, "dead")

    def test_look_does_not_consume_turn(self):
        engine = Engine(self.countdown_story())
        engine.start()
        engine.handle(Command("look"))
        self.assertEqual(engine.state.vars["air"], 2)

    def test_on_enter_goto_loop_is_detected(self):
        raw = mini_raw()
        raw["scenes"] = [
            {"id": "a", "text": "A", "on_enter": [{"goto": "b"}]},
            {"id": "b", "text": "B", "on_enter": [{"goto": "a"}]},
        ]
        with self.assertRaisesRegex(RuleError, "循环"):
            Engine(parse_story(raw)).start()


if __name__ == "__main__":
    unittest.main()
