"""LQ：两个真实剧本的固定种子探索，随现有 integration CI 自动执行。"""
import unittest
from pathlib import Path
from taleloom.loader import load_story
from taleloom.replay import explore


class StoryExplorationTest(unittest.TestCase):
    def test_both_stories_remain_valid_during_fixed_seed_exploration(self):
        root = Path(__file__).resolve().parents[2]
        for name in ['deep_space', 'fog_harbor']:
            with self.subTest(story=name):
                results = explore(load_story(root / 'stories' / name), seed=6181, runs=12, steps=60)
                self.assertEqual(len(results), 12)
