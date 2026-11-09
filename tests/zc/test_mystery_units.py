"""ZC：调查单元——观察点、由 Python 判定的核对、分层提示与存档恢复。

使用测试内的迷你剧本，不读取 stories/。
"""

import copy
import unittest

from taleloom.engine import Engine
from taleloom.loader import parse_story
from taleloom.mechanics.mystery import action_values
from taleloom.model import Command
from taleloom.save import decode_save, encode_save
from taleloom.session import GameSession
from taleloom.ui_contract import ActionRequest
from taleloom.validator import validate


def unit_raw():
    """一张账桌：两处观察点，两栏摘录要分开记，第三栏可以弱答后确认保留。"""
    return {
        "format_version": 1, "id": "ledger_desk", "title": "账桌", "start": "desk",
        "mechanics": ["mystery"],
        "clues": {
            "front": {"name": "正面窄边", "text": "顾、叁佰。"},
            "back": {"name": "纸背浅字", "text": "供货汇记，五百八十四。"},
            "split": {"name": "两笔分记", "text": "300 欠据与 584 汇记属于两笔账。"},
            "weak": {"name": "只记了印象", "text": "动机只写了“他很紧张”。"},
        },
        "units": {
            "lamp": {
                "name": "灯下残页",
                "scenes": ["desk"],
                "spots": [
                    {"id": "front", "name": "正面窄边", "text": "窄边上读得出“顾”“叁佰”。",
                     "effects": [{"add_clue": "front"}]},
                    {"id": "back", "name": "灯侧照纸背", "text": "纸背有“供货汇记”和“五百八十四”。",
                     "effects": [{"add_clue": "back"}]},
                ],
                "slots": [
                    {"id": "front", "label": "正面记作", "options": [
                        {"id": "debt", "name": "顾的欠据 300"},
                        {"id": "supply", "name": "供货汇记 584"}]},
                    {"id": "back", "label": "背面记作", "options": [
                        {"id": "debt", "name": "顾的欠据 300"},
                        {"id": "supply", "name": "供货汇记 584"},
                        {"id": "secret", "name": "只有知情人才看得到", "when": {"has_clue": "weak"}}]},
                ],
                "distinct": True,
                "solutions": [{"answer": {"front": "debt", "back": "supply"}, "text": "两面分开记下。",
                               "effects": [{"add_clue": "split"}]}],
                "feedback": [{"answer": {"front": "supply"}, "text": "正面的字是“顾”和“叁佰”。"}],
                "duplicate": "两面标题不同，先核对它们分别属于哪笔账。",
                "fallback": "再对照一下两面的标题。",
                "hints": ["先看正面窄边和纸背。", "比较两面的标题。", "正面记欠据，背面记供货。"],
            },
            "motive": {
                "name": "为什么是今晚",
                "scenes": ["desk"],
                "when": {"has_clue": "split"},
                "slots": [{"id": "why", "label": "依据", "options": [
                    {"id": "deadline", "name": "明早交割"}, {"id": "nervous", "name": "他很紧张"}]}],
                "solutions": [
                    {"answer": {"why": "deadline"}, "grade": "full", "text": "期限落在同一晚。"},
                    {"answer": {"why": "nervous"}, "grade": "weak", "confirm": "紧张不是当夜冲突的依据。仍要这样写吗？",
                     "text": "你保留了原判断。", "effects": [{"add_clue": "weak"}]},
                ],
            },
        },
        "scenes": [
            {"id": "desk", "title": "账房", "text": "灯下一张残页。", "choices": [
                {"id": "leave", "text": "离开", "goto": "hall", "when": {"solved": "lamp"}}]},
            {"id": "hall", "title": "大堂", "text": "雾还没散。", "choices": [
                {"id": "out", "text": "出门", "goto": "out"}]},
            {"id": "out", "title": "门外", "text": "天亮了。", "ending": {"id": "end"}},
        ],
    }


def unit_story(**changes):
    raw = unit_raw()
    raw.update(changes)
    return parse_story(raw)


class UnitEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(unit_story())
        self.engine.start()

    def cmd(self, verb, *args):
        return self.engine.handle(Command(verb, list(args), verb)).lines

    def units(self):
        return self.engine.state.ext.get("mystery", {}).get("units", {})

    def test_entering_scene_grants_no_detail_clues(self):
        self.assertNotIn("front", self.engine.state.ext.get("mystery", {}).get("clues", []))
        self.assertEqual(self.units(), {})

    def test_inspect_spot_records_once_and_rereads_without_turn(self):
        lines = self.cmd("inspect", "lamp/front")
        self.assertIn("窄边上读得出“顾”“叁佰”。", lines)
        self.assertIn("【获得线索】正面窄边：顾、叁佰。", lines)
        self.assertEqual(self.engine.state.turn, 1)
        again = self.cmd("inspect", "lamp/front")
        self.assertIn("窄边上读得出“顾”“叁佰”。", again)
        self.assertEqual(self.engine.state.turn, 1)
        self.assertEqual(self.units()["lamp"]["spots"], ["front"])

    def test_inspect_accepts_names_and_reports_unknown_spot(self):
        self.assertIn("纸背有“供货汇记”和“五百八十四”。", self.cmd("inspect", "灯下残页", "灯侧照纸背"))
        self.assertIn("这里没有可以查看的“抽屉”。", self.cmd("inspect", "抽屉"))

    def test_solve_waits_for_required_spots(self):
        lines = self.cmd("solve", "lamp", "debt", "supply")
        self.assertIn("先查看：正面窄边、灯侧照纸背。", lines)
        self.assertEqual(self.engine.state.turn, 0)

    def look_all(self):
        self.cmd("inspect", "lamp/front")
        self.cmd("inspect", "lamp/back")

    def test_correct_answer_applies_effects_once(self):
        self.look_all()
        lines = self.cmd("solve", "lamp", "debt", "supply")
        self.assertIn("两面分开记下。", lines)
        self.assertIn("【获得线索】两笔分记：300 欠据与 584 汇记属于两笔账。", lines)
        self.assertEqual(self.units()["lamp"]["grade"], "ok")
        again = self.cmd("solve", "lamp", "debt", "supply")
        self.assertIn("“灯下残页”已经核对过了。", again)
        self.assertEqual(self.engine.state.ext["mystery"]["clues"].count("split"), 1)

    def test_names_work_like_ids(self):
        self.look_all()
        self.assertIn("两面分开记下。", self.cmd("solve", "灯下残页", "顾的欠据 300", "供货汇记 584"))

    def test_wrong_answer_gives_targeted_feedback_and_can_retry(self):
        self.look_all()
        lines = self.cmd("solve", "lamp", "supply", "debt")
        self.assertIn("正面的字是“顾”和“叁佰”。", lines)
        self.assertEqual(self.units()["lamp"]["tries"], 1)
        self.assertNotIn("grade", self.units()["lamp"])
        self.assertIn("两面分开记下。", self.cmd("solve", "lamp", "debt", "supply"))

    def test_merging_two_columns_uses_duplicate_feedback(self):
        self.look_all()
        self.assertIn("两面标题不同，先核对它们分别属于哪笔账。", self.cmd("solve", "lamp", "debt", "debt"))

    def test_unlisted_or_locked_option_is_rejected_without_turn(self):
        self.look_all()
        turn = self.engine.state.turn
        lines = self.cmd("solve", "lamp", "debt", "secret")
        self.assertIn("“secret”不是可选的背面记作。可选：顾的欠据 300、供货汇记 584", lines)
        self.assertEqual(self.engine.state.turn, turn)

    def test_missing_values_prompt_slots(self):
        self.look_all()
        self.assertIn("请依次给出：<正面记作> <背面记作>", self.cmd("solve", "lamp", "debt"))

    def test_hints_reveal_one_tier_at_a_time(self):
        self.assertIn("【提示 1/3】先看正面窄边和纸背。", self.cmd("hint", "lamp"))
        self.assertIn("【提示 2/3】比较两面的标题。", self.cmd("hint", "灯下残页"))
        self.assertIn("【提示 3/3】正面记欠据，背面记供货。", self.cmd("hint", "lamp"))
        turn = self.engine.state.turn
        self.assertIn("提示已经全部给出。", self.cmd("hint", "lamp"))
        self.assertEqual(self.engine.state.turn, turn)

    def test_weak_answer_needs_confirmation_then_keeps_grade(self):
        self.look_all()
        self.cmd("solve", "lamp", "debt", "supply")
        first = self.cmd("solve", "motive", "nervous")
        self.assertIn("紧张不是当夜冲突的依据。仍要这样写吗？", first)
        self.assertNotIn("grade", self.units()["motive"])
        second = self.cmd("solve", "motive", "nervous")
        self.assertIn("你保留了原判断。", second)
        self.assertEqual(self.units()["motive"]["grade"], "weak")

    def test_changing_answer_after_warning_can_still_reach_full(self):
        self.look_all()
        self.cmd("solve", "lamp", "debt", "supply")
        self.cmd("solve", "motive", "nervous")
        self.cmd("solve", "motive", "deadline")
        self.assertEqual(self.units()["motive"]["grade"], "full")

    def test_solved_condition_supports_grade(self):
        self.look_all()
        self.cmd("solve", "lamp", "debt", "supply")
        self.cmd("solve", "motive", "deadline")
        check = self.engine.registry.check
        ctx = self.engine._ctx()
        self.assertTrue(check(ctx, {"solved": "lamp"}))
        self.assertTrue(check(ctx, {"solved": "motive:full"}))
        self.assertFalse(check(ctx, {"solved": "motive:weak"}))
        self.assertTrue(check(ctx, {"inspected": "lamp/front"}))

    def test_unit_outside_its_scene_is_unavailable(self):
        self.look_all()
        self.cmd("solve", "lamp", "debt", "supply")
        self.cmd("choose", "leave")
        self.assertIn("这里没有可以核对的“灯下残页”。", self.cmd("solve", "lamp", "debt", "supply"))


class UnitSessionTest(unittest.TestCase):
    def setUp(self):
        self.session = GameSession(unit_story(), seed=1)
        self.session.start()

    def act(self, action_id, revision=None, **values):
        rev = self.session.snapshot().revision if revision is None else revision
        return self.session.dispatch(ActionRequest(action_id, rev, values))

    def action(self, action_id):
        view = self.session.snapshot()
        return next((a for a in view.actions if a.id == action_id), None)

    def test_snapshot_offers_spots_hint_and_disabled_solve_without_answers(self):
        inspect = self.action("mystery:inspect")
        self.assertEqual([o.id for o in inspect.parameters[0].options], ["lamp/front", "lamp/back"])
        solve = self.action("mystery:solve")
        self.assertFalse(solve.enabled)
        self.assertEqual(solve.disabled_reason, "先查看：正面窄边、灯侧照纸背。")
        self.assertEqual([p.key for p in solve.parameters], ["unit", "front", "back"])
        self.assertEqual([o.id for o in solve.parameters[2].options], ["debt", "supply"])
        text = repr(self.session.snapshot())
        self.assertNotIn("两面分开记下", text)
        self.assertNotIn("answer", text)
        hint = self.action("mystery:hint")
        self.assertEqual(hint.parameters[0].options[0].label, "提示 0/3")

    def test_snapshot_reads_do_not_change_state(self):
        before = self.session.export_save()
        for _ in range(3):
            self.session.snapshot()
        self.assertEqual(self.session.export_save(), before)

    def test_full_unit_through_session(self):
        self.act("mystery:inspect", spot="lamp/front")
        result = self.act("mystery:inspect", spot="lamp/back")
        self.assertIn("纸背有“供货汇记”和“五百八十四”。", result.messages)
        inspect = self.action("mystery:inspect")
        self.assertEqual([o.description for o in inspect.parameters[0].options], ["已查看", "已查看"])
        self.assertTrue(self.action("mystery:solve").enabled)
        wrong = self.act("mystery:solve", unit="lamp", front="supply", back="debt")
        self.assertIn("正面的字是“顾”和“叁佰”。", wrong.messages)
        ok = self.act("mystery:solve", unit="lamp", front="debt", back="supply")
        self.assertIn("两面分开记下。", ok.messages)
        self.assertEqual(self.action("mystery:solve").parameters[0].options[0].id, "motive")

    def test_stale_and_duplicate_requests_are_rejected(self):
        self.act("mystery:inspect", spot="lamp/front")
        self.act("mystery:inspect", spot="lamp/back")
        revision = self.session.snapshot().revision
        self.act("mystery:solve", unit="lamp", front="debt", back="supply")
        stale = self.act("mystery:solve", revision, unit="lamp", front="debt", back="supply")
        self.assertEqual(stale.error_code, "stale_revision")
        dup = self.act("mystery:solve", unit="lamp", front="debt", back="supply")
        self.assertEqual(dup.error_code, "invalid_parameters")
        self.assertEqual(self.session.engine.state.ext["mystery"]["clues"].count("split"), 1)

    def test_rewind_restores_unit_progress(self):
        self.act("mystery:inspect", spot="lamp/front")
        self.act("mystery:inspect", spot="lamp/back")
        self.act("mystery:solve", unit="lamp", front="debt", back="supply")
        saved = self.session.export_save()
        self.act("choice:leave")
        restored = GameSession(unit_story(), seed=1)
        restored.start()
        result = restored.restore(copy.deepcopy(saved))
        self.assertIsNone(result.error_code)
        units = restored.engine.state.ext["mystery"]["units"]
        self.assertEqual(units["lamp"]["grade"], "ok")
        self.assertEqual(units["lamp"]["spots"], ["front", "back"])

    def test_malformed_unit_progress_in_save_counts_as_unstarted(self):
        saved = self.session.export_save()
        saved["state"]["ext"]["mystery"] = {"units": {"lamp": {"spots": "front", "tries": "x"}, "motive": 3}}
        self.assertIsNone(self.session.restore(saved).error_code)
        inspect = self.action("mystery:inspect")
        self.assertEqual([o.description for o in inspect.parameters[0].options], ["", ""])
        result = self.act("mystery:inspect", spot="lamp/front")
        self.assertIsNone(result.error_code)
        self.assertEqual(self.session.engine.state.ext["mystery"]["units"]["lamp"]["spots"], ["front"])

    def test_hint_texts_stay_readable_in_snapshot(self):
        self.act("mystery:hint", unit="lamp")
        option = self.action("mystery:hint").parameters[0].options[0]
        self.assertEqual(option.label, "提示 1/3")
        self.assertEqual(option.description, "先看正面窄边和纸背。")


class UnitTextCommandTest(unittest.TestCase):
    def test_text_commands_map_to_action_values(self):
        engine = Engine(unit_story())
        engine.start()
        engine.handle(Command("inspect", ["lamp/front"], ""))
        engine.handle(Command("inspect", ["lamp/back"], ""))
        story, state, registry = engine.story, engine.state, engine.registry
        self.assertEqual(action_values(story, state, registry, Command("inspect", ["正面窄边"])),
                         {"spot": "lamp/front"})
        self.assertEqual(action_values(story, state, registry, Command("solve", ["灯下残页", "顾的欠据 300", "supply"])),
                         {"unit": "lamp", "front": "debt", "back": "supply"})
        self.assertEqual(action_values(story, state, registry, Command("hint", ["lamp"])), {"unit": "lamp"})
        self.assertIsNone(action_values(story, state, registry, Command("solve", ["lamp", "x"])))


class UnitValidationTest(unittest.TestCase):
    def test_clean_unit_story_has_no_issues(self):
        self.assertEqual([i for i in validate(unit_story()) if i.level == "error"], [])

    def test_reports_bad_unit_definitions(self):
        raw = unit_raw()
        lamp = raw["units"]["lamp"]
        lamp["scenes"] = ["nowhere"]
        lamp["slots"].append({"id": "unit", "label": "坏", "options": [{"id": "x"}]})
        lamp["solutions"][0]["answer"]["front"] = "ghost"
        lamp["spots"][0]["effects"] = [{"add_clue": "missing"}]
        raw["scenes"][0]["choices"][0]["when"] = {"solved": "nope"}
        messages = [f"{i.path}: {i.message}" for i in validate(parse_story(raw)) if i.level == "error"]
        joined = "\n".join(messages)
        self.assertIn("units.lamp.scenes: 场景不存在：nowhere", joined)
        self.assertIn("units.lamp.slots[2].id: 栏位 id 不能是 unit", joined)
        self.assertIn("units.lamp.solutions[0].answer.front: 选项不存在：ghost", joined)
        self.assertIn("线索不存在：missing", joined)
        self.assertIn("调查单元不存在：nope", joined)

    def test_malformed_units_are_reported_not_crash(self):
        raw = unit_raw()
        raw["units"] = {"lamp": "坏", "motive": {"slots": "坏", "spots": [1]}}
        issues = validate(parse_story(raw))
        self.assertTrue(any(i.path.startswith("units.lamp") for i in issues))
        engine = Engine(parse_story(raw))
        engine.start()
        engine.handle(Command("solve", ["lamp"], ""))


if __name__ == "__main__":
    unittest.main()
