"""校验八条旧整场录音的逐页时间点；对齐由 Whisper 转写与剧本原文生成。"""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CUES = ROOT / "web" / "cinematic" / "legacy-cues.json"

EXPECTED_PAGES = {
    "p01_dock": 10,
    "p02_lobby": 12,
    "p03_dinner": 14,
    "p04_office": 13,
    "a01_found": 13,
    "a02_door": 12,
    "a03_lamp": 12,
    "a04_window": 10,
}


class LegacyCueTests(unittest.TestCase):
    def test_every_old_scene_has_one_cue_per_page(self):
        scenes = json.loads(CUES.read_text(encoding="utf-8"))["scenes"]
        self.assertEqual(set(scenes), set(EXPECTED_PAGES))
        for scene_id, count in EXPECTED_PAGES.items():
            with self.subTest(scene=scene_id):
                self.assertEqual(len(scenes[scene_id]["cues"]), count)

    def test_cues_are_monotonic_and_inside_the_audio(self):
        scenes = json.loads(CUES.read_text(encoding="utf-8"))["scenes"]
        for scene_id, asset in scenes.items():
            with self.subTest(scene=scene_id):
                cues = asset["cues"]
                self.assertEqual(cues, sorted(cues))
                self.assertTrue(all(0 < cue <= asset["duration"] for cue in cues))
                self.assertGreaterEqual(asset["duration"] - cues[-1], 0)

    def test_old_audio_files_exist(self):
        scenes = json.loads(CUES.read_text(encoding="utf-8"))["scenes"]
        for asset in scenes.values():
            self.assertTrue((ROOT / "web" / "cinematic" / "audio" / asset["file"]).is_file())


if __name__ == "__main__":
    unittest.main()
