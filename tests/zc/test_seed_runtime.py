"""校验 Seed Audio 运行映射的页面时间点；素材在 CI 中不重新生成。"""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "web" / "cinematic" / "seed-runtime.json"


class SeedRuntimeTests(unittest.TestCase):
    def test_scene_and_choice_cues_are_monotonic_and_inside_audio(self):
        runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
        for group in ("scenes", "choices"):
            for key, asset in runtime[group].items():
                with self.subTest(group=group, key=key):
                    cues = asset["cues"]
                    self.assertTrue(cues)
                    self.assertEqual(cues, sorted(cues))
                    self.assertTrue(all(0 < cue <= asset["duration"] for cue in cues))

    def test_ambience_files_are_mapped(self):
        runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
        self.assertEqual(set(runtime["ambience"]),
                         {"harbor", "lobby", "dinner", "office", "kitchen",
                          "dutyroom", "ledger", "rain", "attic", "tension"})


if __name__ == "__main__":
    unittest.main()
