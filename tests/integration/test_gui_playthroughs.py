"""集成：真实剧本经桌面界面控制器逐步通关。负责人：ZRS，目录归 ZC。

动作由 tools.web_vectors.build_vectors() 从通关脚本生成，与网页桥接使用
同一份数据；剧本作者改剧情后这里不需要手改步骤。steps 的提交方式与
窗口一致（GameController.submit），因此验证的是 GUI 真正会用到的路径。
"""

import tempfile
import unittest
from pathlib import Path

from taleloom.gui.controller import GameController
from taleloom.session_factory import create_session
from tools.web_vectors import build_vectors

ROOT = Path(__file__).resolve().parents[2]
STORIES = ROOT / "stories"


class GuiPlaythroughTest(unittest.TestCase):
    def setUp(self):
        self.saves = tempfile.TemporaryDirectory()
        self.vectors = build_vectors()

    def tearDown(self):
        self.saves.cleanup()

    def make(self):
        controller = GameController(STORIES, Path(self.saves.name), lambda story: create_session(story, seed=0))
        controller.load_catalog()
        return controller

    def test_catalog_lists_valid_stories(self):
        controller = self.make()
        self.assertEqual([s.id for s in controller.stories], ["deep_space", "fog_harbor"])
        self.assertEqual(controller.problems, [])

    def test_every_walkthrough_is_clickable(self):
        """两个剧本的全部通关脚本都只用界面提供的动作走完，结局与脚本一致。"""
        self.assertGreaterEqual(len(self.vectors), 2)
        self.assertEqual({v["story_id"] for v in self.vectors}, {"deep_space", "fog_harbor"})
        controller = self.make()
        for vector in self.vectors:
            with self.subTest(story=vector["story_id"], walkthrough=vector["name"]):
                seed = vector['initial_save']['state'].get('random_seed', 0)
                controller._create_session = lambda story: create_session(story, seed=seed)
                self.assertTrue(controller.start(vector["story_id"]), controller.error)
                for index, step in enumerate(vector["actions"]):
                    offered = {a.id for a in controller.view.choices + controller.view.actions}
                    self.assertIn(step["action_id"], offered,
                                  f"第 {index + 1} 步界面没有提供 {step['action_id']}")
                    action = next(a for a in controller.view.choices + controller.view.actions
                                  if a.id == step["action_id"])
                    for key, value in step["values"].items():
                        parameter = next(p for p in action.parameters if p.key == key)
                        self.assertIn(value, {o.id for o in parameter.options},
                                      f"第 {index + 1} 步 {key} 候选里没有 {value}")
                    result = controller.submit(step["action_id"], step["values"])
                    self.assertTrue(result.ok, f"第 {index + 1} 步失败：{result.error_code}")
                self.assertTrue(controller.view.ended)
                self.assertEqual(controller.view.ending_id, vector["ending"])
                self.assertEqual(controller.view.choices, [])
                self.assertEqual(controller.view.actions, [])

    def test_save_and_resume_mid_walkthrough(self):
        """走到一半存档、返回书架、继续阅读，能接着走完同一结局。"""
        vector = next(v for v in self.vectors if v["story_id"] == "fog_harbor")
        controller = self.make()
        self.assertTrue(controller.start(vector["story_id"]))
        half = len(vector["actions"]) // 2
        for step in vector["actions"][:half]:
            self.assertTrue(controller.submit(step["action_id"], step["values"]).ok)
        self.assertTrue(controller.save())
        scene = controller.view.scene_id
        controller.home()
        self.assertTrue(controller.start(vector["story_id"], resume=True))
        self.assertEqual(controller.view.scene_id, scene)
        for step in vector["actions"][half:]:
            result = controller.submit(step["action_id"], step["values"])
            self.assertTrue(result.ok, result.error_code)
        self.assertEqual(controller.view.ending_id, vector["ending"])


if __name__ == "__main__":
    unittest.main()
