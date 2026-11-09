"""审阅 #17/#18 回归：正式模型、插件动作及独立随机事件。"""
import unittest
from taleloom.session import GameSession
from taleloom.rules import Context, default_registry
from taleloom.state import GameState
from tests.fixtures import mini_story

class ReviewTest(unittest.TestCase):
    def test_resources_and_assets_follow_shared_model(self):
        from taleloom.model import Resource
        story = mini_story(vars={'air': 7})
        story.resources = [Resource('air', '空气', 10)]
        story.assets = {'background': 'assets/room.png'}
        view = GameSession(story).start().view
        self.assertEqual(view.resources[0].value, 7)
        self.assertEqual(view.assets, story.assets)

    def test_no_hardcoded_oxygen(self):
        story = mini_story(vars={'oxygen': 9})
        story.id = 'deep_space'
        self.assertEqual(GameSession(story).start().view.resources, [])

    def test_graphical_text_removes_cli_hints(self):
        story = mini_story()
        story.scenes['a'].text = '房间。\n（输入“看”重读。）'
        self.assertEqual(GameSession(story).start().view.text, '房间。')

    def test_new_games_use_new_seeds_and_allow_explicit_seed(self):
        self.assertNotEqual(GameSession(mini_story()).engine.state.random_seed,
                            GameSession(mini_story()).engine.state.random_seed)
        self.assertEqual(GameSession(mini_story(), seed=52).engine.state.random_seed, 52)
        with self.assertRaises(ValueError):
            GameSession(mini_story(), seed=True)

    def test_independent_events_across_many_seeds(self):
        r, story = default_registry(), mini_story()
        joint = first = second = 0
        for seed in range(5000):
            ctx = Context(story, GameState('mini', 'a', random_seed=seed))
            a = r.check(ctx, {'chance': {'percent': 30, 'id': 'meteor'}})
            b = r.check(ctx, {'chance': {'percent': 70, 'id': 'battery'}})
            first += a; second += b; joint += a and b
        self.assertAlmostEqual(first/5000, .3, delta=.025)
        self.assertAlmostEqual(second/5000, .7, delta=.025)
        self.assertAlmostEqual(joint/5000, .21, delta=.025)

    def test_bad_new_mystery_save_fields_preserve_progress(self):
        import copy
        s = GameSession(mini_story())
        s.start()
        saved = s.export_save()
        for key, value in [('asked', 1), ('examined', 'bad'), ('act', [])]:
            bad = copy.deepcopy(saved)
            bad['state']['ext'] = {'mystery': {key: value}}
            self.assertEqual(s.restore(bad).error_code, 'invalid_save')
            self.assertEqual(s.export_save(), saved)
