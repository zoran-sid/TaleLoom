"""ZRS：命令解析（含 parser.py 中的 doctest）。"""

import doctest
import unittest

from taleloom import parser
from taleloom.parser import parse

CHOICES = [(1, "去账房查看现场"), (2, "去后厨找阿芸"), (3, "回到大堂")]
MYSTERY = {"accuse": ["指认", "accuse"], "clues": ["线索"]}


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(parser))
    return tests


class ParserTest(unittest.TestCase):
    def test_empty_and_whitespace_are_noop(self):
        for text in ("", "   ", "　"):
            self.assertEqual(parse(text).verb, "noop")

    def test_fullwidth_digit_selects_choice(self):
        cmd = parse("２", CHOICES)
        self.assertEqual((cmd.verb, cmd.args), ("choose", ["2"]))

    def test_builtin_verbs_in_both_languages(self):
        for text, verb in [("look", "look"), ("看", "look"), ("I", "inventory"), ("背包", "inventory"),
                           ("存档", "save"), ("load", "load"), ("退出", "quit"), ("?", "help")]:
            with self.subTest(text=text):
                self.assertEqual(parse(text).verb, verb)

    def test_exact_choice_text(self):
        self.assertEqual(parse("回到大堂", CHOICES).args, ["3"])

    def test_unique_substring_of_choice(self):
        self.assertEqual(parse("后厨", CHOICES).args, ["2"])

    def test_ambiguous_substring_is_unknown(self):
        self.assertEqual(parse("去", CHOICES).verb, "unknown")       # 单字不做模糊匹配
        self.assertEqual(parse("大堂查看", CHOICES).verb, "unknown")

    def test_plugin_verbs_with_and_without_space(self):
        self.assertEqual(parse("指认 顾先生", extra_verbs=MYSTERY).args, ["顾先生"])
        cmd = parse("指认顾先生", extra_verbs=MYSTERY)
        self.assertEqual((cmd.verb, cmd.args), ("accuse", ["顾先生"]))
        self.assertEqual(parse("ACCUSE gu", extra_verbs=MYSTERY).args, ["gu"])

    def test_plugin_verb_unknown_without_plugin(self):
        self.assertEqual(parse("指认 顾先生").verb, "unknown")

    def test_raw_text_is_kept(self):
        self.assertEqual(parse("  Look ").raw, "  Look ")


PUZZLE = {"use": ["使用", "用", "use"], "use_on": [], "combine": ["组合", "combine"]}


class UseOnParsingTest(unittest.TestCase):
    def test_use_a_on_b_with_and_without_spaces(self):
        for text in ("把 扳手 用在 控制面板 上", "把扳手用在控制面板上", "扳手用在控制面板上"):
            with self.subTest(text=text):
                self.assertEqual(parse(text, extra_verbs=PUZZLE).args, ["扳手", "控制面板"])
                self.assertEqual(parse(text, extra_verbs=PUZZLE).verb, "use_on")

    def test_missing_trailing_shang_is_tolerated(self):
        self.assertEqual(parse("把 木棍 用在 砖墙", extra_verbs=PUZZLE).args, ["木棍", "砖墙"])

    def test_particles_around_item_are_trimmed(self):
        self.assertEqual(parse("把 扳手用在 panel 上", extra_verbs=PUZZLE).args, ["扳手", "panel"])

    def test_plain_use_is_not_taken_as_use_on(self):
        self.assertEqual(parse("用 扳手", extra_verbs=PUZZLE).verb, "use")
        self.assertEqual(parse("使用 提灯", extra_verbs=PUZZLE).args, ["提灯"])

    def test_sentence_needs_puzzle_plugin(self):
        self.assertEqual(parse("把 扳手 用在 控制面板 上").verb, "unknown")


if __name__ == "__main__":
    unittest.main()
