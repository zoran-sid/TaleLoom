"""集成：桌面失败回退在真实影像剧本上的窗口级验证。负责人：ZRS，目录归 ZC。

用 stories/film/ 的真实剧本，按选项文字点击（不手写场景 id），
验证失败结局出现“回到上一个选择”，并能真的回到上一个选择。
剧本作者改剧情时这里不用改；没有图形显示时跳过（CI 用 xvfb 后真跑）。
"""

import tempfile
import unittest
from pathlib import Path

try:
    import tkinter as tk
except ImportError:
    tk = None

from taleloom.gui.controller import GameController
from taleloom.session_factory import create_session
from tests.zrs.test_gui_window import no_display_reason, root, widgets

ROOT = Path(__file__).resolve().parents[2]
FILM = ROOT / "stories" / "film" / "fog_harbor_film"


@unittest.skipIf(no_display_reason() != "", no_display_reason())
class FilmRollbackWindowTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.controller = GameController(ROOT / "stories" / "film", Path(self.folder.name), create_session)
        self.controller.load_catalog()
        self.tk = root()
        for child in self.tk.winfo_children():
            child.destroy()
        self.tk.geometry("1020x720")
        from taleloom.gui.window import TaleLoomWindow
        self.window = TaleLoomWindow(self.tk, self.controller)

    def tearDown(self):
        for child in self.tk.winfo_children():
            child.destroy()
        self.folder.cleanup()

    def click(self, label_part: str) -> None:
        """按选项文字点击（剧本作者改剧情时这里不用改）。"""
        for _ in range(4):
            self.tk.update()
        for widget in self.window.choices.winfo_children():
            if label_part in widget.cget("text"):
                widget.invoke()
                self.tk.update()
                return
        raise AssertionError(f"没有找到选项：{label_part}；当前 {[w.cget('text') for w in self.window.choices.winfo_children()]}")

    def test_film_story_reaches_failure_and_can_rewind(self):
        self.window.show_library()
        self.window._start("fog_harbor_film", False)
        self.tk.update()
        self.click("推开账房的门")
        self.click("查看半开的窗户")
        self.click("绕到后院")
        self.click("沿石阶下到码头")
        self.assertTrue(self.controller.view.ended)
        self.assertEqual(self.controller.view.ending_id, "fail_tide")
        self.assertTrue(self.controller.failed)
        texts = [w.cget("text") for w in widgets(self.window.ending, "Button")]
        self.assertTrue(any("回到上一个选择" in t for t in texts), texts)

        self.controller.rewind()          # 直接走控制器，避开确认对话框
        self.tk.update()
        self.window.render()
        self.assertEqual(self.controller.view.scene_id, "backyard")
        self.assertFalse(self.controller.view.ended)
        self.assertEqual(self.controller.chances_left, 2)

    def test_checkpoint_list_appears_on_ending(self):
        self.window.show_library()
        self.window._start("fog_harbor_film", False)
        self.tk.update()
        self.click("推开账房的门")          # 进入账房 = 第一个存档点
        self.assertTrue(self.controller.checkpoints, "进入账房后应记下存档点")
        self.assertIn("账房", self.controller.checkpoints[0]["label"])


if __name__ == "__main__":
    unittest.main()
