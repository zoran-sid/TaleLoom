"""ZRS：窗口冒烟测试——真实 Tk 窗口 + 测试替身。

覆盖书架、正文、选项按钮、笔记、多参数动作、存读档与结局页；
不启动 mainloop，只 update 让布局生效。整个模块共用一个隐藏的根窗口，
避免反复创建／销毁 Tk 根时 ttk 样式事件指向旧窗口。

跳过只在两种真实缺失时发生，且原因分开写：没装 Tcl/Tk，或没有图形显示
（Linux 上用 `xvfb-run -a` 运行即可，见 issue #15）。
"""

import atexit
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    import tkinter as tk
except ImportError:          # CI 的 Python 可能不带 Tcl/Tk
    tk = None

from taleloom.gui.controller import GameController
from taleloom.ui_contract import ActionParameter, ActionSpec, DisplayItem
from tests.ui_fakes import FakeGameSession

_ROOT = None
_DISPLAY: bool | None = None
_SKIP_REASON = ""


def no_display_reason() -> str:
    """返回空字符串表示可创建窗口；否则给出具体原因，便于 CI 日志判断。"""
    global _ROOT, _DISPLAY, _SKIP_REASON
    if _DISPLAY is None:
        if tk is None:
            _DISPLAY, _SKIP_REASON = False, "当前 Python 没有 Tcl/Tk（tkinter 不可导入）"
        else:
            try:
                _ROOT = tk.Tk()
            except tk.TclError:
                missing = "没有图形显示"
                if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                    missing = "没有图形显示（DISPLAY 未设置；可用 xvfb-run -a 运行）"
                _DISPLAY, _SKIP_REASON = False, missing
            else:
                _ROOT.withdraw()
                _ROOT.geometry("700x520")
                _DISPLAY, _SKIP_REASON = True, ""
                atexit.register(_ROOT.destroy)
    return _SKIP_REASON


def root():
    return _ROOT if no_display_reason() == "" else None


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


class AccusationSession(FakeGameSession):
    """模拟指认：四个参数（三选一 + 一列证据），用来验证较宽的动作表单不会溢出。"""

    def snapshot(self):
        view = super().snapshot()
        view.step = 0
        view.actions = [ActionSpec('mystery:accuse', '作出指认', [
            ActionParameter('suspect', '指认对象', options=[DisplayItem('gu', '顾先生'), DisplayItem('zhou', '周文')]),
            ActionParameter('motive', '动机', options=[DisplayItem('debt', '欠债'),
                                                     DisplayItem('embezzle', '挪用账款被发现'),
                                                     DisplayItem('robbery', '谋财')]),
            ActionParameter('means', '手段', options=[DisplayItem('poison', '下毒'),
                                                    DisplayItem('weight', '用铜镇纸击打后脑'),
                                                    DisplayItem('window', '翻窗潜入')]),
            ActionParameter('evidence', '关键证据', options=[
                DisplayItem(f'clue{i}', f'第 {i + 1} 条线索的完整名称') for i in range(6)]),
        ])]
        return view


@unittest.skipIf(no_display_reason() != "", no_display_reason())
class WindowTest(unittest.TestCase):
    LONG_TEXT = "很长的中文段落，用来验证自动换行与滚动。" * 40

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        for story_id in ("ui_demo", "long", "accuse"):
            story_dir = self.root / "stories" / story_id
            story_dir.mkdir(parents=True)
            story = json.loads(json.dumps(STORY))
            story["id"] = story_id
            (story_dir / "story.json").write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
        sessions = {
            "long": lambda: LongTextSession(self.LONG_TEXT),
            "accuse": AccusationSession,
        }
        self.controller = GameController(
            self.root / "stories", self.root / "saves",
            lambda story: sessions.get(story.id, FakeGameSession)())
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

    def test_wide_parameter_forms_fit_narrow_window(self):
        """指认有四个参数；横排时表单比窗口还宽，递交按钮会被挤出可视区。"""
        self.tk.deiconify()
        self.tk.geometry("560x420")
        self.window.show_library()
        self.window._start("accuse", False)
        for _ in range(4):
            self.tk.update()
        card = widgets(self.window.actions, "Frame")[0]
        submit = widgets(card, "Button")[-1]
        self.assertEqual(submit.cget("text"), "作出指认")
        self.assertEqual(len(widgets(card, "Combobox")), 4)
        limit = self.window.scroller.canvas.winfo_width()
        self.assertGreater(limit, 300, "画布应已按窗口宽度布局")
        right = card.winfo_x() + submit.winfo_x() + submit.winfo_width()
        self.assertLessEqual(right, limit, f"递交按钮在 {right}px，可视宽度 {limit}px")
        self.tk.geometry("1020x720")

    def test_open_failure_is_explained_on_shelf(self):
        self.controller.stories = []
        self.window.show_library()
        self.window._start("missing", False)
        self.tk.update()
        self.assertTrue(self.window.library.grid_info(), "失败后应留在书架页")
        self.assertFalse(self.window.game.grid_info(), "失败后不应进入游戏页")
        self.assertIn("找不到", self.window.open_error.cget("text"))

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
