"""YHT：结构性检查（死路、陷阱环、一次性出口、未使用物品）。"""

import unittest

from taleloom.loader import parse_story
from taleloom.validator import errors, validate
from tests.fixtures import mini_raw


def check(raw):
    return validate(parse_story(raw))


def has(issues, needle):
    return any(needle in str(i) for i in issues)


class DeadEndTest(unittest.TestCase):
    def test_non_ending_scene_without_exit_is_error(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"] = [raw["scenes"][0]["choices"][0]]   # 只剩 take
        issues = check(raw)
        self.assertTrue(has(issues, "没有任何出口"), [str(i) for i in issues])
        self.assertTrue(any(i.level == "error" and "没有任何出口" in i.message for i in issues))

    def test_ending_scene_may_have_no_exit(self):
        raw = mini_raw()
        raw["scenes"][1]["choices"] = []
        self.assertEqual(errors(check(raw)), [])


class TrapLoopTest(unittest.TestCase):
    def test_loop_with_exit_is_clean(self):
        raw = mini_raw(items=[], scenes=[
            {"id": "a", "text": "A", "choices": [{"id": "go", "text": "去 B", "goto": "b"}]},
            {"id": "b", "text": "B", "choices": [
                {"id": "back", "text": "回 A", "goto": "a"},
                {"id": "leave", "text": "离开", "goto": "end"},
            ]},
            {"id": "end", "text": "结束", "ending": {"id": "e"}},
        ])
        self.assertEqual(check(raw), [])

    def test_two_scene_trap_is_error(self):
        raw = mini_raw(items=[], scenes=[
            {"id": "a", "text": "A", "choices": [{"id": "go", "text": "去 B", "goto": "b"}]},
            {"id": "b", "text": "B", "choices": [{"id": "back", "text": "回 A", "goto": "a"}]},
            {"id": "end", "text": "不可达的结局", "ending": {"id": "e"}},
        ])
        issues = check(raw)
        self.assertTrue(has(issues, "陷阱环"), [str(i) for i in issues])
        self.assertTrue(has(issues, "a、b") or has(issues, "b、a"))

    def test_self_loop_is_trap(self):
        raw = mini_raw(items=[], scenes=[
            {"id": "a", "text": "A", "choices": [{"id": "stay", "text": "原地", "goto": "a"}]},
            {"id": "end", "text": "结束", "ending": {"id": "e"}},
        ])
        self.assertTrue(has(check(raw), "陷阱环"))


class OnceChoiceTest(unittest.TestCase):
    def make_story(self, once=True):
        return mini_raw(items=[], scenes=[
            {"id": "a", "text": "A", "choices": [
                {"id": "go", "text": "去 B", "once": once, "goto": "b"},
            ]},
            {"id": "b", "text": "B", "choices": [
                {"id": "back", "text": "回 A", "goto": "a"},
                {"id": "leave", "text": "离开", "goto": "end"},
            ]},
            {"id": "end", "text": "结束", "ending": {"id": "e"}},
        ])

    def test_all_exits_once_and_scene_is_reenterable(self):
        issues = check(self.make_story(once=True))
        self.assertTrue(has(issues, "一次性"), [str(i) for i in issues])
        self.assertTrue(has(issues, "再次进入"))

    def test_normal_exit_prevents_exhaustion(self):
        self.assertFalse(has(check(self.make_story(once=False)), "一次性"))

    def test_global_exit_suppresses_exhaustion(self):
        raw = self.make_story(once=True)
        raw["triggers"] = [{"id": "timeout", "when": {"flag": "never"}, "effects": [{"goto": "end"}]}]
        self.assertFalse(has(check(raw), "一次性"))


class UnusedItemTest(unittest.TestCase):
    def test_unused_item_is_warning(self):
        raw = mini_raw(items=[
            {"id": "key", "name": "钥匙"},
            {"id": "ghost", "name": "幽灵"},
        ])
        issues = check(raw)
        ghost = [i for i in issues if i.path == "items.ghost"]
        self.assertEqual([i.level for i in ghost], ["warning"])
        self.assertFalse(errors(issues))

    def test_used_item_is_not_reported(self):
        issues = check(mini_raw())
        self.assertFalse(any(i.path == "items.key" for i in issues))

    def test_story_without_item_usage_is_quiet(self):
        raw = mini_raw(items=[{"id": "key", "name": "钥匙"}], scenes=[
            {"id": "a", "text": "A", "choices": [{"id": "go", "text": "去 B", "goto": "b"}]},
            {"id": "b", "text": "B", "ending": {"id": "e"}},
        ])
        self.assertFalse(any(i.path == "items.key" for i in check(raw)))

    def test_plugin_reference_counts_as_used(self):
        raw = mini_raw(
            items=[{"id": "key", "name": "钥匙"}, {"id": "rod", "name": "铁棒"}],
            mechanics=["puzzle"],
            uses=[{"item": "rod", "scene": "a"}],
        )
        self.assertFalse(any(i.path == "items.rod" for i in check(raw)))


if __name__ == "__main__":
    unittest.main()
