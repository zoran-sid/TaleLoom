"""集成测试：真实剧本 + 全部模块。负责人：ZC（整合），剧本作者维护各自的通关脚本。

规则：
1. stories/ 下每个剧本必须通过校验（无 error）；
2. 每个通关脚本必须到达声明的结局；
3. 每个结局至少被一个通关脚本覆盖。
"""

import io
import unittest
from contextlib import redirect_stdout

import main
from taleloom import replay
from taleloom.loader import load_story
from taleloom.validator import errors, validate
from tests.fixtures import STORIES

STORY_DIRS = sorted(p.parent for p in STORIES.glob("*/story.json"))


class StoriesTest(unittest.TestCase):
    def test_two_stories_on_one_engine(self):
        stories = [load_story(d) for d in STORY_DIRS]
        self.assertGreaterEqual(len(stories), 2)
        self.assertGreaterEqual(len({tuple(s.mechanics) for s in stories}), 2, "两个剧本应展示不同的机制组合")

    def test_stories_validate(self):
        for d in STORY_DIRS:
            with self.subTest(story=d.name):
                self.assertEqual([str(i) for i in errors(validate(load_story(d)))], [])

    def test_walkthroughs_and_ending_coverage(self):
        for d in STORY_DIRS:
            story = load_story(d)
            results = []
            for path in replay.walkthroughs_for(d):
                with self.subTest(story=d.name, walkthrough=path.stem):
                    result = replay.check(story, replay.load_walkthrough(path))
                    results.append(result)
                    self.assertTrue(result.ok, result.message + "\n" + "\n".join(result.transcript))
            with self.subTest(story=d.name, check="coverage"):
                all_endings, covered = replay.ending_coverage(story, results)
                self.assertEqual(all_endings - covered, set(), "以上结局没有通关脚本覆盖")


class MainEntryTest(unittest.TestCase):
    def test_validate_command(self):
        with redirect_stdout(io.StringIO()) as buf:
            code = main.main(["validate"])
        self.assertEqual(code, 0, buf.getvalue())

    def test_unknown_story_name(self):
        with self.assertRaises(SystemExit):
            main.resolve("no_such_story")


if __name__ == "__main__":
    unittest.main()
