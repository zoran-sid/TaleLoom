"""ZC：推理插件的深入搜证、审问、分幕与带理由的指认。

只使用测试内构造的迷你剧本，不读取 stories/。
"""

import copy
import unittest

from taleloom.engine import Engine
from taleloom.loader import parse_story
from taleloom.mechanics.mystery import accusation_targets, action_values, build_actions
from taleloom.model import Command
from taleloom.validator import errors, validate
from tests.fixtures import mini_raw


def deep_raw():
    """一位管家、一位女仆、三条线索、两幕、三个结局的推理小剧本。"""
    raw = mini_raw(
        mechanics=["mystery"],
        items=[{"id": "lens", "name": "放大镜"}],
        clues={
            "letter": {
                "name": "信", "text": "约在午夜。",
                "examine": {
                    "when": {"has_item": "lens"},
                    "hint": "字太小了，需要放大镜。",
                    "text": "落款处有一个淡淡的“周”字。",
                    "effects": [{"add_clue": "seal"}],
                },
            },
            "seal": {"name": "落款", "text": "信末的“周”字。"},
            "knife": {"name": "刀", "text": "带血。"},
        },
        acts=[
            {"id": "night", "title": "第一幕 · 夜"},
            {"id": "dawn", "title": "第二幕 · 天亮", "text": "天亮了，警察到了。"},
        ],
        triggers=[{"id": "to_dawn", "when": {"clues_found": 3}, "effects": [{"start_act": "dawn"}]}],
        accusation={
            "when": {"visited": "a"},
            "suspects": {
                "butler": {"name": "管家", "aliases": ["老周"], "topics": [
                    {"id": "night", "name": "昨晚的行踪", "text": "我一直在酒窖。",
                     "effects": [{"set_flag": "butler_lied"}]},
                    {"id": "letter", "clue": "letter", "text": "这……这不是我写的！"},
                    {"id": "dawn", "name": "天亮后的去向", "when": {"act": "dawn"}, "text": "我去报了警。"},
                ]},
                "maid": {"name": "女仆", "scenes": ["b"], "topics": [
                    {"id": "night", "name": "昨晚", "text": "我早早睡了。"},
                ]},
            },
            "reasons": [
                {"id": "motive", "label": "动机", "options": [
                    {"id": "money", "name": "钱", "aliases": ["遗产"]},
                    {"id": "love", "name": "情", "when": {"flag": "butler_lied"}},
                ]},
                {"id": "evidence", "label": "关键证据", "from": "clues"},
            ],
            "outcomes": [
                {"suspect": "butler", "reasons": {"motive": "money", "evidence": ["seal", "knife"]}, "goto": "good"},
                {"suspect": "butler", "reasons": {"motive": "money", "evidence": "seal"},
                 "min_correct": 1, "goto": "half"},
            ],
            "default": "bad",
        },
    )
    raw["scenes"] = [
        {"id": "a", "text": "书房。", "choices": [
            {"id": "lens", "text": "拿起放大镜", "once": True, "effects": [{"give_item": "lens"}]},
            {"id": "desk", "text": "看书桌", "once": True, "effects": [{"add_clue": "letter"}]},
            {"id": "pot", "text": "翻花盆", "once": True, "effects": [{"add_clue": "knife"}]},
            {"id": "yard", "text": "去后院", "goto": "b"},
        ]},
        {"id": "b", "text": "后院。", "choices": [{"id": "back", "text": "回书房", "goto": "a"}]},
        {"id": "good", "text": "破案。", "ending": {"id": "good"}},
        {"id": "half", "text": "半真相。", "ending": {"id": "half"}},
        {"id": "bad", "text": "冤案。", "ending": {"id": "bad"}},
    ]
    return raw


class Play:
    """直接驱动 Engine 的小助手：返回输出文字，便于断言。"""

    def __init__(self, raw=None):
        self.story = parse_story(raw or deep_raw())
        self.engine = Engine(self.story)
        self.engine.start()

    def __call__(self, verb, *args):
        return self.engine.handle(Command(verb, list(args), " ".join((verb,) + args)))

    def text(self, verb, *args):
        return "\n".join(self(verb, *args).lines)

    @property
    def state(self):
        return self.engine.state

    def clues(self):
        return self.state.ext.get("mystery", {}).get("clues", [])


class ExamineTest(unittest.TestCase):
    def test_examine_needs_condition_and_shows_hint_without_turn(self):
        play = Play()
        play("choose", "desk")
        turn = play.state.turn
        self.assertIn("需要放大镜", play.text("examine", "信"))
        self.assertEqual(play.state.turn, turn)
        self.assertNotIn("seal", play.clues())

    def test_examine_reveals_next_clue_and_consumes_turn(self):
        play = Play()
        play("choose", "lens")
        play("choose", "desk")
        turn = play.state.turn
        text = play.text("examine", "letter")
        self.assertIn("淡淡的“周”字", text)
        self.assertIn("【获得线索】落款", text)
        self.assertEqual(play.state.turn, turn + 1)

    def test_examine_twice_does_not_repeat_effects(self):
        play = Play()
        play("choose", "lens")
        play("choose", "desk")
        play("examine", "信")
        turn = play.state.turn
        self.assertIn("已经仔细查看过", play.text("examine", "信"))
        self.assertEqual(play.state.turn, turn)

    def test_examine_unknown_or_unfound_clue_is_a_message(self):
        play = Play()
        self.assertIn("笔记里没有“信”", play.text("examine", "信"))
        self.assertIn("要深入调查哪条线索", play.text("examine"))
        play("choose", "pot")
        self.assertIn("看不出更多", play.text("examine", "刀"))
        self.assertEqual(play.state.turn, 1)


class InterrogationTest(unittest.TestCase):
    def test_first_question_applies_effects_and_consumes_turn(self):
        play = Play()
        text = play.text("ask", "管家", "昨晚的行踪")
        self.assertIn("我一直在酒窖。", text)
        self.assertIn("butler_lied", play.state.flags)
        self.assertEqual(play.state.turn, 1)

    def test_repeat_question_rereads_without_turn(self):
        play = Play()
        play("ask", "老周", "昨晚的行踪")
        self.assertIn("我一直在酒窖。", play.text("ask", "butler/night"))
        self.assertEqual(play.state.turn, 1)

    def test_presenting_a_clue_needs_the_clue(self):
        play = Play()
        self.assertIn("没什么可说", play.text("ask", "管家", "信"))
        play("choose", "desk")
        self.assertIn("这不是我写的", play.text("ask", "管家", "信"))

    def test_only_suspect_lists_available_topics(self):
        play = Play()
        text = play.text("ask", "管家")
        self.assertIn("昨晚的行踪", text)
        self.assertNotIn("天亮后的去向", text)

    def test_suspect_must_be_present_in_scene(self):
        play = Play()
        self.assertIn("女仆不在这里", play.text("ask", "女仆", "昨晚"))
        play("choose", "yard")
        self.assertIn("我早早睡了。", play.text("ask", "女仆", "昨晚"))

    def test_unknown_suspect_and_missing_args(self):
        play = Play()
        self.assertIn("要审问谁", play.text("ask"))
        self.assertIn("没有叫“园丁”的人", play.text("ask", "园丁", "昨晚"))
        self.assertEqual(play.state.turn, 0)


class ActsTest(unittest.TestCase):
    def test_trigger_starts_next_act_with_interlude(self):
        play = Play()
        play("choose", "lens")
        play("choose", "desk")
        self.assertNotIn("天亮后的去向", play.text("ask", "管家"))
        text = play.text("choose", "pot")  # 第 2 条线索
        self.assertNotIn("第二幕", text)
        text = play.text("examine", "信")  # 第 3 条线索，回合结束时触发
        self.assertIn("—— 第二幕 · 天亮 ——", text)
        self.assertIn("天亮了，警察到了。", text)
        self.assertIn("我去报了警。", play.text("ask", "管家", "天亮后的去向"))

    def test_start_act_never_goes_back(self):
        raw = deep_raw()
        raw["scenes"][0]["choices"].append(
            {"id": "rewind", "text": "倒回", "effects": [{"start_act": "dawn"}, {"start_act": "night"}]})
        play = Play(raw)
        text = play.text("choose", "rewind")
        self.assertEqual(text.count("——"), 2)  # 只有“第二幕”标题一行
        self.assertEqual(play.state.ext["mystery"]["act"], "dawn")


class AccusationReasonsTest(unittest.TestCase):
    def ready(self):
        play = Play()
        for choice in ("lens", "desk", "pot"):
            play("choose", choice)
        play("examine", "信")
        return play

    def test_all_reasons_right_reaches_best_ending(self):
        play = self.ready()
        out = play("accuse", "管家", "钱", "刀")
        self.assertEqual(out.ending, "good")
        self.assertIn("动机：钱", "\n".join(out.lines))

    def test_reasons_accept_ids_and_aliases(self):
        self.assertEqual(self.ready()("accuse", "butler", "遗产", "seal").ending, "good")

    def test_partly_right_reasons_reach_lower_tier(self):
        self.assertEqual(self.ready()("accuse", "管家", "钱", "信").ending, "half")

    def test_wrong_suspect_goes_to_default(self):
        self.assertEqual(self.ready()("accuse", "女仆", "钱", "刀").ending, "bad")

    def test_missing_reasons_prompt_without_ending(self):
        play = self.ready()
        out = play("accuse", "管家")
        self.assertFalse(out.ended)
        text = "\n".join(out.lines)
        self.assertIn("请说明理由", text)
        self.assertIn("钱", text)

    def test_unknown_or_locked_reason_is_rejected(self):
        play = self.ready()
        self.assertIn("“情”不是可选的动机", play.text("accuse", "管家", "情", "刀"))
        self.assertIn("“账本”不是可选的关键证据", play.text("accuse", "管家", "钱", "账本"))
        self.assertFalse(play.state.ending)
        play("ask", "管家", "昨晚的行踪")
        self.assertEqual(play("accuse", "管家", "情", "刀").ending, "bad")


class ReadOnlyQueriesTest(unittest.TestCase):
    def test_has_clue_check_does_not_create_plugin_state(self):
        play = Play()
        before = copy.deepcopy(play.state.to_dict())
        play.engine.registry.check(play.engine._ctx(), {"has_clue": "letter"})
        play.engine.registry.check(play.engine._ctx(), {"clues_found": 1})
        play.engine.registry.check(play.engine._ctx(), {"act": "dawn"})
        self.assertEqual(play.state.to_dict(), before)


class BuildActionsTest(unittest.TestCase):
    def actions(self, play):
        return {a.id: a for a in build_actions(play.story, play.state, play.engine.registry)}

    def test_actions_offer_only_known_and_available_options(self):
        play = Play()
        actions = self.actions(play)
        self.assertNotIn("mystery:examine", actions)
        ask = actions["mystery:ask"].parameters[0]
        self.assertEqual([o.id for o in ask.options], ["butler/night"])
        self.assertIn("管家", ask.options[0].label)
        accuse = actions["mystery:accuse"]
        self.assertEqual([p.key for p in accuse.parameters], ["suspect", "motive", "evidence"])
        self.assertEqual([o.id for o in accuse.parameters[1].options], ["money"])
        self.assertEqual(accuse.parameters[2].options, [])

    def test_examine_and_present_appear_after_finding_clues(self):
        play = Play()
        play("choose", "desk")
        actions = self.actions(play)
        self.assertEqual([o.id for o in actions["mystery:examine"].parameters[0].options], ["letter"])
        topics = [o.id for o in actions["mystery:ask"].parameters[0].options]
        self.assertEqual(topics, ["butler/night", "butler/letter"])
        self.assertEqual([o.id for o in actions["mystery:accuse"].parameters[2].options], ["letter"])

    def test_examined_clue_leaves_examine_options(self):
        play = Play()
        play("choose", "lens")
        play("choose", "desk")
        play("examine", "信")
        self.assertNotIn("mystery:examine", self.actions(play))

    def test_building_actions_is_read_only(self):
        play = Play()
        play("choose", "desk")
        before = copy.deepcopy(play.state.to_dict())
        build_actions(play.story, play.state, play.engine.registry)
        self.assertEqual(play.state.to_dict(), before)

    def test_no_actions_after_ending(self):
        play = Play()
        play("choose", "pot")
        play("accuse", "女仆", "钱", "刀")
        self.assertEqual(play.state.ending, "bad")
        self.assertEqual(self.actions(play), {})


class ActionValuesTest(unittest.TestCase):
    def values(self, play, verb, *args):
        return action_values(play.story, play.state, play.engine.registry, Command(verb, list(args)))

    def test_text_commands_map_to_action_values(self):
        play = Play()
        play("choose", "desk")
        play("choose", "pot")
        self.assertEqual(self.values(play, "examine", "信"), {"clue": "letter"})
        self.assertEqual(self.values(play, "ask", "老周", "信"), {"topic": "butler/letter"})
        self.assertEqual(self.values(play, "ask", "butler/night"), {"topic": "butler/night"})
        self.assertEqual(self.values(play, "accuse", "管家", "遗产", "刀"),
                         {"suspect": "butler", "motive": "money", "evidence": "knife"})

    def test_unmappable_commands_return_none(self):
        play = Play()
        self.assertIsNone(self.values(play, "examine", "信"))
        self.assertIsNone(self.values(play, "ask", "管家", "信"))
        self.assertIsNone(self.values(play, "accuse", "管家"))
        self.assertIsNone(self.values(play, "clues"))


class ValidateDeepTest(unittest.TestCase):
    def issues(self, raw):
        return [str(i) for i in validate(parse_story(raw))]

    def test_clean_deep_story_has_no_issues(self):
        self.assertEqual(self.issues(deep_raw()), [])

    def test_reports_bad_references_in_plugin_data(self):
        raw = deep_raw()
        raw["clues"]["letter"]["examine"]["effects"] = [{"add_clue": "ghost"}]
        raw["accusation"]["suspects"]["butler"]["topics"][1]["clue"] = "phantom"
        raw["accusation"]["suspects"]["maid"]["scenes"] = ["nowhere"]
        raw["triggers"][0]["effects"] = [{"start_act": "noon"}]
        raw["accusation"]["outcomes"][0]["reasons"]["motive"] = "revenge"
        raw["accusation"]["outcomes"][1]["reasons"]["weapon"] = "knife"
        msgs = self.issues(raw)
        for expected in ("线索不存在：ghost", "线索不存在：phantom", "场景不存在：nowhere",
                         "幕不存在：noon", "选项不存在：revenge", "理由不存在：weapon"):
            self.assertTrue(any(expected in m for m in msgs), (expected, msgs))

    def test_reports_unknown_condition_and_effect_names(self):
        raw = deep_raw()
        raw["accusation"]["suspects"]["butler"]["topics"][0]["when"] = {"mood": "angry"}
        raw["clues"]["letter"]["examine"]["effects"] = [{"explode": True}]
        msgs = self.issues(raw)
        self.assertTrue(any("未知条件：mood" in m for m in msgs), msgs)
        self.assertTrue(any("未知效果：explode" in m for m in msgs), msgs)

    def test_reports_duplicate_and_malformed_ids(self):
        raw = deep_raw()
        raw["accusation"]["suspects"]["butler"]["topics"][1]["id"] = "night"
        raw["accusation"]["suspects"]["a/b"] = {"name": "斜杠"}
        raw["acts"].append({"id": "night", "title": "重复"})
        raw["accusation"]["reasons"][0]["id"] = "suspect"
        msgs = self.issues(raw)
        for expected in ("话题 id 重复：night", "嫌疑人 id 不能包含“/”", "幕 id 重复：night",
                         "理由 id 不能是 suspect"):
            self.assertTrue(any(expected in m for m in msgs), (expected, msgs))

    def test_malformed_plugin_data_is_reported_not_crash(self):
        raw = deep_raw()
        raw["accusation"]["suspects"]["butler"]["topics"] = "oops"
        raw["clues"]["letter"]["examine"] = ["bad"]
        raw["acts"] = {"id": "x"}
        raw["accusation"]["reasons"] = [{"id": "motive", "options": "bad"}]
        msgs = [str(i) for i in errors(validate(parse_story(raw)))]
        self.assertTrue(msgs)
        self.assertFalse(any("校验数据时出错" in m for m in msgs), msgs)

    def test_goto_inside_topics_counts_as_reachable(self):
        raw = deep_raw()
        raw["scenes"].append({"id": "confess", "text": "他招了。", "ending": {"id": "confess"}})
        raw["accusation"]["suspects"]["butler"]["topics"][0]["effects"] = [{"goto": "confess"}]
        self.assertIn("confess", accusation_targets(parse_story(raw)))
        self.assertEqual(self.issues(raw), [])

    def test_topic_goto_moves_to_scene(self):
        raw = deep_raw()
        raw["scenes"].append({"id": "confess", "text": "他招了。", "ending": {"id": "confess"}})
        raw["accusation"]["suspects"]["butler"]["topics"][0]["effects"] = [{"goto": "confess"}]
        play = Play(raw)
        self.assertEqual(play("ask", "管家", "昨晚的行踪").ending, "confess")


if __name__ == "__main__":
    unittest.main()
