"""ZRS：道具插件——把道具用在某处、候选说明、校验与图形动作。"""

import unittest

from taleloom.engine import Engine
from taleloom.loader import parse_story
from taleloom.mechanics.puzzle import available_targets, build_actions, resolve_target
from taleloom.model import Command
from taleloom.ui_contract import DisplayItem
from taleloom.validator import errors, validate
from tests.fixtures import mini_raw


def puzzle_story(**extra):
    raw = mini_raw(
        mechanics=["puzzle"],
        items=[
            {"id": "rod", "name": "木棍"},
            {"id": "hook", "name": "铁钩"},
            {"id": "pole", "name": "钩竿", "aliases": ["竿"]},
            {"id": "key", "name": "钥匙"},
            {"id": "lamp", "name": "提灯", "description": "还能亮的提灯。"},
        ],
        targets=[{"id": "panel", "name": "控制面板", "aliases": ["面板"], "scene": "a"},
                 {"id": "wall", "name": "砖墙", "description": "一面旧砖墙。"}],
        combinations=[{"items": ["rod", "hook"], "result": "pole", "message": "你把铁钩绑在木棍上。"}],
        uses=[
            {"item": "pole", "scene": "a", "effects": [{"give_item": "key"}],
             "message": "你钩到了钥匙。", "consume": True},
            {"item": "lamp", "target": "wall", "effects": [{"set_flag": "lit"}],
             "message": "你举起提灯照亮砖墙。"},
        ],
    )
    raw["scenes"][0]["choices"] = [
        {"id": "search", "text": "翻找", "once": True,
         "effects": [{"give_item": "rod"}, {"give_item": "hook"}, {"give_item": "lamp"}]},
        {"id": "open", "text": "开门", "goto": "b", "when": {"has_item": "key"}},
    ]
    raw.update(extra)
    return parse_story(raw)


class UseOnTest(unittest.TestCase):
    def setUp(self):
        self.story = puzzle_story()
        self.engine = Engine(self.story)
        self.engine.start()
        self.engine.handle(Command("choose", ["1"], "choose 1"))

    def run_cmd(self, verb, *args):
        return self.engine.handle(Command(verb, list(args), " ".join((verb,) + args)))

    def test_use_on_target_matches_declared_target(self):
        out = self.run_cmd("use_on", "lamp", "wall")
        self.assertIn("你举起提灯照亮砖墙。", out.lines)
        self.assertIn("lit", self.engine.state.flags)

    def test_use_on_uses_alias_and_is_case_insensitive(self):
        story = puzzle_story(targets=[{"id": "wall", "name": "砖墙", "aliases": ["BrickWall"],
                                      "description": "一面旧砖墙。"}])
        engine = Engine(story)
        engine.start()
        engine.handle(Command("choose", ["1"], "choose 1"))
        out = engine.handle(Command("use_on", ["lamp", "brickwall"], "use_on"))
        self.assertIn("照亮砖墙", "\n".join(out.lines))

    def test_use_on_unknown_target_does_not_advance(self):
        turn = self.engine.state.turn
        out = self.run_cmd("use_on", "lamp", "天花板")
        self.assertIn("这里没有可以这样用“天花板”的东西。", out.lines)
        self.assertEqual(self.engine.state.turn, turn)

    def test_use_on_rejects_item_not_in_inventory(self):
        out = self.run_cmd("use_on", "竿", "wall")
        self.assertIn("你身上没有“竿”。", out.lines)

    def test_use_on_more_than_two_arguments_is_rejected(self):
        self.assertIn("一次只能", self.run_cmd("use_on", "提灯", "砖墙", "窗户").lines[0])

    def test_scene_scoped_target_is_not_usable_elsewhere(self):
        engine = Engine(puzzle_story(targets=[{"id": "panel", "name": "控制面板", "scene": "b"},
                                              {"id": "wall", "name": "砖墙"}]))
        engine.start()
        engine.handle(Command("choose", ["1"], "choose 1"))
        self.assertIsNone(resolve_target(engine.story, "控制面板", "a"))
        self.assertEqual(resolve_target(engine.story, "控制面板", "b"), "panel")

    def test_plain_use_still_matches_scene_rules(self):
        self.run_cmd("combine", "木棍", "铁钩")
        out = self.run_cmd("use", "竿")
        self.assertIn("你钩到了钥匙。", out.lines)

    def test_target_rule_without_target_argument_does_not_fire(self):
        out = self.run_cmd("use", "提灯")
        self.assertIn("这里用不上它。", out.lines)


class PuzzleActionsTest(unittest.TestCase):
    def test_actions_expose_inventory_and_scene_targets_only(self):
        story = puzzle_story(targets=[
            {"id": "panel", "name": "控制面板", "scene": "a"},
            {"id": "hatch", "name": "舱门", "scene": "b"},
        ])
        engine = Engine(story)
        engine.start()
        state = engine.state
        inventory = [DisplayItem("lamp", "提灯", "还能亮的提灯。")]
        actions = build_actions(story, state, inventory)
        self.assertEqual([a.id for a in actions], ["puzzle:use", "puzzle:use_on"])
        use_on = actions[1]
        self.assertEqual([p.key for p in use_on.parameters], ["item", "target"])
        self.assertEqual([o.id for o in use_on.parameters[1].options], ["panel"])
        self.assertEqual(use_on.parameters[0].options[0].description, "还能亮的提灯。")

    def test_combine_requires_two_items_and_pending_target(self):
        story = puzzle_story()
        engine = Engine(story)
        engine.start()
        state = engine.state
        self.assertEqual(build_actions(story, state, []), [])
        single = build_actions(story, state, [DisplayItem("lamp", "提灯")])
        self.assertEqual([a.id for a in single], ["puzzle:use", "puzzle:use_on"])
        pair = build_actions(story, state, [DisplayItem("lamp", "提灯"), DisplayItem("rod", "木棍")])
        self.assertIn("puzzle:combine", [a.id for a in pair])

    def test_actions_disappear_after_ending(self):
        story = puzzle_story()
        engine = Engine(story)
        engine.start()
        engine.state.ending = "out"
        inventory = [DisplayItem("lamp", "提灯")]
        self.assertEqual(build_actions(story, engine.state, inventory), [])

    def test_unscoped_target_appears_in_every_scene(self):
        story = puzzle_story()
        ids = {target["id"] for scene in ("a", "b") for target in available_targets(story, scene)}
        self.assertEqual(sorted(ids), ["panel", "wall"])


class TargetValidationTest(unittest.TestCase):
    def test_unknown_use_target_is_reported(self):
        story = puzzle_story(uses=[{"item": "lamp", "target": "ceiling", "effects": []}])
        self.assertTrue(any("目标不存在：ceiling" in i.message for i in validate(story)))

    def test_target_with_unknown_scene_is_reported(self):
        story = puzzle_story(targets=[{"id": "wall", "name": "砖墙", "scene": "ghost"}])
        self.assertTrue(any("场景不存在：ghost" in i.message for i in validate(story)))

    def test_duplicate_and_bad_target_ids_are_reported(self):
        story = puzzle_story(targets=[{"id": "wall", "name": "砖墙"}, {"id": "wall", "name": "墙"},
                                      {"name": "无名"}])
        messages = [i.message for i in validate(story)]
        self.assertIn("目标 id 重复：wall", messages)
        self.assertIn("目标 id 应为非空字符串", messages)

    def test_valid_target_data_has_no_errors(self):
        self.assertEqual(errors(validate(puzzle_story())), [])

    def test_targets_does_not_hide_unused_item_warning(self):
        story = puzzle_story(targets=[{"id": "wall", "name": "砖墙"}],
                             uses=[{"item": "lamp", "target": "wall", "effects": []}])
        self.assertEqual(errors(validate(story)), [])


if __name__ == "__main__":
    unittest.main()
