"""ZRS：命令行界面。用脚本化输入代替键盘，检查不会崩溃且反馈清楚。"""

import tempfile
import unittest
from pathlib import Path

from taleloom.cli import play
from tests.fixtures import mini_story


class FakeIO:
    def __init__(self, inputs):
        self.inputs = list(inputs)
        self.lines = []

    def input(self, prompt):
        if not self.inputs:
            raise EOFError
        return self.inputs.pop(0)

    def print(self, text=""):
        self.lines.append(text)

    @property
    def text(self):
        return "\n".join(self.lines)


class CliTest(unittest.TestCase):
    def play(self, inputs, save_path=None):
        io = FakeIO(inputs)
        with tempfile.TemporaryDirectory() as tmp:
            play(mini_story(), save_path or Path(tmp) / "s.json", io.input, io.print)
        return io

    def test_menu_is_numbered(self):
        self.assertIn("  [1] 捡起钥匙", self.play(["q"]).lines)

    def test_full_playthrough(self):
        io = self.play(["1", "开门", "q"])
        self.assertIn("【结局】出门", io.text)
        self.assertIn("故事结束", io.text)

    def test_invalid_input_does_not_crash(self):
        io = self.play(["xyzzy", "99", "", "q"])
        self.assertIn("无法理解", io.text)
        self.assertIn("没有编号为“99”的选项。", io.text)

    def test_eof_exits_cleanly(self):
        self.assertIn("再见。", self.play([]).text)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            io = self.play(["1", "存档", "读档", "背包", "q"], save_path=path)
        self.assertIn("已存档", io.text)
        self.assertIn("继续游戏", io.text)
        self.assertIn("  · 钥匙", io.text)

    def test_load_without_save_reports_error(self):
        self.assertIn("读档失败", self.play(["读档", "q"]).text)


if __name__ == "__main__":
    unittest.main()
