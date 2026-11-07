"""跨模块接口样例验收，不读取 stories，也不启动窗口或浏览器。"""

import json
import unittest

from taleloom.ui_contract import ActionRequest, GameSession, SaveStore, StorageError
from tests.ui_fakes import FakeGameSession, MemorySaveStore


class SessionContractMixin:
    """真实适配器可复用这些行为断言，提供包含 take/open 动作的迷你会话。"""

    def make_session(self):
        raise NotImplementedError

    def test_snapshot_reads_do_not_change_state_or_revision(self):
        session = self.make_session()
        first = session.start().view.to_dict()
        self.assertEqual(session.snapshot().to_dict(), first)
        self.assertEqual(session.snapshot().to_dict(), first)
        self.assertEqual(session.start().view.to_dict(), first)

    def test_mutating_returned_view_does_not_change_session(self):
        session = self.make_session()
        view = session.start().view
        view.choices.clear()
        view.assets['background'] = 'changed.png'
        self.assertTrue(session.snapshot().choices)
        self.assertEqual(session.snapshot().assets, {})

    def test_stale_action_is_rejected_without_advancing(self):
        session = self.make_session()
        revision = session.start().view.revision
        result = session.dispatch(ActionRequest('choice:take', revision))
        self.assertTrue(result.ok)
        before = session.snapshot().to_dict()
        stale = session.dispatch(ActionRequest('choice:open', revision))
        self.assertEqual(stale.error_code, 'stale_revision')
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_unknown_action_preserves_state(self):
        session = self.make_session()
        before = session.start().view.to_dict()
        result = session.dispatch(ActionRequest('missing', before['revision']))
        self.assertEqual(result.error_code, 'invalid_action')
        self.assertEqual(result.view.to_dict(), before)


class FakeSessionTest(SessionContractMixin, unittest.TestCase):
    def make_session(self):
        return FakeGameSession()

    def test_protocol_and_json_wire_format(self):
        session = self.make_session()
        self.assertIsInstance(session, GameSession)
        result = session.start()
        wire = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
        self.assertEqual(wire['view']['protocol_version'], 1)
        self.assertEqual(wire['view']['choices'][0]['id'], 'choice:take')
        self.assertEqual(wire['error_code'], None)

    def test_parameter_action_uses_item_id_and_reaches_ending(self):
        session = self.make_session()
        session.start()
        taken = session.dispatch(ActionRequest('choice:take', 0)).view
        self.assertEqual(taken.inventory[0].id, 'key')
        parameter = taken.actions[0].parameters[0]
        self.assertEqual(parameter.options[0].id, 'key')
        invalid = session.dispatch(ActionRequest('puzzle:use', 1, {'item': 'unknown'}))
        self.assertEqual(invalid.error_code, 'invalid_parameters')
        end = session.dispatch(ActionRequest('puzzle:use', 1, {'item': 'key'}))
        self.assertTrue(end.view.ended)
        self.assertEqual(end.view.ending_id, 'out')
        self.assertEqual(end.view.choices, [])
        self.assertEqual(end.view.actions, [])

    def test_restore_invalidates_old_actions_and_preserves_progress(self):
        session = self.make_session()
        session.start()
        session.dispatch(ActionRequest('choice:take', 0))
        saved = session.export_save()
        session.dispatch(ActionRequest('choice:open', 1))
        restored = session.restore(saved)
        self.assertTrue(restored.ok)
        self.assertFalse(restored.view.ended)
        self.assertEqual(restored.view.turn, 1)
        self.assertGreater(restored.view.revision, 2)
        self.assertEqual(restored.view.inventory[0].id, 'key')

    def test_bad_restore_preserves_current_game(self):
        session = self.make_session()
        before = session.start().view.to_dict()
        for payload in ({}, {'fixture': 'ui_demo', 'step': 9}, {'fixture': 'ui_demo', 'step': True}):
            result = session.restore(payload)
            self.assertEqual(result.error_code, 'invalid_save')
            self.assertEqual(session.snapshot().to_dict(), before)


class MemoryStoreTest(unittest.TestCase):
    def test_slots_and_payloads_are_isolated_copies(self):
        store = MemorySaveStore()
        self.assertIsInstance(store, SaveStore)
        payload = {'state': {'turn': 2}}
        store.write('slot-1', payload)
        payload['state']['turn'] = 99
        copy = store.read('slot-1')
        copy['state']['turn'] = 100
        self.assertEqual(store.read('slot-1')['state']['turn'], 2)
        self.assertEqual(store.list_slots(), ['slot-1'])

    def test_missing_slot_has_a_storage_error(self):
        with self.assertRaises(StorageError):
            MemorySaveStore().read('missing')
