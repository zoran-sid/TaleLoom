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

    def test_fake_checkpoint_contract_supports_frontend_development(self):
        session = self.make_session()
        session.start()
        session.dispatch(ActionRequest('choice:take', 0))
        point = session.list_checkpoints()[0]
        result = session.restore_checkpoint(point.id, session.snapshot().revision)
        self.assertTrue(result.ok)
        self.assertEqual(result.view.turn, 0)
        self.assertEqual(result.view.checkpoint.id, point.id)
        self.assertEqual(result.view.rewinds, 1)
        self.assertEqual(result.view.rewinds_remaining, 3)
        saved = session.export_save()
        self.assertEqual(session.rewind(result.view.revision).error_code, 'rewind_unavailable')
        self.assertTrue(session.restore(saved).ok)
        self.assertEqual(session.snapshot().rewinds, 1)

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


class CheckpointContractTest(unittest.TestCase):
    """影像版共享会话约定；仅用小剧本，字段迁移由 YHT 另行处理。"""

    def make_session(self, **options):
        from taleloom.model import Choice, Scene, Story
        from taleloom.session_factory import create_session
        scenes = {
            'a': Scene('a', '开场', '起点', choices=[Choice('next', '继续', 'b')]),
            'b': Scene('b', '门口', '作出选择', choices=[
                Choice('bad', '冒险', 'fail'), Choice('next', '继续', 'c')],
                on_enter=[{'add_var': ['visits', 1]}]),
            'c': Scene('c', '终点前', '再选一次', choices=[Choice('end', '结束', 'end')]),
            'fail': Scene('fail', '失败', '失败了', ending={'id': 'bad', 'kind': 'failure'}),
            'end': Scene('end', '结局', '完成', ending={'id': 'out'}),
        }
        # 模拟 YHT 即将提供的 Scene 可选属性；不接管其加载／校验实现。
        scenes['b'].art = 'office'
        scenes['b'].checkpoint = '门口存档'
        scenes['c'].checkpoint = '终点存档'
        story = Story('checkpoint_demo', '回退样例', 'a', scenes, initial_vars={'visits': 0})
        return create_session(story, seed=42, **options)

    def act(self, session, name):
        result = session.dispatch(ActionRequest('choice:' + name, session.snapshot().revision))
        self.assertTrue(result.ok, result.messages)
        return result.view

    def test_optional_fields_keep_old_snapshot_construction_and_json(self):
        from taleloom.ui_contract import ViewSnapshot
        view = ViewSnapshot('old', '旧剧本', 'a', '开场', '正文')
        wire = json.loads(json.dumps(view.to_dict()))
        self.assertIsNone(wire['art'])
        self.assertIsNone(wire['ending_kind'])
        self.assertIsNone(wire['checkpoint'])
        self.assertEqual(wire['protocol_version'], 1)
        s = self.make_session()
        s.start()
        view = self.act(s, 'next')
        self.assertEqual(view.art, 'office')
        self.assertEqual(view.checkpoint.label, '门口存档')
        self.assertEqual(self.act(s, 'bad').ending_kind, 'failure')

    def test_checkpoint_list_is_visible_only_and_isolated(self):
        s = self.make_session()
        s.start()
        self.assertEqual([p.scene_id for p in s.list_checkpoints()], ['a'])
        self.act(s, 'next')
        points = s.list_checkpoints()
        self.assertEqual([p.scene_id for p in points], ['a', 'b'])
        points[-1].label = '篡改'
        points.clear()
        self.assertEqual(s.snapshot().checkpoint.label, '门口存档')
        self.assertEqual(len(s.list_checkpoints()), 2)

    def test_failure_rewind_restores_state_and_spends_one_of_three_chances(self):
        s = self.make_session()
        s.start()
        self.act(s, 'next')
        for used in range(1, 4):
            failed = self.act(s, 'bad')
            result = s.rewind(failed.revision)
            self.assertTrue(result.ok)
            self.assertEqual(result.view.scene_id, 'b')
            self.assertEqual(result.view.turn, 1)
            self.assertEqual(result.view.mistakes, used)
            self.assertEqual(result.view.rewinds_remaining, 3 - used)
            self.assertGreater(result.view.revision, failed.revision)
            self.assertEqual(s.export_save()['state']['vars']['visits'], 1)
        self.act(s, 'bad')
        before = s.export_save()
        self.assertEqual(s.rewind(s.snapshot().revision).error_code, 'rewind_exhausted')
        self.assertEqual(s.export_save(), before)

    def test_checkpoint_rewind_is_free_preserves_counts_and_discards_future(self):
        s = self.make_session()
        s.start()
        self.act(s, 'next')
        self.act(s, 'bad')
        s.rewind(s.snapshot().revision)
        self.act(s, 'next')
        discarded = s.list_checkpoints()[-1].id
        target = s.list_checkpoints()[1].id
        result = s.restore_checkpoint(target, s.snapshot().revision)
        self.assertTrue(result.ok)
        self.assertEqual(result.view.scene_id, 'b')
        self.assertEqual(result.view.mistakes, 1)
        self.assertEqual(result.view.rewinds, 1)
        self.assertEqual(result.view.rewinds_remaining, 2)
        self.assertEqual([p.scene_id for p in s.list_checkpoints()], ['a', 'b'])
        before = s.export_save()
        self.assertEqual(s.restore_checkpoint(discarded, result.view.revision).error_code, 'invalid_checkpoint')
        self.assertEqual(s.export_save(), before)

    def test_rewind_requests_validate_revision_and_preconditions_atomically(self):
        s = self.make_session()
        first = s.start().view
        self.assertEqual(s.rewind(first.revision).error_code, 'rewind_unavailable')
        self.act(s, 'next')
        failed = self.act(s, 'bad')
        before = s.export_save()
        self.assertEqual(s.rewind(first.revision).error_code, 'stale_revision')
        self.assertEqual(s.restore_checkpoint('a', True).error_code, 'stale_revision')
        self.assertEqual(s.export_save(), before)
        self.assertTrue(s.rewind(failed.revision).ok)
        self.assertEqual(s.rewind(failed.revision).error_code, 'stale_revision')
        self.assertEqual(s.rewind(s.snapshot().revision).error_code, 'rewind_unavailable')

    def test_save_roundtrip_preserves_counters_limit_and_rewind_targets(self):
        s = self.make_session(rewind_limit=1)
        s.start()
        self.act(s, 'next')
        self.act(s, 'bad')
        payload = json.loads(json.dumps(s.export_save()))
        other = self.make_session(rewind_limit=9)
        other.start()
        self.assertTrue(other.restore(payload).ok)
        self.assertEqual(other.snapshot().rewinds_remaining, 1)
        self.assertTrue(other.rewind(other.snapshot().revision).ok)
        self.assertTrue(other.restore_checkpoint('a', other.snapshot().revision).ok)
        saved = other.export_save()
        self.assertTrue(s.restore(saved).ok)
        self.assertEqual(s.snapshot().mistakes, 1)
        self.assertEqual(s.snapshot().rewinds, 1)
        self.assertEqual(s.snapshot().rewinds_remaining, 0)
        self.assertEqual(s.snapshot().rewind_limit, 1)

    def test_snapshot_and_checkpoint_reads_do_not_query_rules_or_draw_randomness(self):
        from unittest.mock import patch
        s = self.make_session()
        s.start()
        self.act(s, 'next')
        saved, view = s.export_save(), s.snapshot().to_dict()
        with patch('taleloom.rules.Registry.check', side_effect=AssertionError('不得查询规则')), \
                patch('secrets.randbits', side_effect=AssertionError('不得抽取随机数')):
            for _ in range(4):
                self.assertEqual(s.snapshot().to_dict(), view)
                s.list_checkpoints()
        self.assertEqual(s.export_save(), saved)

    def test_legacy_save_has_no_invented_past_and_keeps_configured_limit(self):
        from taleloom.save import encode_save
        s = self.make_session(rewind_limit=0)
        s.start()
        self.act(s, 'next')
        old = encode_save(s.engine.state, s.story)
        old['state']['ext'].pop('session', None)
        self.act(s, 'bad')
        self.assertTrue(s.restore(old).ok)
        self.assertEqual(s.snapshot().rewinds_remaining, 0)
        self.assertEqual([p.scene_id for p in s.list_checkpoints()], ['b'])
        self.assertEqual(s.rewind(s.snapshot().revision).error_code, 'rewind_unavailable')

    def test_invalid_configuration_is_rejected(self):
        for limit in (True, -1, 1.5, '3'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.make_session(rewind_limit=limit)
