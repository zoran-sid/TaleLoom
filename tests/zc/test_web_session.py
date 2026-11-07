"""浏览器 v0 兼容适配测试；只使用迷你剧本，不占用成员的正式模块。"""

import copy
import tempfile
import unittest
from pathlib import Path

from taleloom.save import load_game, save_game
from taleloom.ui_contract import ActionRequest
from tests.fixtures import mini_story
from tests.integration.test_ui_contract import SessionContractMixin
from web.runtime.legacy_session import LegacySession


class WebSessionTest(SessionContractMixin, unittest.TestCase):
    def make_session(self):
        return LegacySession(mini_story())

    def test_cli_save_roundtrip_and_restore_revision(self):
        session = self.make_session()
        session.start()
        session.dispatch(ActionRequest('choice:take', 0))
        saved = session.export_save()
        session.dispatch(ActionRequest('choice:open', 1))
        result = session.restore(saved)
        self.assertTrue(result.ok)
        self.assertGreater(result.view.revision, 2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'save.json'
            import json
            path.write_text(json.dumps(session.export_save()), encoding='utf-8')
            state, notes = load_game(path, mini_story())
            self.assertEqual(state.inventory, ['key'])
            self.assertEqual(notes, [])
            save_game(state, mini_story(), path)
            self.assertTrue(session.restore(json.loads(path.read_text())).ok)

    def test_malformed_save_is_transactional(self):
        session = self.make_session()
        before = session.start().view.to_dict()
        payload = session.export_save()
        mutations = [('turn', True), ('inventory', 'key'), ('vars', {'x': 'bad'}),
                     ('scene', 'missing'), ('story_id', 'other'), ('ext', []),
                     ('ext', {'mystery': {'clues': 'bad'}}), ('ending', 'missing')]
        for field, value in mutations:
            bad = copy.deepcopy(payload)
            bad['state'][field] = value
            with self.subTest(field=field, value=value):
                self.assertEqual(session.restore(bad).error_code, 'invalid_save')
                self.assertEqual(session.snapshot().to_dict(), before)

    def test_invalid_parameter_does_not_mutate_history(self):
        session = self.make_session()
        session.start()
        before = session.export_save()
        result = session.dispatch(ActionRequest('choice:take', 0, {'extra': 'value'}))
        self.assertEqual(result.error_code, 'invalid_parameters')
        self.assertEqual(session.export_save(), before)

    def test_snapshot_does_not_repeat_enter_effects(self):
        story = mini_story()
        story.scenes['a'].on_enter = [{'add_var': ['count', 1]}]
        session = LegacySession(story)
        session.start()
        for _ in range(3):
            session.start()
            session.snapshot()
        self.assertEqual(session.export_save()['state']['vars']['count'], 1)

    def test_hidden_clues_and_recipes_are_not_exposed(self):
        story = mini_story(mechanics=['puzzle', 'mystery'], clues={
            'secret': {'name': '答案', 'text': '不应显示'}
        })
        session = LegacySession(story)
        view = session.start().view
        self.assertEqual(view.clues, [])
        self.assertEqual(view.actions, [])

    def test_puzzle_parameters_are_inventory_not_recipe_answers(self):
        session = LegacySession(mini_story(mechanics=['puzzle']))
        session.start()
        view = session.dispatch(ActionRequest('choice:take', 0)).view
        self.assertEqual(view.actions[0].id, 'puzzle:use')
        self.assertEqual([x.id for x in view.actions[0].parameters[0].options], ['key'])
        before = session.export_save()
        result = session.dispatch(ActionRequest('puzzle:use', view.revision, {'item': 'hidden'}))
        self.assertEqual(result.error_code, 'invalid_parameters')
        self.assertEqual(session.export_save(), before)
