"""LJ：通关脚本回放。"""

import tempfile
import unittest
from pathlib import Path

from taleloom import replay
from tests.fixtures import mini_story


class ReplayTest(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def test_parse_walkthrough(self):
        wt = replay.load_walkthrough(self.write("# 注释\n# expect: out\n\n捡起钥匙\n  开门  \n"))
        self.assertEqual(wt.commands, ["捡起钥匙", "开门"])
        self.assertEqual(wt.expect, "out")

    def test_check_success(self):
        result = replay.check(mini_story(), replay.Walkthrough("w", ["1", "开门"], "out"))
        self.assertTrue(result.ok, result.message)
        self.assertIn("> 开门", result.transcript)

    def test_check_reports_wrong_ending(self):
        result = replay.check(mini_story(), replay.Walkthrough("w", ["1"], "out"))
        self.assertFalse(result.ok)
        self.assertIn("未结束", result.message)

    def test_without_expectation_only_checks_running(self):
        self.assertTrue(replay.check(mini_story(), replay.Walkthrough("w", ["xyzzy"])).ok)

    def test_ending_coverage(self):
        story = mini_story()
        results = [replay.check(story, replay.Walkthrough("w", ["1", "开门"], "out"))]
        self.assertEqual(replay.ending_coverage(story, results), ({"out"}, {"out"}))


if __name__ == "__main__":
    unittest.main()
