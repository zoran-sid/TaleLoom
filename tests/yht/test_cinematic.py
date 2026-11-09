"""影像模式正式字段：结局类型、场景存档点与画面键。"""

from __future__ import annotations

import unittest

from taleloom.loader import StoryFormatError, parse_story
from taleloom.validator import validate
from tests.fixtures import mini_raw


def story_raw(*scenes, meta=None):
    """在迷你剧本的骨架上替换场景，并去掉与这些场景无关的物品。"""
    raw = mini_raw()
    raw["scenes"] = list(scenes)
    raw["items"] = []
    raw["meta"] = dict(meta or {})
    return raw


def scene(scene_id, *, choices=None, ending=None, checkpoint=None, art=None, on_enter=None):
    raw = {"id": scene_id, "text": f"{scene_id} 的正文。"}
    if choices is not None:
        raw["choices"] = choices
    if on_enter is not None:
        raw["on_enter"] = on_enter
    if ending is not None:
        raw["ending"] = ending
    if checkpoint is not None:
        raw["checkpoint"] = checkpoint
    if art is not None:
        raw["art"] = art
    return raw


def choice(choice_id, *, goto=None, effects=None):
    raw = {"id": choice_id, "text": choice_id}
    if goto is not None:
        raw["goto"] = goto
    if effects is not None:
        raw["effects"] = effects
    return raw


class LoaderCinematicFieldsTest(unittest.TestCase):
    def test_loads_checkpoint_art_and_ending_kind(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("go", goto="b")],
                  checkpoint="第一幕 · 门厅", art="lobby"),
            scene("b", ending={"id": "out", "title": "出门", "kind": "normal"}),
        ))
        self.assertEqual(story.scenes["a"].checkpoint, "第一幕 · 门厅")
        self.assertEqual(story.scenes["a"].art, "lobby")
        self.assertEqual(story.scenes["b"].ending["kind"], "normal")
        self.assertIsNone(story.scenes["b"].checkpoint)
        self.assertIsNone(story.scenes["b"].art)

    def test_old_story_keeps_optional_fields_empty(self):
        story = parse_story(mini_raw())
        self.assertIsNone(story.scenes["a"].checkpoint)
        self.assertIsNone(story.scenes["a"].art)
        self.assertNotIn("kind", story.scenes["b"].ending)

    def test_rejects_unknown_ending_kind(self):
        with self.assertRaisesRegex(StoryFormatError, r"ending\.kind"):
            parse_story(story_raw(
                scene("a", choices=[choice("go", goto="b")]),
                scene("b", ending={"id": "out", "kind": "bad"}),
            ))

    def test_rejects_non_string_checkpoint(self):
        with self.assertRaisesRegex(StoryFormatError, r"scenes\[0\]\.checkpoint"):
            parse_story(story_raw(scene("a", checkpoint=3)))

    def test_rejects_empty_checkpoint(self):
        with self.assertRaisesRegex(StoryFormatError, r"scenes\[0\]\.checkpoint"):
            parse_story(story_raw(scene("a", checkpoint="  ")))

    def test_rejects_non_string_art(self):
        with self.assertRaisesRegex(StoryFormatError, r"scenes\[0\]\.art"):
            parse_story(story_raw(scene("a", art=["lobby"])))

    def test_rejects_non_boolean_linear_meta(self):
        with self.assertRaisesRegex(StoryFormatError, r"meta\.linear"):
            parse_story(story_raw(scene("a"), meta={"linear": "true"}))


class ValidatorCinematicFieldsTest(unittest.TestCase):
    def test_duplicate_checkpoint_names_are_rejected(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("go", goto="b")], checkpoint="第一幕"),
            scene("b", ending={"id": "out"}, checkpoint="第一幕"),
        ))
        issues = validate(story)
        self.assertTrue(any(
            issue.level == "error" and issue.path == "scenes.b.checkpoint"
            and "存档点名称重复" in issue.message
            for issue in issues
        ), [str(issue) for issue in issues])

    def test_failure_ending_entered_by_choice_is_ok(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("go", goto="b")]),
            scene("b", ending={"id": "fail", "kind": "failure"}),
        ))
        self.assertEqual([str(issue) for issue in validate(story)], [])

    def test_failure_ending_entered_by_choice_effect_is_ok(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("go", effects=[{"goto": "b"}])]),
            scene("b", ending={"id": "fail", "kind": "failure"}),
        ))
        self.assertEqual([str(issue) for issue in validate(story)], [])

    def test_failure_ending_not_entered_by_choice_is_rejected(self):
        story = parse_story(story_raw(
            scene("a", on_enter=[{"goto": "b"}]),
            scene("b", ending={"id": "fail", "kind": "failure"}),
        ))
        issues = validate(story)
        self.assertTrue(any(
            issue.level == "error" and issue.path == "scenes.b.ending.kind"
            and "必须由选择进入" in issue.message
            for issue in issues
        ), [str(issue) for issue in issues])

    def test_invalid_ending_kind_in_constructed_story_is_rejected(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("go", goto="b")]),
            scene("b", ending={"id": "out", "kind": "normal"}),
        ))
        story.scenes["b"].ending["kind"] = "bad"
        issues = validate(story)
        self.assertTrue(any(
            issue.level == "error" and issue.path == "scenes.b.ending.kind"
            and "normal" in issue.message and "failure" in issue.message
            for issue in issues
        ), [str(issue) for issue in issues])

    def test_linear_story_with_cycle_is_rejected(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("again", goto="a"), choice("go", goto="c")]),
            scene("c", ending={"id": "out"}),
            meta={"linear": True},
        ))
        issues = validate(story)
        self.assertTrue(any(
            issue.level == "error" and issue.path == "meta.linear"
            and "回路" in issue.message
            for issue in issues
        ), [str(issue) for issue in issues])

    def test_cycle_is_allowed_without_linear_meta(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("again", goto="a"), choice("go", goto="c")]),
            scene("c", ending={"id": "out"}),
        ))
        issues = validate(story)
        self.assertFalse(any(issue.path == "meta.linear" for issue in issues),
                         [str(issue) for issue in issues])

    def test_acyclic_linear_story_is_ok(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("go", goto="b")]),
            scene("b", ending={"id": "out"}),
            meta={"linear": True},
        ))
        self.assertEqual([str(issue) for issue in validate(story)], [])

    def test_invalid_linear_type_in_constructed_story_is_rejected(self):
        story = parse_story(story_raw(
            scene("a", choices=[choice("go", goto="b")]),
            scene("b", ending={"id": "out"}),
        ))
        story.meta["linear"] = "true"
        issues = validate(story)
        self.assertTrue(any(
            issue.level == "error" and issue.path == "meta.linear"
            for issue in issues
        ), [str(issue) for issue in issues])


if __name__ == "__main__":
    unittest.main()
