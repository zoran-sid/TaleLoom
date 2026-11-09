"""LQ：剧本 B 的规格、固定种子回放与中途存读档。"""
import unittest
from pathlib import Path
from taleloom.loader import load_story
from taleloom.replay import load_walkthrough, walkthroughs_for, run_commands, check, ending_coverage
from taleloom.save import encode_save, decode_save
from taleloom.engine import Engine
from taleloom.parser import parse


class DeepSpaceCompleteTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parents[2] / 'stories/deep_space'
        self.story = load_story(self.path)

    def test_expansion_has_two_resources_targets_and_covered_endings(self):
        self.assertTrue(8 <= len(self.story.scenes) <= 12)
        self.assertEqual({r.var for r in self.story.resources}, {'oxygen', 'battery'})
        self.assertGreaterEqual(len(self.story.endings()), 3)
        self.assertTrue(self.story.data.get('targets'))
        results = [check(self.story, load_walkthrough(p)) for p in walkthroughs_for(self.path)]
        self.assertTrue(all(r.ok for r in results), [r.message for r in results])
        self.assertEqual(*ending_coverage(self.story, results))

    def test_saved_random_state_continues_exactly_the_same_route(self):
        wt = load_walkthrough(self.path / 'walkthroughs/truth.txt')
        full, _ = run_commands(self.story, wt.commands, seed=wt.seed)
        half = len(wt.commands) // 2
        partial, _ = run_commands(self.story, wt.commands[:half], seed=wt.seed)
        state, _ = decode_save(encode_save(partial.state, self.story), self.story)
        resumed = Engine(self.story, state)
        out = resumed.start()
        for text in wt.commands[half:]:
            out = resumed.handle(parse(text, out.choices, resumed.verb_aliases()))
        self.assertEqual(resumed.state.to_dict(), full.state.to_dict())
