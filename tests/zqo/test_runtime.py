"""正式会话与核心扩展的行为测试；仅使用迷你剧本。"""
import copy
import json
import unittest

from tests.fixtures import mini_raw, mini_story
from tests.integration.test_ui_contract import SessionContractMixin
from taleloom.loader import parse_story, StoryFormatError
from taleloom.model import Command
from taleloom.engine import Engine
from taleloom.rules import Context, RuleError, default_registry
from taleloom.state import GameState
from taleloom.session import GameSession


class SessionTest(SessionContractMixin, unittest.TestCase):
    def make_session(self):
        return GameSession(mini_story())

    def test_requires_start(self):
        from taleloom.ui_contract import ActionRequest
        with self.assertRaises(RuntimeError):
            self.make_session().dispatch(ActionRequest('choice:take', 0))

    def test_bad_rule_rolls_back_all_state(self):
        from taleloom.ui_contract import ActionRequest
        story = mini_story()
        story.scenes['a'].choices[0].effects += [{'unknown': 1}]
        s = GameSession(story)
        s.start()
        before = s.export_save()
        result = s.dispatch(ActionRequest('choice:take', 0))
        self.assertFalse(result.ok)
        self.assertEqual(s.export_save(), before)
        self.assertEqual(s.snapshot().revision, 0)

    def test_noop_plugin_preserves_state_and_revision(self):
        from taleloom.ui_contract import ActionRequest
        s = GameSession(mini_story(mechanics=['puzzle']))
        s.start()
        s.dispatch(ActionRequest('choice:take', 0))
        before = s.export_save()
        result = s.dispatch(ActionRequest('puzzle:use', 1, {'item': 'key'}))
        self.assertEqual(result.view.revision, 1)
        self.assertEqual(s.export_save(), before)
        self.assertTrue(result.messages)

    def test_restore_is_atomic_and_invalidates_old_actions(self):
        from taleloom.ui_contract import ActionRequest
        s = self.make_session()
        s.start()
        saved = s.export_save()
        s.dispatch(ActionRequest('choice:take', 0))
        before = s.snapshot().to_dict()
        for field, value in [('random_seed', True), ('turn', -1), ('inventory', ['missing'])]:
            bad = copy.deepcopy(saved)
            bad['state'][field] = value
            self.assertEqual(s.restore(bad).error_code, 'invalid_save')
            self.assertEqual(s.snapshot().to_dict(), before)
        self.assertTrue(s.restore(saved).ok)
        self.assertGreater(s.snapshot().revision, before['revision'])

    def test_optional_and_text_plugin_parameters(self):
        from taleloom.mechanics.base import Mechanic
        from taleloom.ui_contract import ActionSpec, ActionParameter, ActionRequest
        class Note(Mechanic):
            name = 'note'
            verbs = {'write': ['write']}
            def actions(self, engine):
                return [ActionSpec('note:write', '记录', [ActionParameter('text', '文字', kind='text'), ActionParameter('extra', '补充', kind='text', required=False)])]
            def handle(self, engine, cmd, ctx):
                ctx.state.set_flag(cmd.args[0])
                return True
        s = self.make_session()
        s.engine.mechanics['note'] = Note()
        s.start()
        result = s.dispatch(ActionRequest('note:write', 0, {'text': '笔记'}))
        self.assertTrue(result.ok)
        self.assertIn('笔记', s.engine.state.flags)


class PresentationTest(unittest.TestCase):
    def test_interpolation_and_variants_in_cli_and_session(self):
        raw = mini_raw(vars={'oxygen': 5})
        raw['scenes'][0]['text'] = '氧气{vars.oxygen}，物品{item:key}，{missing}'
        raw['scenes'][0]['variants'] = [{'when': {'has_item': 'key'}, 'text': '已取得{item:key}', 'mode': 'replace'}]
        story = parse_story(raw)
        e = Engine(story)
        self.assertIn('氧气5，物品钥匙，【未知占位符：missing】', e.start().lines)
        e.handle(Command('choose', ['take']))
        self.assertIn('已取得钥匙', e.handle(Command('look')).lines)
        s = GameSession(story)
        self.assertIn('氧气5', s.start().view.text)

    def test_bad_variant_rejected_with_location(self):
        for variant in [{'text': 3}, {'text': 'x', 'mode': 'bad'}, 'bad']:
            raw = mini_raw()
            raw['scenes'][0]['variants'] = [variant]
            with self.assertRaisesRegex(StoryFormatError, 'variants'):
                parse_story(raw)

    def test_append_variant(self):
        raw = mini_raw()
        raw['scenes'][0]['variants'] = [{'text': '追加说明'}]
        self.assertIn('追加说明', GameSession(parse_story(raw)).start().view.text)


class ChanceTest(unittest.TestCase):
    def test_boundaries_invalid_values_and_pure_reads(self):
        r = default_registry()
        ctx = Context(mini_story(), GameState('mini', 'a'))
        self.assertFalse(r.check(ctx, {'chance': 0}))
        self.assertTrue(r.check(ctx, {'chance': 100}))
        before = ctx.state.to_dict()
        a = r.check(ctx, {'chance': 30})
        self.assertEqual(r.check(ctx, {'chance': 30}), a)
        self.assertEqual(ctx.state.to_dict(), before)
        for value in [-1, 101, True, '30', None]:
            with self.assertRaises(RuleError):
                r.check(ctx, {'chance': value})

    def test_saved_seed_and_turn_reproduce_sequence(self):
        r = default_registry()
        state = GameState('mini', 'a', random_seed=47)
        def sequence(s):
            result = []
            for _ in range(30):
                result.append(r.check(Context(mini_story(), s), {'chance': 50}))
                s.turn += 1
            return result
        restored = GameState.from_dict(json.loads(json.dumps(state.to_dict())))
        a = sequence(state)
        self.assertEqual(a, sequence(restored))
        self.assertIn(True, a)
        self.assertIn(False, a)

class IntegrationBoundaryTest(unittest.TestCase):
    def test_example_registers_condition_effect_verb_and_graphical_action(self):
        from taleloom.ui_contract import ActionRequest
        story = mini_story(mechanics=['example'])
        s = GameSession(story)
        view = s.start().view
        self.assertIn('example:ring', [a.id for a in view.actions])
        result = s.dispatch(ActionRequest('example:ring', 0))
        self.assertTrue(result.ok)
        self.assertEqual(s.engine.state.ext['example']['rings'], 1)
        self.assertTrue(s.engine.registry.check(Context(story, s.engine.state), {'bell_rung': True}))

    def test_variant_conditions_are_statically_checked(self):
        from taleloom.validator import validate
        for condition in [{'chance': 101}, {'has_item': 'missing'}, {'unknown': True}]:
            raw = mini_raw()
            raw['scenes'][0]['variants'] = [{'when': condition, 'text': 'x'}]
            issues = validate(parse_story(raw))
            self.assertTrue(any(i.level == 'error' and 'variants' in i.path for i in issues))

    def test_random_session_roundtrip_and_read_purity(self):
        from taleloom.ui_contract import ActionRequest
        raw = mini_raw(vars={'hit': 0}, triggers=[{'id': 'random', 'once': False,
            'when': {'chance': 50}, 'effects': [{'add_var': ['hit', 1]}]}])
        raw['scenes'][0]['choices'].append({'id': 'wait', 'text': '等待'})
        a, b = GameSession(parse_story(raw)), GameSession(parse_story(raw))
        a.engine.state.random_seed = 31
        a.start(); b.start()
        for _ in range(5):
            a.dispatch(ActionRequest('choice:wait', a.snapshot().revision))
        self.assertTrue(b.restore(a.export_save()).ok)
        for _ in range(10):
            before = a.export_save()
            a.snapshot(); a.start(); a.engine.available_choices()
            self.assertEqual(a.export_save(), before)
            for s in (a, b):
                self.assertTrue(s.dispatch(ActionRequest('choice:wait', s.snapshot().revision)).ok)
            self.assertEqual(a.export_save(), b.export_save())

class CodecAndPluginTest(unittest.TestCase):
    def test_save_codec_isolated_and_old_format_supported(self):
        s = GameSession(mini_story(), seed=89)
        s.start()
        encoded = s.export_save()
        restored = GameSession(mini_story())
        restored.start()
        self.assertTrue(restored.restore(encoded).ok)
        restored.engine.state.flags.append('changed')
        self.assertEqual(encoded['state']['flags'], [])
        self.assertEqual(s.engine.state.flags, [])
        self.assertEqual(restored.engine.state.random_seed, 89)
        del encoded['state']['random_seed']
        self.assertTrue(restored.restore(encoded).ok)
        self.assertEqual(restored.engine.state.random_seed, 0)

    def test_example_rejects_bad_effect_and_command(self):
        engine = Engine(mini_story(mechanics=['example']))
        engine.start()
        before = engine.state.to_dict()
        result = engine.handle(Command('ring', ['extra']))
        self.assertTrue(result.lines)
        self.assertEqual(engine.state.to_dict(), before)
        with self.assertRaises(RuleError):
            engine.registry.apply(Context(engine.story, engine.state), [{'ring_bell': 1}])
        self.assertEqual(engine.state.to_dict(), before)

    def test_plugin_presentation_does_not_modify_real_state_or_story(self):
        from taleloom.mechanics.base import Mechanic
        class BadDisplay(Mechanic):
            def actions(self, engine):
                engine.state.vars['bad'] = 1
                engine.story.title = 'changed'
                return []
        story = mini_story()
        s = GameSession(story)
        s.engine.mechanics['bad'] = BadDisplay()
        s.start()
        self.assertNotIn('bad', s.engine.state.vars)
        self.assertEqual(story.title, '迷你剧本')

class ChoiceTextTest(unittest.TestCase):
    def test_cli_and_graphical_choice_labels_use_same_interpolation(self):
        story = mini_story()
        story.scenes['a'].choices[0].text = '拿起{item:key}'
        self.assertEqual(Engine(story).start().choices[0][1], '拿起钥匙')
        self.assertEqual(GameSession(story).start().view.choices[0].label, '拿起钥匙')
