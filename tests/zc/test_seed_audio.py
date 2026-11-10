"""Timestamp alignment from Seed Audio subtitles to the displayed pages."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from seed_audio import clamp_cues, cue_times  # noqa: E402


class SeedAudioCuesTest(unittest.TestCase):
    def test_uses_word_timestamps_for_page_boundaries(self):
        job = {"pages": [{"text": "雨停了。"}, {"text": "船靠岸。"}]}
        subtitle = {"sentences": [{"words": [
            {"text": "雨停了", "end_time": 1300},
            {"text": "船靠岸", "end_time": 3400},
        ]}]}
        ratio, cues = cue_times(job, subtitle, 4.0)
        self.assertEqual(ratio, 1.0)
        self.assertEqual(cues, [1.3, 4.0])

    def test_missing_subtitle_is_not_released_as_synchronized_audio(self):
        self.assertEqual(cue_times({"pages": [{"text": "原文"}]}, None, 2.0), (0.0, []))

    def test_short_page_gets_minimum_dwell_time(self):
        self.assertEqual(clamp_cues([0.2, 0.4, 4.0], 4.0), [1.2, 2.4, 4.0])

    def test_last_cue_never_exceeds_duration(self):
        self.assertEqual(clamp_cues([1.0, 2.0], 2.0), [1.2, 2.0])


if __name__ == "__main__":
    unittest.main()
