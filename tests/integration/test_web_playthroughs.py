"""真实剧本的网页版适配与 CPython CLI 引擎逐步状态等价。"""
import unittest
from tools.web_vectors import build_vectors


class WebPlaythroughTest(unittest.TestCase):
    def test_all_walkthroughs_match_native_states_and_endings(self):
        vectors = build_vectors()
        self.assertGreaterEqual(len(vectors), 6)
        self.assertEqual({v['story_id'] for v in vectors}, {'fog_harbor', 'deep_space'})
