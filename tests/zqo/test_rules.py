"""ZQO：条件与效果解释器、游戏状态。"""

import unittest

from taleloom.rules import Context, RuleError, default_registry
from taleloom.state import GameState
from tests.fixtures import mini_story


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.reg = default_registry()
        self.ctx = Context(story=mini_story(), state=GameState(story_id="mini", scene="a"))

    def test_empty_condition_is_true(self):
        self.assertTrue(self.reg.check(self.ctx, None))
        self.assertTrue(self.reg.check(self.ctx, {}))

    def test_flag_and_logic(self):
        self.ctx.state.set_flag("lit")
        self.assertTrue(self.reg.check(self.ctx, {"flag": "lit"}))
        self.assertFalse(self.reg.check(self.ctx, {"not": {"flag": "lit"}}))
        self.assertTrue(self.reg.check(self.ctx, {"any": [{"flag": "x"}, {"flag": "lit"}]}))
        self.assertFalse(self.reg.check(self.ctx, {"all": [{"flag": "x"}, {"flag": "lit"}]}))

    def test_multiple_keys_mean_all(self):
        self.ctx.state.set_flag("lit")
        self.assertFalse(self.reg.check(self.ctx, {"flag": "lit", "has_item": "key"}))

    def test_var_comparisons_and_default_zero(self):
        self.reg.apply(self.ctx, [{"set_var": ["hp", 3]}, {"add_var": ["hp", -1]}])
        self.assertEqual(self.ctx.state.vars["hp"], 2)
        for op, value, expected in [("==", 2, True), ("<", 2, False), ("<=", 2, True), (">", 1, True), ("!=", 2, False)]:
            with self.subTest(op=op):
                self.assertEqual(self.reg.check(self.ctx, {"var": ["hp", op, value]}), expected)
        self.assertTrue(self.reg.check(self.ctx, {"var": ["unset", "==", 0]}))

    def test_bad_operator(self):
        with self.assertRaises(RuleError):
            self.reg.check(self.ctx, {"var": ["hp", "=~", 1]})

    def test_items_and_messages(self):
        self.reg.apply(self.ctx, [{"give_item": "key"}, {"give_item": "key"}])
        self.assertEqual(self.ctx.state.inventory, ["key"])
        self.assertIn("【获得物品】钥匙", self.ctx.lines)
        self.reg.apply(self.ctx, [{"take_item": "key"}])
        self.assertEqual(self.ctx.state.inventory, [])

    def test_goto_effect_sets_pending_move(self):
        self.reg.apply(self.ctx, [{"goto": "b"}])
        self.assertEqual(self.ctx.goto, "b")

    def test_unknown_keys_raise(self):
        with self.assertRaisesRegex(RuleError, "未知条件"):
            self.reg.check(self.ctx, {"nope": 1})
        with self.assertRaisesRegex(RuleError, "未知效果"):
            self.reg.apply(self.ctx, [{"nope": 1}])

    def test_duplicate_registration_rejected(self):
        with self.assertRaises(RuleError):
            self.reg.register_condition("flag", lambda ctx, a: True)


class StateTest(unittest.TestCase):
    def test_roundtrip(self):
        s = GameState(story_id="x", scene="a", vars={"o": 3})
        s.set_flag("f")
        s.plugin("mystery")["clues"] = ["c1"]
        self.assertEqual(GameState.from_dict(s.to_dict()), s)

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            GameState.from_dict({"story_id": "x", "scene": "a", "hp": 1})


if __name__ == "__main__":
    unittest.main()
