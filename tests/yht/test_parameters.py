"""YHT：条件与效果参数的类型校验。"""

import unittest

from taleloom.loader import parse_story
from taleloom.validator import errors, validate
from tests.fixtures import mini_raw


def issues_for(raw):
    return validate(parse_story(raw))


class ValidParametersTest(unittest.TestCase):
    def test_full_valid_condition_and_effect_set(self):
        raw = mini_raw(
            vars={"hp": 5},
            triggers=[{
                "id": "check",
                "when": {"all": [
                    {"var": ["hp", ">=", 1]},
                    {"not": {"flag": "lost"}},
                    {"any": [{"visited": "a"}, {"has_item": "key"}]},
                ]},
                "effects": [{"say": "检查通过"}],
            }],
        )
        choice = raw["scenes"][0]["choices"][0]
        choice["effects"] = [
            {"set_var": ["hp", 3]},
            {"add_var": ["hp", -1]},
            {"set_flag": "took"},
            {"clear_flag": "lost"},
            {"say": "好"},
        ]
        self.assertEqual(errors(issues_for(raw)), [])

    def test_nested_conditions_are_checked(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["when"] = {
            "all": [{"any": [{"not": {"var": ["hp", "=", 1]}}]}]
        }
        msgs = [str(i) for i in issues_for(raw)]
        self.assertTrue(any("var" in m and "运算符" in m for m in msgs), msgs)


class InvalidParametersTest(unittest.TestCase):
    def assert_parameter_error(self, when=None, effects=None, needle=""):
        raw = mini_raw()
        choice = raw["scenes"][0]["choices"][1]
        if when is not None:
            choice["when"] = when
        if effects is not None:
            choice["effects"] = effects
        issues = issues_for(raw)
        self.assertFalse(any("Traceback" in str(i) for i in issues))
        self.assertTrue(any(needle in str(i) for i in issues), [str(i) for i in issues])

    def test_var_must_be_three_items(self):
        self.assert_parameter_error(when={"var": ["hp", ">="]}, needle="3 项")

    def test_var_name_must_be_non_empty_string(self):
        self.assert_parameter_error(when={"var": ["", ">=", 1]}, needle="变量名")

    def test_var_operator_must_be_known(self):
        self.assert_parameter_error(when={"var": ["hp", "=>", 1]}, needle="运算符")

    def test_var_value_must_be_number(self):
        self.assert_parameter_error(when={"var": ["hp", ">=", "1"]}, needle="数值")

    def test_set_var_requires_two_items(self):
        self.assert_parameter_error(effects=[{"set_var": ["hp"]}], needle="set_var")

    def test_set_var_value_must_be_integer(self):
        self.assert_parameter_error(effects=[{"set_var": ["hp", "3"]}], needle="整数")

    def test_add_var_value_must_be_integer(self):
        self.assert_parameter_error(effects=[{"add_var": ["hp", 1.5]}], needle="整数")

    def test_all_must_be_list(self):
        self.assert_parameter_error(when={"all": {"flag": "x"}}, needle="数组")

    def test_any_item_must_be_condition_object(self):
        self.assert_parameter_error(when={"any": [{"flag": "x"}, "bad"]}, needle="条件对象")

    def test_not_must_be_object(self):
        self.assert_parameter_error(when={"not": ["flag", "x"]}, needle="条件对象")

    def test_string_conditions_reject_numbers(self):
        for key in ("flag", "visited", "has_item"):
            with self.subTest(key=key):
                self.assert_parameter_error(when={key: 1}, needle="字符串")

    def test_string_effects_reject_numbers(self):
        for key in ("set_flag", "clear_flag", "give_item", "take_item", "goto", "say"):
            with self.subTest(key=key):
                self.assert_parameter_error(effects=[{key: 1}], needle="字符串")

    def test_unhashable_argument_does_not_crash(self):
        self.assert_parameter_error(when={"has_item": ["key"]}, needle="字符串")

    def test_parameter_error_points_to_exact_location(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][0]["effects"] = [{"set_var": ["hp", "3"]}]
        issues = issues_for(raw)
        paths = [i.path for i in issues if "set_var" in i.message or "整数" in i.message]
        self.assertIn("scenes.a.choices.take.effects[0]", paths)

    def test_unknown_plugin_parameter_does_not_crash(self):
        raw = mini_raw(mechanics=["mystery"], clues={"c1": {"name": "线索", "text": "内容"}})
        raw["scenes"][0]["choices"][0]["effects"] = [{"add_clue": ["c1"]}]
        issues = issues_for(raw)
        self.assertTrue(issues, "插件参数非法时至少应返回一个问题，而不是崩溃")


class PluginDataParameterTest(unittest.TestCase):
    def test_puzzle_use_condition_and_effect_are_checked(self):
        raw = mini_raw(
            mechanics=["puzzle"],
            uses=[{
                "item": "key", "scene": "a",
                "when": {"var": ["hp", ">="]},
                "effects": [{"set_var": ["hp", "3"]}],
            }],
        )
        issues = issues_for(raw)
        paths = {i.path for i in issues}
        self.assertIn("uses[0].when", paths)
        self.assertIn("uses[0].effects[0]", paths)
        self.assertTrue(any("3 项" in i.message for i in issues))
        self.assertTrue(any("整数" in i.message for i in issues))

    def test_accusation_conditions_are_checked(self):
        raw = mini_raw(
            mechanics=["mystery"],
            clues={"c1": {"name": "线索", "text": "内容"}},
            accusation={
                "when": {"var": ["hp", ">="]},
                "suspects": {"gu": {"name": "顾"}},
                "outcomes": [{"suspect": "gu", "when": {"has_item": "ghost"}, "goto": "b"}],
                "default": "b",
            },
        )
        issues = issues_for(raw)
        self.assertIn("accusation.when", {i.path for i in issues})
        self.assertIn("accusation.outcomes[0].when", {i.path for i in issues})
        self.assertTrue(any("物品不存在：ghost" in i.message for i in issues))

    def test_puzzle_goto_in_effects_must_exist(self):
        raw = mini_raw(
            mechanics=["puzzle"],
            uses=[{"item": "key", "scene": "a", "effects": [{"goto": "nowhere"}]}],
        )
        self.assertTrue(any("跳转目标不存在：nowhere" in str(i) for i in issues_for(raw)))

    def test_malformed_plugin_condition_does_not_crash(self):
        raw = mini_raw(
            mechanics=["mystery"],
            clues={"c1": {"name": "线索", "text": "内容"}},
            accusation={
                "when": "not-an-object",
                "suspects": {"gu": {"name": "顾"}},
                "outcomes": [],
                "default": "b",
            },
        )
        issues = issues_for(raw)
        self.assertIsInstance(issues, list)
        self.assertTrue(any("mystery" in str(i) for i in issues))


class ReferenceTest(unittest.TestCase):
    def test_visited_scene_must_exist(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["when"] = {"visited": "nowhere"}
        self.assertTrue(any("场景不存在：nowhere" in str(i) for i in issues_for(raw)))


if __name__ == "__main__":
    unittest.main()
