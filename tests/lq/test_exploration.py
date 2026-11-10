"""LQ：探索器本身使用迷你数据，不读取真实剧本。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from taleloom import replay
from tests.fixtures import mini_story


class ExplorationTest(unittest.TestCase):
    def test_english_and_chinese_target_commands_map_to_the_same_action(self):
        from taleloom.parser import parse
        verbs = {'use_on': []}
        a = parse('use 扳手 on 控制面板', extra_verbs=verbs)
        b = parse('把 扳手 用在 控制面板 上', extra_verbs=verbs)
        self.assertEqual((a.verb, a.args), ('use_on', ['扳手', '控制面板']))
        self.assertEqual((a.verb, a.args), (b.verb, b.args))

    def test_same_seed_produces_the_same_routes_and_states(self):
        a = replay.explore(mini_story(), seed=7, runs=4, steps=20)
        b = replay.explore(mini_story(), seed=7, runs=4, steps=20)
        self.assertEqual(a, b)
        self.assertTrue(all(x.steps <= 20 for x in a))
        self.assertTrue(any(x.ending == 'out' for x in a))

    def test_maximum_steps_and_invalid_limits(self):
        results = replay.explore(mini_story(), runs=3, steps=1)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(x.steps <= 1 for x in results))
        for limits in [dict(steps=0), dict(runs=-1), dict(seed=True)]:
            with self.assertRaises(ValueError):
                replay.explore(mini_story(), **limits)

    def test_failure_reports_seed_and_route_instead_of_passing(self):
        with patch('taleloom.session.GameSession.dispatch', side_effect=RuntimeError('bug')):
            with self.assertRaisesRegex(replay.ExplorationError, 'seed=.*route='):
                replay.explore(mini_story(), seed=19)

    def test_walkthrough_parses_seed_and_rejects_bad_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'route.txt'
            p.write_text('# seed: 42\n# expect: out\n1\n开门\n', encoding='utf-8')
            wt = replay.load_walkthrough(p)
            self.assertEqual(wt.seed, 42)
            self.assertTrue(replay.check(mini_story(), wt).ok)
            p.write_text('# seed: bad\n1\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'seed'):
                replay.load_walkthrough(p)
