"""YHT：剧本静态校验。"""

import unittest

from taleloom.validator import errors, validate
from tests.fixtures import mini_raw, mini_story
from taleloom.loader import parse_story


def messages(story):
    return [str(i) for i in validate(story)]


class ValidatorTest(unittest.TestCase):
    def test_clean_story_has_no_issues(self):
        self.assertEqual(validate(mini_story()), [])

    def test_missing_start_scene(self):
        self.assertTrue(any("起始场景不存在" in m for m in messages(mini_story(start="zzz"))))

    def test_dangling_goto(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["goto"] = "nowhere"
        self.assertTrue(any("跳转目标不存在：nowhere" in m for m in messages(parse_story(raw))))

    def test_unknown_item(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][0]["effects"] = [{"give_item": "ghost"}]
        self.assertTrue(any("物品不存在：ghost" in m for m in messages(parse_story(raw))))

    def test_unknown_condition_hints_at_plugin(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["when"] = {"has_clue": "c1"}
        msgs = messages(parse_story(raw))
        self.assertTrue(any("未知条件：has_clue" in m and "mystery" in m for m in msgs), msgs)

    def test_unknown_mechanic(self):
        self.assertTrue(any("未知的机制插件" in m for m in messages(mini_story(mechanics=["magic"]))))

    def test_story_without_ending_is_error(self):
        raw = mini_raw()
        raw["scenes"][1].pop("ending")
        self.assertTrue(any("没有任何结局" in str(i) for i in errors(validate(parse_story(raw)))))

    def test_unreachable_scene_is_warning(self):
        raw = mini_raw()
        raw["scenes"].append({"id": "island", "text": "孤岛", "choices": [{"text": "回去", "goto": "a"}]})
        issues = [i for i in validate(parse_story(raw)) if "island" in i.path]
        self.assertEqual([i.level for i in issues], ["warning"])

    def test_global_trigger_goto_counts_as_reachable(self):
        raw = mini_raw(triggers=[{"when": {"var": ["hp", "<=", 0]}, "effects": [{"goto": "dead"}]}])
        raw["scenes"].append({"id": "dead", "text": "你倒下了。", "ending": {"id": "dead"}})
        self.assertEqual(validate(parse_story(raw)), [])

    def test_duplicate_choice_id(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["id"] = "take"
        self.assertTrue(any("选项 id 重复" in m for m in messages(parse_story(raw))))


if __name__ == "__main__":
    unittest.main()
