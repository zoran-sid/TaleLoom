"""ZRS：真实剧本经控制器与真实会话逐步点击通关。

读取 stories/ 与真实 session_factory，属于系统层验证；动作全部来自
快照（choice:* / puzzle:* / mystery:*），不拼中文命令。
"""

import tempfile
import unittest
from pathlib import Path

from taleloom.gui.controller import GameController
from taleloom.session_factory import create_session

ROOT = Path(__file__).resolve().parents[2]
STORIES = ROOT / "stories"


class RealStoryPlaythroughTest(unittest.TestCase):
    def setUp(self):
        self.saves = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.saves.cleanup()

    def make(self):
        controller = GameController(STORIES, Path(self.saves.name), create_session)
        controller.load_catalog()
        return controller

    def test_both_stories_are_listed_and_valid(self):
        controller = self.make()
        self.assertEqual([s.id for s in controller.stories], ["deep_space", "fog_harbor"])
        self.assertEqual(controller.problems, [])

    def test_deep_space_escape_is_clickable(self):
        controller = self.make()
        self._play(controller, "deep_space", "escape", [
            ("choice:locker", {}),
            ("choice:out", {}),
            ("choice:tools", {}),
            ("choice:wrench", {}),
            ("choice:tank", {}),
            ("puzzle:combine", {"first": "broken_wrench", "second": "tape"}),
            ("choice:back", {}),
            ("choice:airlock", {}),
            ("puzzle:use", {"item": "fixed_wrench"}),
            ("choice:escape", {}),
        ])

    def test_fog_harbor_truth_is_clickable(self):
        controller = self.make()
        # 剧本 A 扩写后的完整推理链（ZC 随 PR #10 更新路线）。
        self._play(controller, "fog_harbor", "truth", [
            ("choice:office", {}),
            ("choice:ledger", {}),
            ("choice:window", {}),
            ("choice:body", {}),
            ("choice:desk", {}),
            ("mystery:examine", {"clue": "head_wound"}),
            ("mystery:examine", {"clue": "torn_ledger"}),
            ("choice:back", {}),
            ("choice:room", {}),
            ("choice:guest", {}),
            ("choice:coat", {}),
            ("choice:back", {}),
            ("choice:back", {}),
            ("mystery:ask", {"topic": "gu/coat"}),
            ("choice:kitchen", {}),
            ("mystery:ask", {"topic": "zhou/night"}),
            ("choice:vat", {}),
            ("mystery:ask", {"topic": "zhou/weight"}),
            ("choice:back", {}),
            ("choice:room", {}),
            ("choice:zhou", {}),
            ("choice:floor", {}),
            ("mystery:examine", {"clue": "secret_ledger"}),
            ("choice:back", {}),
            ("choice:attic", {}),
            ("choice:box", {}),
            ("choice:back", {}),
            ("choice:back", {}),
            ("choice:kitchen", {}),
            ("mystery:ask", {"topic": "ayun/letter"}),
            ("choice:back", {}),
            ("choice:gather", {}),
            ("mystery:accuse", {"suspect": "zhou", "motive": "embezzle",
                                "means": "paperweight", "evidence": "vat_weight"}),
        ])

    def _play(self, controller, story_id, ending, actions):
        self.assertTrue(controller.start(story_id), controller.error)
        for action_id, values in actions:
            offered = {a.id for a in controller.view.choices + controller.view.actions}
            self.assertIn(action_id, offered, f"{story_id} 的快照没有提供 {action_id}")
            action = next(a for a in controller.view.choices + controller.view.actions if a.id == action_id)
            for key, value in values.items():
                parameter = next(p for p in action.parameters if p.key == key)
                self.assertIn(value, {o.id for o in parameter.options})
            result = controller.submit(action_id, values)
            self.assertTrue(result.ok, result.error_code)
        self.assertTrue(controller.view.ended)
        self.assertEqual(controller.view.ending_id, ending)
        self.assertEqual(controller.view.choices, [])
        self.assertEqual(controller.view.actions, [])


if __name__ == "__main__":
    unittest.main()
