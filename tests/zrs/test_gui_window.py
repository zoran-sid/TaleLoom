"""ZRS：窗口冒烟测试——真实 Tk 窗口 + 测试替身，无图形显示时跳过。

覆盖书架、正文、选项按钮、笔记、道具参数、存读档与结局页；
不启动 mainloop，只 update 让布局生效。整个模块共用一个隐藏的根窗口，
避免反复创建／销毁 Tk 根时 ttk 样式事件指向旧窗口。
"""

import atexit
import json
import tempfile
import types
import unittest
from pathlib import Path

try:
    import tkinter as tk
except ImportError:          # CI 的 Python 可能不带 Tcl/Tk
    tk = None

from taleloom.gui.controller import GameController
from tests.ui_fakes import FakeGameSession

_ROOT = None
_DISPLAY: bool | None = None


def root():
    global _ROOT, _DISPLAY
    if _DISPLAY is None:
        if tk is None:
            _DISPLAY = False
        else:
            try:
                _ROOT = tk.Tk()
            except tk.TclError:      # 没有图形显示
                _DISPLAY = False
            else:
                _ROOT.withdraw()
                _ROOT.geometry("700x520")
                _DISPLAY = True
                atexit.register(_ROOT.destroy)
    return _ROOT if _DISPLAY else None


def widgets(container, kind=None):
    """递归列出子控件；ttk 与 tk 的类名不同，用 winfo_class 判断。"""
    found = []
    for child in container.winfo_children():
        if kind is None or child.winfo_class().endswith(kind):
            found.append(child)
        found += widgets(child, kind)
    return found


def texts(container, kind="Label"):
    return [w.cget("text") for w in widgets(container, kind)]


class LongTextSession(FakeGameSession):
    """正文来自剧本的长段落，其余行为沿用测试替身。"""

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def snapshot(self):
        view = super().snapshot()
        view.text = self.text
        return view


@unittest.skipUnless(root() is not None, "当前环境没有可用的图形显示")
class WindowTest(unittest.TestCase):
    LONG_TEXT = "很长的中文段落，用来验证自动换行与滚动。" * 40

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        for story_id in ("ui_demo", "long"):
            story_dir = self.root / "stories" / story_id
            story_dir.mkdir(parents=True)
            story = json.loads(json.dumps(STORY))
            story["id"] = story_id
            (story_dir / "story.json").write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
        self.controller = GameController(
            self.root / "stories", self.root / "saves",
            lambda story: LongTextSession(self.LONG_TEXT) if story.id == "long" else FakeGameSession())
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

    def open_story(self):
        self.window.show_library()
        self.window._start("ui_demo", False)
        self.tk.update()

    def action_submit(self):
        card = widgets(self.window.actions, "Frame")[0]
        return widgets(card, "Button")[0]

    def test_shelf_shows_story_and_start_button(self):
        self.assertIn("界面测试剧本", texts(self.window.shelf))
        self.assertEqual(self.window._story_buttons["ui_demo"].cget("text"), "开始阅读")

    def test_start_renders_scene_text_and_choices(self):
        self.open_story()
        self.assertEqual(self.window.scene_title.cget("text"), "门厅")
        self.assertEqual(self.window.scene_text.cget("text"), "门边有一把钥匙。")
        self.assertEqual([w.cget("text") for w in widgets(self.window.choices, "Button")], ["捡起钥匙"])

    def test_clicking_choice_button_advances_and_renders_actions(self):
        self.open_story()
        widgets(self.window.choices, "Button")[0].invoke()
        self.tk.update()
        self.assertEqual([w.cget("text") for w in widgets(self.window.choices, "Button")], ["打开房门"])
        self.assertIn("钥匙", texts(self.window.inventory))
        self.assertIn("使用物品", texts(self.window.actions))
        self.assertEqual(widgets(self.window.actions, "Combobox")[0].cget("values"), ("钥匙",))

    def test_parameter_action_completes_story(self):
        self.open_story()
        widgets(self.window.choices, "Button")[0].invoke()
        self.action_submit().invoke()
        self.tk.update()
        self.assertTrue(self.controller.view.ended)
        self.assertIn("这一页，已写下结局。", texts(self.window.ending))

    def test_stale_action_is_reported_and_view_keeps_new_state(self):
        self.open_story()
        widgets(self.window.choices, "Button")[0].invoke()
        widgets(self.window.choices, "Button")[0].invoke()   # 打开房门
        self.assertEqual(self.controller.view.scene_title, "门外")
        self.assertEqual(widgets(self.window.choices, "Button"), [])

    def test_long_text_wraps_to_window_width_and_scrolls(self):
        self.window.show_library()
        self.window._start("long", False)
        self.tk.update()
        self.assertEqual(self.window.scene_text.cget("text"), self.LONG_TEXT)
        self.assertGreaterEqual(self.window.scene_text.cget("wraplength"), 300)
        self.assertGreater(self.window.scroller.canvas.bbox("all")[3], 300)

    def test_narrow_window_moves_notes_below_text(self):
        self.window.show_library()
        self.window._start("ui_demo", False)
        self.tk.update()
        self.window._on_body_resize(types.SimpleNamespace(width=560))
        self.tk.update()
        self.assertTrue(self.window._narrow)
        self.assertGreater(self.window.sidebar.winfo_y(), self.window.page.winfo_y())
        self.window._on_body_resize(types.SimpleNamespace(width=980))
        self.tk.update()
        self.assertFalse(self.window._narrow)
        self.assertEqual(self.window.sidebar.winfo_y(), 0)

    def test_save_marks_progress_saved_and_shelf_offers_continue(self):
        self.open_story()
        widgets(self.window.choices, "Button")[0].invoke()
        self.controller.save()
        self.window.render()
        self.assertIn("已保存", self.window.story_label.cget("text"))
        self.window.show_library()
        self.assertIn("继续阅读", texts(self.window.shelf, "Button"))

    def test_notes_and_resources_do_not_advance_turn(self):
        self.open_story()
        turn, revision = self.controller.view.turn, self.controller.view.revision
        self.window.render()
        self.window.render()
        self.assertEqual((self.controller.view.turn, self.controller.view.revision), (turn, revision))

    def test_missing_save_reports_on_load(self):
        self.open_story()
        self.window._load()
        self.assertIn("先点“保存进度”", self.window.status_label.cget("text"))


STORY = {
    "format_version": 1, "id": "ui_demo", "title": "界面测试剧本", "start": "hall",
    "scenes": [
        {"id": "hall", "title": "门厅", "text": "门边有一把钥匙。",
         "choices": [{"id": "take", "text": "捡起钥匙", "once": True},
                     {"id": "open", "text": "打开房门", "goto": "out"}]},
        {"id": "out", "title": "门外", "text": "你出来了。", "ending": {"id": "out", "title": "出门"}},
    ],
}


if __name__ == "__main__":
    unittest.main()
