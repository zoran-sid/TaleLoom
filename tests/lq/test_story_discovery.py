"""LQ：探索目录用临时文件构造，覆盖影像层级而不读真实剧本。"""
import tempfile
import unittest
from pathlib import Path
from taleloom.replay import story_files


class StoryDiscoveryTest(unittest.TestCase):
    def test_exploration_lists_regular_and_film_stories_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = ['deep_space/story.json', 'film/deep_space_film/story.json',
                        'film/fog_harbor_film/story.json']
            for relative in expected + ['assets/not-a-story.json']:
                p = root / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('{}')
            self.assertEqual([p.relative_to(root).as_posix() for p in story_files(root)], expected)
            self.assertEqual(len(story_files(root / 'film')), 2)

    def test_missing_directory_is_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(story_files(Path(folder) / 'missing'), [])
