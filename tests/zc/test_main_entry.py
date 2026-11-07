"""ZC：main.py 启动入口——无参数打开 GUI，缺少 GUI 或 Tkinter 时回退命令行。"""

import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

import main


def fake_find_spec(missing):
    """返回一个 find_spec 替身：missing 中的模块视为未安装。"""
    return lambda name, *args: None if name in missing else object()


class MainEntryTest(unittest.TestCase):
    def run_main(self, argv, missing=()):
        with mock.patch.object(main.importlib.util, "find_spec", fake_find_spec(missing)), \
                mock.patch.object(main, "cmd_play", return_value=0) as play, \
                redirect_stdout(io.StringIO()) as out:
            code = main.main(argv)
        return code, play, out.getvalue()

    def test_no_args_falls_back_to_cli_until_gui_exists(self):
        code, play, out = self.run_main([], missing={"taleloom.gui"})
        self.assertEqual(code, 0)
        play.assert_called_once_with(None)
        self.assertIn("命令行模式", out)

    def test_no_args_falls_back_when_tkinter_missing(self):
        code, play, out = self.run_main([], missing={"tkinter"})
        play.assert_called_once_with(None)
        self.assertIn("Tkinter", out)

    def test_no_args_opens_gui_with_story_and_save_dirs(self):
        gui = types.ModuleType("taleloom.gui")
        gui.run = mock.Mock(return_value=0)
        with mock.patch.dict(sys.modules, {"taleloom.gui": gui}):
            code, play, _ = self.run_main([])
        self.assertEqual(code, 0)
        play.assert_not_called()
        gui.run.assert_called_once_with(stories_dir=main.STORIES, saves_dir=main.SAVES)

    def test_play_subcommand_stays_on_cli(self):
        code, play, _ = self.run_main(["play", "fog_harbor"])
        play.assert_called_once_with("fog_harbor")


if __name__ == "__main__":
    unittest.main()
