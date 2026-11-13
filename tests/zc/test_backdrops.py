"""ZC：影像版场景镜头的映射与素材。

每个影像版场景都要映射到一个镜头；镜头要么是已有转场的静帧，要么在 MiniMax 镜头清单里。
已生成的镜头必须同时有循环视频、静帧和清单记录；尚未生成的镜头由播放器退回代码画面。
"""

import hashlib
import json
import unittest

from tests.fixtures import ROOT, STORIES

MEDIA = ROOT / "web" / "cinematic" / "media"
TABLE = json.loads((ROOT / "web" / "cinematic" / "backdrops.json").read_text(encoding="utf-8"))
PLAN = json.loads((ROOT / "tools" / "minimax_shots.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((MEDIA / "manifest.json").read_text(encoding="utf-8"))


class BackdropTest(unittest.TestCase):
    def test_every_film_scene_has_a_clip(self):
        for story_dir in sorted((STORIES / "film").glob("*/story.json")):
            story = json.loads(story_dir.read_text(encoding="utf-8"))
            table = TABLE["stories"].get(story["id"], {})
            scenes = [scene["id"] for scene in story["scenes"]]
            with self.subTest(story=story["id"]):
                self.assertEqual([s for s in scenes if s not in table], [], "没有镜头的场景")
                self.assertEqual([s for s in table if s not in scenes], [], "映射里多出的场景")

    def test_clips_are_known_stills_or_planned_shots(self):
        planned = {shot["id"] for shot in PLAN["shots"]}
        used = {clip for table in TABLE["stories"].values() for clip in table.values()}
        self.assertEqual(sorted(used - planned - set(TABLE["stills"])), [])
        self.assertEqual(sorted(planned - used), [], "清单里没有被任何场景使用的镜头")

    def test_alternates_point_to_existing_footage(self):
        planned = {shot["id"] for shot in PLAN["shots"]}
        for missing, substitute in TABLE["alternates"].items():
            with self.subTest(clip=missing):
                self.assertIn(missing, planned)
                self.assertTrue((MEDIA / f"{substitute}.jpg").exists(), "替代镜头必须已有静帧")

    def test_stills_keep_their_transition_and_last_frame(self):
        for clip in TABLE["stills"]:
            with self.subTest(clip=clip):
                self.assertTrue((MEDIA / f"{clip}.mp4").exists())
                self.assertTrue((MEDIA / f"{clip}.jpg").exists())

    def test_generated_shots_have_loop_poster_and_record(self):
        for shot in PLAN["shots"]:
            video = MEDIA / f"{shot['id']}.mp4"
            if not video.exists():
                continue  # 尚未生成：播放器用代码画面
            with self.subTest(shot=shot["id"]):
                record = MANIFEST["shots"][shot["id"]]
                self.assertTrue((MEDIA / record["poster"]).exists())
                self.assertEqual(record["sha256"], hashlib.sha256(video.read_bytes()).hexdigest())
                self.assertTrue(record["task_id"] and record["prompt"] and record["cost_cny"] > 0)
                self.assertLess(video.stat().st_size, 2_000_000, "循环镜头应控制在 2 MB 内")

    def test_manifest_spend_matches_records(self):
        total = sum(r["cost_cny"] for r in MANIFEST["shots"].values()) + sum(r["cost_cny"] for r in MANIFEST["rejected"])
        self.assertAlmostEqual(MANIFEST["spent_cny"], total, places=2)

    def test_prompts_never_contain_credentials(self):
        text = json.dumps(MANIFEST, ensure_ascii=False) + json.dumps(PLAN, ensure_ascii=False)
        for marker in ("sk-api-", "fal_sk_", "Bearer "):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
