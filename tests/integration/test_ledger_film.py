"""《雾港旧案：未结的账》影像版：剧情事实、证据时机、调查单元与存档回退。负责人：ZC。

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

# 进入场景时允许直接记下的事实：剧本写明“记录”的公开信息与人物当面说出的话。
MANDATED = {"paperweight_seen", "iou_mail", "ayun_waits", "tea_crack", "ayun_account", "gu_account",
            "gu_refused", "liability_724", "pingchao", "book_refused"}


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

    def test_entering_scenes_grants_only_mandated_facts(self):
        for sid, scene in self.story.scenes.items():
            granted = {e["add_clue"] for e in scene.on_enter if "add_clue" in e}
            with self.subTest(scene=sid):
                self.assertLessEqual(granted, MANDATED)

    def test_cloth_is_seen_before_anyone_is_called(self):
        found = self.story.scenes["a01_found"]
        for choice in found.choices:
            with self.subTest(choice=choice.id):
                self.assertIn({"add_clue": "cloth_first"}, choice.effects)
                self.assertEqual(choice.goto, "a02_door")
        self.assertNotIn("周文", found.text.split("灰蓝布")[0].split("账房没有回答")[1])

    def test_detail_records_need_their_own_look(self):
        engine, _ = run("truth_later")
        clues = engine.state.ext["mystery"]["clues"]
        self.assertIn("cloth_first", clues)
        for detail in ("wound", "cloth_detail", "weight_missing"):
            self.assertNotIn(detail, clues, "没有查看的细节不能自动记下")

    def test_player_text_has_no_author_notes(self):
        banned = ("调查／推进", "作者", "进入条件", "替代路线", "通关", "if ", "flag")
        for sid, scene in self.story.scenes.items():
            texts = [scene.text] + [c.text for c in scene.choices] + [c.message or "" for c in scene.choices]
            texts += [v["text"] for v in scene.variants]
            for text in texts:
                for word in banned:
                    with self.subTest(scene=sid, word=word):
                        self.assertNotIn(word, text)

    def test_snapshots_never_reveal_answers_feedback_or_locked_hints(self):
        units = self.story.data["units"]
        secrets = {s["text"] for u in units.values() for s in u.get("solutions", []) if s.get("text")}
        secrets |= {f["text"] for u in units.values() for f in u.get("feedback", [])}
        vector = self.vectors["truth"]
        session = create_session(self.story, seed=0)
        view = session.start().view
        for step in vector["actions"]:
            text = repr(view)
            for secret in secrets:
                self.assertNotIn(secret.split("\n")[0], text)
            view = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"])).view

    def test_story_choices_wait_for_unit_checks(self):
        session = create_session(self.story, seed=0)
        view = session.start().view
        vector = self.vectors["truth"]
        for step in vector["actions"]:
            if view.scene_id == "a03_lamp":
                break
            view = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"])).view
        self.assertEqual(view.scene_id, "a03_lamp")
        self.assertNotIn("choice:window", [c.id for c in view.choices])
        blocked = session.dispatch(ActionRequest("choice:window", view.revision, {}))
        self.assertEqual(blocked.error_code, "invalid_action")
        solve = next(a for a in view.actions if a.id == "mystery:solve")
        self.assertFalse(solve.enabled, "三处都没看就不能提交核对")

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

    def test_five_checkpoints_in_order(self):
        labels = [s.checkpoint for s in self.story.scenes.values() if s.checkpoint]
        self.assertEqual(labels, ["一 · 夜深取账", "二 · 旧账", "三 · 后厨", "四 · 对质之前", "五 · 最后签字"])

    def test_checkpoint_rollback_restores_unit_progress(self):
        session = create_session(self.story, seed=0)
        view = session.start().view
        for step in self.vectors["truth"]["actions"]:
            view = session.dispatch(ActionRequest(step["action_id"], view.revision, step["values"])).view
            if view.scene_id == "d01_kitchen":
                break
        units = lambda: session.export_save()["state"]["ext"]["mystery"]["units"]
        self.assertEqual(units()["sums"]["grade"], "full")
        target = next(c for c in session.list_checkpoints() if c.label == "二 · 旧账")
        result = session.restore_checkpoint(target.id, view.revision)
        self.assertTrue(result.ok, result.messages)
        self.assertEqual(result.view.scene_id, "c01_batch")
        self.assertNotIn("sums", units())
        self.assertNotIn("batch", units())
        self.assertEqual(units()["lamp"]["grade"], "ok", "存档点之前完成的调查保留")

    def test_saved_ending_restores_with_unit_progress(self):
        for name, vector in self.vectors.items():
            with self.subTest(walkthrough=name):
                session = create_session(self.story, seed=0)
                session.start()
                self.assertTrue(session.restore(vector["save"]).ok)
                self.assertEqual(session.snapshot().ending_id, vector["ending"])
                self.assertIn("units", session.export_save()["state"]["ext"]["mystery"])


if __name__ == "__main__":
    unittest.main()
