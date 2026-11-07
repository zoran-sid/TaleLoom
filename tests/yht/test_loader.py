"""YHT：剧本加载。"""

import json
import unittest
from pathlib import Path

from taleloom.loader import StoryFormatError, load_story, parse_story
from tests.fixtures import STORIES, mini_raw
from tests.yht.tmp import temp_dir


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

    def test_format_version_must_be_integer(self):
        with self.assertRaisesRegex(StoryFormatError, r"\$\.format_version: 应为整数"):
            parse_story(mini_raw(format_version="1"))
        with self.assertRaisesRegex(StoryFormatError, r"\$\.format_version: 应为整数"):
            parse_story(mini_raw(format_version=True))

    def test_required_ids_must_not_be_empty(self):
        for path, mutate in [
            (r"\$\.id", lambda r: r.update(id="  ")),
            (r"\$\.start", lambda r: r.update(start="")),
            (r"scenes\[0\]\.id", lambda r: r["scenes"][0].update(id="")),
            (r"items\[0\]\.id", lambda r: r["items"][0].update(id="")),
        ]:
            with self.subTest(path=path):
                raw = mini_raw()
                mutate(raw)
                with self.assertRaisesRegex(StoryFormatError, path):
                    parse_story(raw)

    def test_typed_fields_report_exact_paths(self):
        cases = [
            (r"\$\.title", lambda r: r.update(title=1)),
            (r"scenes\[0\]\.title", lambda r: r["scenes"][0].update(title=1)),
            (r"scenes\[0\]\.choices\[0\]\.once",
             lambda r: r["scenes"][0]["choices"][0].update(once="yes")),
            (r"scenes\[0\]\.choices\[1\]\.goto",
             lambda r: r["scenes"][0]["choices"][1].update(goto=1)),
            (r"scenes\[0\]\.choices\[1\]\.message",
             lambda r: r["scenes"][0]["choices"][1].update(message=1)),
            (r"scenes\[0\]\.choices\[0\]\.aliases",
             lambda r: r["scenes"][0]["choices"][0].update(aliases=[1])),
            (r"items\[0\]\.description",
             lambda r: r["items"][0].update(description=1)),
            (r"items\[0\]\.aliases", lambda r: r["items"][0].update(aliases=[1])),
            (r"\$\.vars\.hp", lambda r: r.update(vars={"hp": "5"})),
            (r"\$\.vars\.hp", lambda r: r.update(vars={"hp": True})),
            (r"\$\.mechanics", lambda r: r.update(mechanics=[1])),
            (r"\$\.meta", lambda r: r.update(meta=[])),
        ]
        for path, mutate in cases:
            with self.subTest(path=path):
                raw = mini_raw()
                mutate(raw)
                with self.assertRaisesRegex(StoryFormatError, path):
                    parse_story(raw)

    def test_ending_requires_id_and_optional_title(self):
        raw = mini_raw()
        raw["scenes"][1]["ending"] = {}
        with self.assertRaisesRegex(StoryFormatError, r"scenes\[1\]\.ending\.id"):
            parse_story(raw)

        raw = mini_raw()
        raw["scenes"][1]["ending"] = {"id": "out", "title": 1}
        with self.assertRaisesRegex(StoryFormatError, r"scenes\[1\]\.ending\.title"):
            parse_story(raw)

        raw = mini_raw()
        raw["scenes"][1]["ending"] = {"id": "out"}
        self.assertEqual(parse_story(raw).scenes["b"].ending, {"id": "out"})

    def test_duplicate_item_id(self):
        raw = mini_raw()
        raw["items"].append({"id": "key", "name": "另一把钥匙"})
        with self.assertRaisesRegex(StoryFormatError, "物品 id 重复：key"):
            parse_story(raw)

    def test_duplicate_trigger_id(self):
        raw = mini_raw(triggers=[
            {"id": "same", "when": {"flag": "x"}, "effects": []},
            {"id": "same", "when": {"flag": "y"}, "effects": []},
        ])
        with self.assertRaisesRegex(StoryFormatError, "触发器 id 重复：same"):
            parse_story(raw)

    def test_trigger_once_must_be_boolean(self):
        raw = mini_raw(triggers=[{"id": "t", "when": {"flag": "x"}, "effects": [], "once": 0}])
        with self.assertRaisesRegex(StoryFormatError, r"triggers\[0\]\.once"):
            parse_story(raw)

    def test_trigger_id_must_be_string(self):
        raw = mini_raw(triggers=[{"id": 1, "when": {"flag": "x"}, "effects": []}])
        with self.assertRaisesRegex(StoryFormatError, r"triggers\[0\]\.id"):
            parse_story(raw)

    def test_scenes_must_not_be_empty(self):
        with self.assertRaisesRegex(StoryFormatError, "至少需要一个场景"):
            parse_story(mini_raw(scenes=[]))

    def test_root_must_be_object(self):
        with self.assertRaisesRegex(StoryFormatError, r"\$: 应为对象"):
            parse_story([])


class FileErrorsTest(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaisesRegex(StoryFormatError, "找不到剧本文件"):
            load_story("/nonexistent/story.json")

    def test_json_syntax_error_has_line_number_and_content(self):
        with temp_dir() as tmp:
            path = Path(tmp) / "story.json"
            path.write_text(
                '{\n  "id": "x",\n  "title": "y",\n  "bad": @\n}',
                encoding="utf-8",
            )   # 第 4 行是非法 token
            with self.assertRaises(StoryFormatError) as ctx:
                load_story(tmp)
            text = str(ctx.exception)
            self.assertIn("第 4 行", text)
            self.assertIn('"bad": @', text)
            self.assertIn("建议：", text)

    def test_roundtrip_through_file(self):
        with temp_dir() as tmp:
            Path(tmp, "story.json").write_text(
                json.dumps(mini_raw(), ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(load_story(tmp).title, "迷你剧本")


if __name__ == "__main__":
    unittest.main()
