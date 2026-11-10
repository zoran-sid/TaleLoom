"""LQ：桌面、兼容会话与正式会话共享的坏档防护。"""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from taleloom.engine import Engine
from taleloom.save import SaveError, encode_save, decode_save, save_game, load_game
from taleloom.session import GameSession
from taleloom.ui_contract import ActionRequest
from tests.fixtures import mini_story


class CodecTest(unittest.TestCase):
    def setUp(self):
        self.story = mini_story()
        self.session = GameSession(self.story, seed=12)
        self.session.start()
        self.payload = self.session.export_save()

    def test_bad_envelope_and_state_are_rejected_transactionally(self):
        mutations = [
            ('save_version', True), ('save_version', 9), ('story_id', 'other'),
            ('state', None), ('state.story_id', 'other'), ('state.scene', 'missing'),
            ('state.scene', []), ('state.turn', -1), ('state.turn', True),
            ('state.vars', []), ('state.vars', {'x': True}),
            ('state.inventory', ['missing']), ('state.inventory', 'key'),
            ('state.ending', 'out'), ('state.ext', []),
            ('state.ext', {'mystery': {'asked': 1}}),
            ('state.ext', {'mystery': {'examined': [None]}}),
            ('state.ext', {'mystery': {'clues': 'answer'}}),
            ('state.ext', {'mystery': {'act': 2}}),
            ('state.random_seed', True), ('state.random_seed', '12'),
            ('state.unknown', 1), ('state.ext', {'plugin': {'n': float('nan')}}),
        ]
        before = self.session.snapshot().to_dict()
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                bad = copy.deepcopy(self.payload)
                parts = field.split('.')
                target = bad if len(parts) == 1 else bad[parts[0]]
                target[parts[-1]] = value
                with self.assertRaises(SaveError):
                    decode_save(bad, self.story)
                self.assertEqual(self.session.restore(bad).error_code, 'invalid_save')
                self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_roundtrip_copies_data_and_preserves_seed(self):
        payload = encode_save(self.session.engine.state, self.story)
        state, notes = decode_save(payload, self.story)
        self.assertEqual(state, self.session.engine.state)
        self.assertEqual(notes, [])
        payload['state']['flags'].append('changed')
        state.flags.append('another')
        self.assertEqual(self.session.engine.state.flags, [])
        self.assertEqual(state.random_seed, 12)

    def test_invalid_unit_progress_in_current_or_nested_save_keeps_session(self):
        self.session.dispatch(ActionRequest('choice:take', self.session.snapshot().revision))
        before = self.session.export_save()
        for location in ('current', 'checkpoint', 'previous'):
            with self.subTest(location=location):
                bad = copy.deepcopy(before)
                state = bad['state']
                if location == 'checkpoint':
                    state = state['ext']['session']['checkpoints'][0]['state']
                elif location == 'previous':
                    state = state['ext']['session']['previous_choice']['state']
                state['ext']['mystery'] = {'units': {'lamp': {'tries': -1}}}
                result = self.session.restore(bad)
                self.assertEqual(result.error_code, 'invalid_save')
                self.assertEqual(self.session.export_save(), before)

    def test_old_v1_without_random_seed_defaults_to_zero(self):
        del self.payload['state']['random_seed']
        state, _ = decode_save(self.payload, self.story)
        self.assertEqual(state.random_seed, 0)

    def test_generated_seed_survives_javascript_number_roundtrip(self):
        for _ in range(10):
            session = GameSession(self.story)
            session.start()
            seed = session.export_save()['state']['random_seed']
            self.assertLessEqual(seed, 2 ** 53 - 1)
            self.assertEqual(int(float(seed)), seed)

    def test_missing_required_field_and_foreign_object(self):
        for field in ['save_version', 'story_id', 'state']:
            bad = copy.deepcopy(self.payload)
            del bad[field]
            with self.assertRaises(SaveError):
                decode_save(bad, self.story)
        self.payload['state']['scene'] = object()
        with self.assertRaises(SaveError):
            decode_save(self.payload, self.story)

    def test_fingerprint_change_stays_a_warning(self):
        self.payload['fingerprint'] = 'old'
        _, notes = decode_save(self.payload, self.story)
        self.assertTrue(notes and '修改' in notes[0])

    def test_both_directions_between_file_and_formal_session(self):
        self.session.dispatch(ActionRequest('choice:take', 0))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'save.json'
            save_game(self.session.engine.state, self.story, path)
            state, _ = load_game(path, self.story)
            result = self.session.restore(encode_save(state, self.story))
            self.assertTrue(result.ok)
            self.assertEqual(result.view.inventory[0].id, 'key')

    def test_file_write_failure_preserves_previous_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'save.json'
            save_game(self.session.engine.state, self.story, path)
            before = path.read_bytes()
            with patch('taleloom.save.os.replace', side_effect=OSError('full')):
                with self.assertRaises(SaveError):
                    save_game(self.session.engine.state, self.story, path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.iterdir()), [path])
