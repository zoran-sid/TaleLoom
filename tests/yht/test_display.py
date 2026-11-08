"""YHT：可选展示字段（公开资源与素材）。"""

import json
import unittest
from pathlib import Path

from taleloom.legacy_session import LegacySession
from taleloom.loader import StoryFormatError, load_story, parse_story
from taleloom.model import Resource
from taleloom.ui_contract import ActionRequest
from taleloom.validator import format_report, validate
from tests.fixtures import mini_raw, mini_story
from tests.yht.tmp import temp_dir


def _display_raw(**overrides):
    raw = mini_raw()
    raw["vars"] = {"oxygen": 8}
    raw["resources"] = [{"var": "oxygen", "name": "氧气", "max": 8}]
    raw["assets"] = {"background": "assets/bg.png"}
    raw.update(overrides)
    return raw


class DisplayLoaderTest(unittest.TestCase):
    def test_parses_canonical_fields(self):
        story = parse_story(_display_raw())
        self.assertEqual([(r.var, r.name, r.maximum) for r in story.resources],
                         [("oxygen", "氧气", 8)])
        self.assertEqual(story.assets, {"background": "assets/bg.png"})
        self.assertIsNone(story.source_dir)

    def test_accepts_view_snapshot_aliases(self):
        raw = _display_raw(resources=[
            {"id": "oxygen", "label": "氧气", "maximum": 8},
        ])
        story = parse_story(raw)
        self.assertEqual((story.resources[0].var, story.resources[0].name,
                          story.resources[0].maximum), ("oxygen", "氧气", 8))

    def test_missing_fields_default_to_empty(self):
        raw = mini_raw()
        story = parse_story(raw)
        self.assertEqual(story.resources, [])
        self.assertEqual(story.assets, {})

    def test_load_story_records_source_directory(self):
        with temp_dir() as root:
            path = root / "story.json"
            path.write_text(json.dumps(_display_raw(), ensure_ascii=False), encoding="utf-8")
            story = load_story(path)
            self.assertEqual(Path(story.source_dir), root)

    def test_invalid_resources_report_field_paths(self):
        cases = [
            (r"resources\[0\]\.var", lambda r: r["resources"][0].pop("var")),
            (r"resources\[0\]\.name", lambda r: r["resources"][0].pop("name")),
            (r"resources\[0\]\.max", lambda r: r["resources"][0].update(max="8")),
            (r"resources\[0\]\.max", lambda r: r["resources"][0].update(max=0)),
            (r"resources\[0\]\.max", lambda r: r["resources"][0].update(max=True)),
            (r"resources\[0\]\.mystery",
             lambda r: r["resources"][0].update(mystery="x")),
            (r"resources\[0\]\.var",
             lambda r: r["resources"][0].update(id="oxygen")),
            (r"\$\.resources", lambda r: r.update(resources={})),
        ]
        for expected, mutate in cases:
            with self.subTest(path=expected):
                raw = _display_raw()
                mutate(raw)
                with self.assertRaisesRegex(StoryFormatError, expected):
                    parse_story(raw)

    def test_duplicate_public_variable_is_rejected(self):
        raw = _display_raw(resources=[
            {"var": "oxygen", "name": "氧气"},
            {"var": "oxygen", "name": "氧气2"},
        ])
        with self.assertRaisesRegex(StoryFormatError, r"resources\[1\]\.var: 公开资源变量重复"):
            parse_story(raw)

    def test_invalid_asset_paths_are_rejected(self):
        cases = [
            ("/abs.png", "绝对路径"),
            ("C:/abs.png", "绝对路径"),
            (r"a\b.png", "使用 / 分隔"),
            ("https://example.com/bg.png", "网址"),
            ("../bg.png", r"\.\.|路径"),
            ("a//b.png", "空段"),
            ("", "不能为空"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                raw = _display_raw(assets={"background": value})
                with self.assertRaisesRegex(StoryFormatError, expected):
                    parse_story(raw)

    def test_asset_role_must_be_non_empty(self):
        raw = _display_raw(assets={" ": "bg.png"})
        with self.assertRaisesRegex(StoryFormatError, "素材角色"):
            parse_story(raw)

    def test_assets_must_be_an_object(self):
        raw = _display_raw(assets=["bg.png"])
        with self.assertRaisesRegex(StoryFormatError, r"\$\.assets: 应为对象"):
            parse_story(raw)


class DisplayValidatorTest(unittest.TestCase):
    def test_missing_asset_is_a_warning(self):
        story = parse_story(_display_raw())
        story.source_dir = "does-not-exist"
        issues = validate(story)
        asset_issues = [i for i in issues if i.path == "assets.background"]
        self.assertEqual(len(asset_issues), 1)
        self.assertEqual(asset_issues[0].level, "warning")
        self.assertIn("素材文件不存在", asset_issues[0].message)

    def test_existing_asset_has_no_issue(self):
        with temp_dir() as root:
            (root / "assets").mkdir()
            (root / "assets" / "bg.png").write_bytes(b"png")
            path = root / "story.json"
            path.write_text(json.dumps(_display_raw(), ensure_ascii=False), encoding="utf-8")
            story = load_story(path)
            self.assertEqual(
                [i for i in validate(story) if i.path.startswith("assets")], []
            )

    def test_manual_invalid_resource_is_reported(self):
        story = mini_story()
        story.resources = [
            Resource("", "", 0),
            Resource("oxygen", "氧气", -1),
        ]
        issues = validate(story)
        paths = {i.path for i in issues if i.path.startswith("resources")}
        self.assertIn("resources[0].var", paths)
        self.assertIn("resources[0].name", paths)
        self.assertIn("resources[0].max", paths)
        self.assertIn("resources[1].max", paths)

    def test_display_issues_get_their_own_report_group(self):
        story = mini_story()
        story.resources = [Resource("", "氧气")]
        report = format_report(validate(story), story)
        self.assertIn("展示字段", report)
        self.assertIn("resources[0].var", report)


class LegacySessionDisplayTest(unittest.TestCase):
    def test_snapshot_exposes_resources_and_assets(self):
        raw = _display_raw()
        raw["scenes"][0]["choices"][0]["effects"] = [{"add_var": ["oxygen", -2]}]
        session = LegacySession(parse_story(raw))
        view = session.start().view
        self.assertEqual(len(view.resources), 1)
        resource = view.resources[0]
        self.assertEqual((resource.id, resource.label, resource.value, resource.maximum),
                         ("oxygen", "氧气", 8, 8))
        self.assertEqual(view.assets, {"background": "assets/bg.png"})

        result = session.dispatch(ActionRequest("choice:take", view.revision, {}))
        self.assertIsNone(result.error_code)
        self.assertEqual(result.view.resources[0].value, 6)

    def test_story_without_display_fields_has_empty_snapshot(self):
        view = LegacySession(mini_story()).start().view
        self.assertEqual(view.resources, [])
        self.assertEqual(view.assets, {})

    def test_mutating_view_assets_does_not_change_story(self):
        story = parse_story(_display_raw())
        view = LegacySession(story).start().view
        view.assets["background"] = "changed.png"
        self.assertEqual(LegacySession(story).start().view.assets,
                         {"background": "assets/bg.png"})


if __name__ == "__main__":
    unittest.main()
