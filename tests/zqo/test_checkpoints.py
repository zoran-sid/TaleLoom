"""ZQO：回退记录的边界、损坏存档与随机可复现性。"""

from copy import deepcopy
import unittest
from unittest.mock import patch

from taleloom.model import Choice, Scene
from taleloom.session import GameSession
from taleloom.ui_contract import ActionRequest
from tests.fixtures import mini_story


def make_session(limit=3):
    """迷你剧本增加一个临时标记存档点和可重复的失败选择。"""
    story = mini_story()
    story.scenes['a'].on_enter = [{'say': '【存档点】门厅'}]
    story.scenes['a'].choices.append(Choice('fail', '冒险', 'failure'))
    story.scenes['failure'] = Scene('failure', '失误', '失败', ending={'id': 'fail_test'})
    session = GameSession(story, seed=31, rewind_limit=limit)
    session.start()
    return session


def choose(session, name):
    """按最新版本提交测试动作。"""
    return session.dispatch(ActionRequest('choice:' + name, session.snapshot().revision))


class CheckpointBoundaryTest(unittest.TestCase):
    def test_legacy_markers_and_explicit_normal_override(self):
        s = make_session()
        self.assertEqual(s.list_checkpoints()[0].label, '门厅')
        self.assertEqual(choose(s, 'fail').view.ending_kind, 'failure')
        s = make_session()
        s.story.scenes['failure'].ending['kind'] = 'normal'
        self.assertEqual(choose(s, 'fail').view.ending_kind, 'normal')
        self.assertEqual(s.rewind(s.snapshot().revision).error_code, 'rewind_unavailable')

    def test_exhausted_game_can_still_restore_checkpoint_without_resetting_budget(self):
        s = make_session(0)
        choose(s, 'fail')
        self.assertEqual(s.rewind(s.snapshot().revision).error_code, 'rewind_exhausted')
        result = s.restore_checkpoint('a', s.snapshot().revision)
        self.assertTrue(result.ok)
        self.assertEqual(result.view.rewinds_remaining, 0)
        self.assertEqual(result.view.rewinds, 1)

    def test_random_failure_repeats_exact_state_after_rewind(self):
        s = make_session()
        s.story.scenes['failure'].variants = [{'when': {'chance': 50}, 'text': '随机文本'}]
        choose(s, 'take')
        first = choose(s, 'fail').view
        first_state = s.engine.state.to_dict()
        self.assertTrue(s.rewind(first.revision).ok)
        second = choose(s, 'fail').view
        self.assertEqual(first.text, second.text)
        self.assertEqual(s.engine.state.to_dict(), first_state)
        self.assertEqual(second.mistakes, 1)

    def test_revisiting_checkpoint_preserves_valid_previous_choice_record(self):
        s = make_session()
        s.story.scenes['b'].ending = None
        s.story.scenes['b'].checkpoint = '门后'
        s.story.scenes['b'].choices = [Choice('back', '回去', 'a')]
        choose(s, 'take')
        choose(s, 'open')
        choose(s, 'back')
        saved = s.export_save()
        self.assertTrue(s.restore(saved).ok)
        self.assertEqual([p.id for p in s.list_checkpoints()], ['a'])
        choose(s, 'fail')
        self.assertTrue(s.rewind(s.snapshot().revision).ok)
        self.assertTrue(s.restore(s.export_save()).ok)

    def test_corrupt_history_is_rejected_atomically_including_nested_states(self):
        s = make_session()
        choose(s, 'fail')
        good = s.export_save()
        mutations = [
            lambda h: h.update(version=True),
            lambda h: h.update(rewind_limit=-1),
            lambda h: h.update(mistakes=True),
            lambda h: h.update(mistakes=4),
            lambda h: h.update(rewinds=-1),
            lambda h: h.update(checkpoints={}),
            lambda h: h['checkpoints'].append(deepcopy(h['checkpoints'][0])),
            lambda h: h['checkpoints'][0].update(id='missing'),
            lambda h: h['checkpoints'][0].update(label=''),
            lambda h: h['checkpoints'][0]['state'].update(scene='missing'),
            lambda h: h['checkpoints'][0]['state'].update(turn=100),
            lambda h: h['checkpoints'][0]['state'].update(random_seed=123),
            lambda h: h['checkpoints'][0]['state']['ext'].update(session={}),
            lambda h: h['previous_choice']['state'].update(turn=-1),
            lambda h: h['previous_choice']['state'].update(story_id='other'),
            lambda h: h['previous_choice'].update(checkpoints='bad'),
            lambda h: h.pop('previous_choice'),
        ]
        for mutate in mutations:
            bad = deepcopy(good)
            mutate(bad['state']['ext']['session'])
            before = s.snapshot().to_dict()
            with self.subTest(mutation=mutate):
                self.assertEqual(s.restore(bad).error_code, 'invalid_save')
                self.assertEqual(s.export_save(), good)
                self.assertEqual(s.snapshot().to_dict(), before)

    def test_restore_and_rewind_failure_leave_revision_history_and_budget_unchanged(self):
        s = make_session()
        choose(s, 'fail')
        good, view = s.export_save(), s.snapshot().to_dict()
        with patch('taleloom.presentation.build_snapshot', side_effect=ValueError('损坏字段')):
            self.assertFalse(s.restore(good).ok)
            self.assertFalse(s.rewind(view['revision']).ok)
            self.assertFalse(s.restore_checkpoint('a', view['revision']).ok)
        self.assertEqual(s.export_save(), good)
        self.assertEqual(s.snapshot().to_dict(), view)

    def test_invalid_dispatch_does_not_replace_last_choice_or_spend_chances(self):
        s = make_session()
        choose(s, 'fail')
        before = s.export_save()
        self.assertFalse(choose(s, 'missing').ok)
        self.assertEqual(s.export_save(), before)
        self.assertTrue(s.rewind(s.snapshot().revision).ok)

    def test_save_and_restore_do_not_share_nested_history_references(self):
        s = make_session()
        choose(s, 'fail')
        good = s.export_save()
        self.assertTrue(s.restore(good).ok)
        good['state']['ext']['session']['previous_choice']['state']['vars']['injected'] = 1
        self.assertTrue(s.rewind(s.snapshot().revision).ok)
        self.assertNotIn('injected', s.engine.state.vars)
