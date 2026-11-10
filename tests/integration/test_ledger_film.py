"""《雾港旧案：未结的账》影像版：剧情事实、证据时机、剧情选择与存档回退。负责人：ZC。

剧本由 stories/film/fog_harbor_ledger/ 提供；本文件检查剧本交接表里约定的事实与次序，
以及正式会话下的调查、回退和结局。
"""

import unittest

from taleloom import replay
from taleloom.loader import load_story
from taleloom.session_factory import create_session
from taleloom.ui_contract import ActionRequest
from tests.fixtures import STORIES
from tools.web_vectors import build_vectors

LEDGER = STORIES / "film" / "fog_harbor_ledger"


def run(name):
    story = load_story(LEDGER)
    walk = replay.load_walkthrough(LEDGER / "walkthroughs" / f"{name}.txt")
    engine, transcript = replay.run_commands(story, walk.commands, seed=walk.seed)
    return engine, transcript


class LedgerStoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.story = load_story(LEDGER)
        cls.vectors = {v["name"]: v for v in build_vectors([LEDGER / "story.json"])}

    def test_all_routes_use_story_choices_without_evidence_quizzes(self):
        self.assertFalse(self.story.data.get("units"))
        for name, vector in self.vectors.items():
            with self.subTest(route=name):
                self.assertTrue(all(a["action_id"].startswith("choice:") for a in vector["actions"]))

    def test_discoveries_are_recorded_where_the_story_describes_them(self):
        expected = {"p02_lobby": "sleeve_intact", "a03_lamp": "two_accounts",
                    "d02_weight": "weight_id", "d02_sleeve": "sleeve_match"}
        for sid, clue in expected.items():
            self.assertIn({"add_clue": clue}, self.story.scenes[sid].on_enter)
        self.assertNotIn({"add_clue": "sleeve_match"}, self.story.scenes["d02_refuse"].on_enter)

    def test_cloth_is_seen_before_anyone_is_called(self):
        found = self.story.scenes["a01_found"]
        for choice in found.choices:
            with self.subTest(choice=choice.id):
                self.assertIn({"add_clue": "cloth_first"}, choice.effects)
                self.assertEqual(choice.goto, "a02_door")
        self.assertNotIn("周文", found.text.split("灰蓝布")[0].split("账房没有回答")[1])

    def test_visible_scene_details_are_recorded_without_extra_inspect_clicks(self):
        engine, _ = run("truth_later")
        clues = engine.state.ext["mystery"]["clues"]
        for detail in ("wound", "cloth_detail", "weight_missing"):
            self.assertIn(detail, clues)

    def test_player_text_has_no_author_notes(self):
        banned = ("调查／推进", "作者", "进入条件", "替代路线", "通关", "if ", "flag")
        for sid, scene in self.story.scenes.items():
            texts = [scene.text] + [c.text for c in scene.choices] + [c.message or "" for c in scene.choices]
            texts += [v["text"] for v in scene.variants]
            for text in texts:
                for word in banned:
                    with self.subTest(scene=sid, word=word):
                        self.assertNotIn(word, text)

    def test_snapshots_offer_story_choices_without_investigation_forms(self):
        session = create_session(self.story, seed=0)
        view = session.start().view
        for step in self.vectors["truth"]["actions"]:
            self.assertFalse({"mystery:inspect", "mystery:solve", "mystery:hint"} & {a.id for a in view.actions})
            result = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"]))
            self.assertTrue(result.ok, result.messages)
            view = result.view

    def test_lamp_scene_can_continue_without_quiz_submission(self):
        session = create_session(self.story, seed=0)
        view = session.start().view
        for step in self.vectors["truth"]["actions"]:
            if view.scene_id == "a03_lamp":
                break
            view = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"])).view
        self.assertIn("choice:window", [c.id for c in view.choices])
        result = session.dispatch(ActionRequest("choice:window", view.revision, {}))
        self.assertTrue(result.ok)
        self.assertEqual(result.view.scene_id, "a04_window")

    def test_old_save_at_unfinished_discovery_can_leave_and_keep_scene_facts(self):
        session = create_session(self.story, seed=0)
        view = session.start().view
        targets = {"p02_lobby", "a03_lamp", "b01_paper", "c01_batch", "d02_weight", "d02_sleeve"}
        checked = set()
        for step in self.vectors["truth"]["actions"]:
            sid = view.scene_id
            if sid in targets and sid not in checked:
                payload = session.export_save()
                mine = payload["state"]["ext"]["mystery"]
                facts = {e["add_clue"] for e in self.story.scenes[sid].on_enter if "add_clue" in e}
                mine["clues"] = [c for c in mine["clues"] if c not in facts]
                mine["units"] = {"retired": {"spots": [], "tries": 1, "last": {"answer": "wrong"}}}
                self.assertTrue(session.restore(payload).ok)
                result = session.dispatch(ActionRequest(step["action_id"], session.snapshot().revision, {}))
                self.assertTrue(result.ok, (sid, result.messages))
                self.assertLessEqual(facts, {c.id for c in result.view.clues})
                checked.add(sid)
            else:
                result = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"]))
                self.assertTrue(result.ok, result.messages)
            view = result.view
        self.assertEqual(checked, targets)
        self.assertEqual(view.ending_id, "truth")

    def test_routes_follow_the_handoff_table(self):
        expected = {
            "truth": ("e03_confess", "b05_gu"),
            "truth_guarded": ("e03_deny", "b05_silent"),
            "truth_later": ("e03_confess", "b05_gu"),
        }
        for name, scenes in expected.items():
            engine, _ = run(name)
            for sid in scenes:
                with self.subTest(walkthrough=name, scene=sid):
                    self.assertIn(sid, engine.state.visited)
        engine, _ = run("insufficient")
        self.assertFalse({"e03_confess", "e03_deny"} & set(engine.state.visited), "事实链不完整时不播放答复")
        self.assertNotIn("sleeve_match", engine.state.ext["mystery"]["clues"], "拒绝路线不能发放完整匹配")

    def test_repair_routes_keep_the_case_solvable(self):
        engine, transcript = run("truth_guarded")
        clues = engine.state.ext["mystery"]["clues"]
        self.assertIn("ayun_three", clues)
        self.assertNotIn("ayun_account", clues, "公开念信后，阿芸的私人细节不再开放")
        self.assertNotIn("gu_account", clues, "顾拒答时不能得到“进门时已倒下”的叙述")
        self.assertIn("confirm_found", clues)
        self.assertEqual(engine.state.ending, "truth")

    def test_ending_variants_follow_old_funds_and_preservation(self):
        _, truth = run("truth")
        self.assertTrue(any("索问函" in line for line in truth))
        _, guarded = run("truth_guarded")
        self.assertTrue(any("登记为待查" in line for line in guarded))
        _, pending = run("dawn_pending")
        self.assertTrue(any("清单旁的标记照实写着" in line for line in pending))
        _, dawn = run("dawn")
        self.assertTrue(any("每件东西的来处" in line for line in dawn))
        _, gaps = run("insufficient")
        self.assertTrue(any("布片是谁比对的" in line for line in gaps))
        self.assertFalse(any("阿芸到底支持了哪一段时间" in line for line in gaps), "只列真实缺项")

    def interrogation(self, route="truth_guarded"):
        """按真实路线到达对质，供缺项组合验证使用。"""
        session = create_session(self.story, seed=0)
        view = session.start().view
        for step in self.vectors[route]["actions"]:
            view = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"])).view
            if view.scene_id == "e02_zhou":
                return session
        self.fail("通关路线没有到达对质")

    def finish_with_gaps(self, session, missing):
        """旧存档可缺少早期事实；结局按实际材料列缺项，不依赖旧答题评分。"""
        payload = session.export_save()
        clues = payload["state"]["ext"]["mystery"]["clues"]
        missing_clues = {"q_time": "duty_check", "q_object": "weight_id",
                         "q_person": "sleeve_match", "q_motive": "motive_724"}
        for key in missing:
            clues.remove(missing_clues[key])
        payload["state"]["ext"]["mystery"]["units"] = {key: {"grade": "full"} for key in missing_clues}
        self.assertTrue(session.restore(payload).ok)
        for action in ("gaps", "old_pending", "sign_zhou_gap"):
            result = session.dispatch(ActionRequest(f"choice:{action}", session.snapshot().revision, {}))
            self.assertTrue(result.ok, result.messages)
        return session.snapshot().text

    def test_refused_testimony_does_not_reappear_in_insufficient_ending(self):
        session = self.interrogation()
        self.assertNotIn("gu_account", {c.id for c in session.snapshot().clues})
        text = self.finish_with_gaps(session, {"q_person"})
        self.assertNotIn("顾坚持保留“翻窗后看见什么”", text)
        self.assertIn("顾拒绝谈账房经过", text)

    def test_missing_motive_feedback_asks_about_tonight_not_proven_scene_link(self):
        text = self.finish_with_gaps(self.interrogation(), {"q_motive"})
        self.assertIn("为什么偏偏是今晚", text)
        self.assertNotIn("什么把这个人和当夜的现场连起来", text)

    def test_four_gaps_report_three_questions_and_disclose_remaining_gap(self):
        text = self.finish_with_gaps(self.interrogation(), {"q_time", "q_object", "q_person", "q_motive"})
        self.assertEqual(text.count("？”"), 3)
        self.assertIn("另有一项待查：当夜冲突", text)

    def test_five_checkpoints_in_order(self):
        labels = [s.checkpoint for s in self.story.scenes.values() if s.checkpoint]
        self.assertEqual(labels, ["一 · 夜深取账", "二 · 旧账", "三 · 后厨", "四 · 对质之前", "五 · 最后签字"])

    def test_checkpoint_rollback_removes_later_discoveries(self):
        session = create_session(self.story, seed=0)
        view = session.start().view
        for step in self.vectors["truth"]["actions"]:
            view = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"])).view
            if view.scene_id == "d01_kitchen":
                break
        self.assertIn("motive_724", {c.id for c in view.clues})
        target = next(c for c in session.list_checkpoints() if c.label == "二 · 旧账")
        result = session.restore_checkpoint(target.id, view.revision)
        self.assertTrue(result.ok, result.messages)
        self.assertEqual(result.view.scene_id, "c01_batch")
        clues = {c.id for c in result.view.clues}
        self.assertNotIn("motive_724", clues)
        self.assertNotIn("relief_340", clues)
        self.assertIn("two_accounts", clues)

    def test_saved_ending_restores_without_unit_progress(self):
        for name, vector in self.vectors.items():
            with self.subTest(walkthrough=name):
                session = create_session(self.story, seed=0)
                session.start()
                self.assertTrue(session.restore(vector["save"]).ok)
                self.assertEqual(session.snapshot().ending_id, vector["ending"])
                self.assertNotIn("units", session.export_save()["state"]["ext"]["mystery"])


if __name__ == "__main__":
    unittest.main()
