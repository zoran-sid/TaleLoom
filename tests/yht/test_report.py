"""YHT：可读的校验报告。"""

import unittest

from taleloom.loader import parse_story
from taleloom.validator import format_report, validate
from tests.fixtures import mini_raw, mini_story


class ReportTest(unittest.TestCase):
    def test_clean_story_has_empty_report(self):
        self.assertEqual(format_report([], mini_story()), "")

    def test_groups_scene_issues_in_story_order_and_keeps_suggestions(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["goto"] = "nowhere"
        raw["items"].append({"id": "ghost", "name": "幽灵"})
        story = parse_story(raw)
        report = format_report(validate(story), story)
        self.assertIn("场景 a《门厅》", report)
        self.assertIn("建议：", report)
        self.assertIn("items.ghost", report)
        self.assertLess(report.index("场景 a《门厅》"), report.index("物品"))

    def test_global_issue_group(self):
        story = mini_story(start="zzz")
        report = format_report(validate(story), story)
        self.assertIn("开始与全局", report)
        self.assertIn("起始场景不存在：zzz", report)

    def test_report_is_gbk_safe(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["goto"] = "nowhere"
        story = parse_story(raw)
        report = format_report(validate(story), story)
        report.encode("gbk")   # 不应抛出 UnicodeEncodeError

    def test_errors_come_before_warnings_in_a_group(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["goto"] = "nowhere"
        raw["scenes"][0]["choices"][0]["effects"] = [{"give_item": "ghost"}]
        story = parse_story(raw)
        report = format_report(validate(story), story)
        first_error = report.index("[error]")
        first_warning = report.find("[warning]")
        self.assertTrue(first_warning == -1 or first_error < first_warning)


if __name__ == "__main__":
    unittest.main()
