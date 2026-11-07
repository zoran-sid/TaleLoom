"""YHT：剧本加载。"""

import json
import tempfile
import unittest
from pathlib import Path

from taleloom.loader import StoryFormatError, load_story, parse_story
from tests.fixtures import STORIES, mini_raw


class LoadRealStoriesTest(unittest.TestCase):
    def test_every_story_directory_loads(self):
        dirs = sorted(p.parent for p in STORIES.glob("*/story.json"))
        self.assertGreaterEqual(len(dirs), 2, "至少要有两个剧本")
        for d in dirs:
            with self.subTest(story=d.name):
                story = load_story(d)
                self.assertIn(story.start, story.scenes)


class ParseTest(unittest.TestCase):
    def test_unknown_top_level_keys_go_to_data(self):
        story = parse_story(mini_raw(clues={"c1": {"name": "x"}}))
        self.assertEqual(story.data["clues"]["c1"]["name"], "x")

    def test_choice_id_defaults_to_position(self):
        raw = mini_raw()
        del raw["scenes"][0]["choices"][0]["id"]
        story = parse_story(raw)
        self.assertEqual(story.scenes["a"].choices[0].id, "c1")

    def test_missing_required_field_reports_path(self):
        raw = mini_raw()
        del raw["scenes"][1]["text"]
        with self.assertRaisesRegex(StoryFormatError, r"scenes\[1\]\.text"):
            parse_story(raw)

    def test_wrong_type_reports_path(self):
        with self.assertRaisesRegex(StoryFormatError, r"\$\.scenes: 应为数组"):
            parse_story(mini_raw(scenes={"a": {}}))

    def test_duplicate_scene_id(self):
        raw = mini_raw()
        raw["scenes"][1]["id"] = "a"
        with self.assertRaisesRegex(StoryFormatError, "场景 id 重复"):
            parse_story(raw)

    def test_effect_must_have_single_key(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][0]["effects"] = [{"give_item": "key", "say": "hi"}]
        with self.assertRaisesRegex(StoryFormatError, "只能有一个键"):
            parse_story(raw)

    def test_unsupported_format_version(self):
        with self.assertRaisesRegex(StoryFormatError, "format_version"):
            parse_story(mini_raw(format_version=99))


class FileErrorsTest(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaisesRegex(StoryFormatError, "找不到剧本文件"):
            load_story("/nonexistent/story.json")

    def test_json_syntax_error_has_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "story.json"
            path.write_text('{\n  "id": "x"\n  "title": "y"\n}', encoding="utf-8")   # 第 3 行前缺逗号
            with self.assertRaisesRegex(StoryFormatError, "第 3 行"):
                load_story(tmp)

    def test_roundtrip_through_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "story.json").write_text(json.dumps(mini_raw(), ensure_ascii=False), encoding="utf-8")
            self.assertEqual(load_story(tmp).title, "迷你剧本")


if __name__ == "__main__":
    unittest.main()
