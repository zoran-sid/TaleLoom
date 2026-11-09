"""ZC：推理动作经共享会话接口执行（深入调查、审问、带理由指认）。

使用测试内的迷你推理剧本，不读取 stories/。
"""

import copy
import unittest

from taleloom.legacy_session import LegacySession
from taleloom.loader import parse_story
from taleloom.ui_contract import ActionRequest
from tests.zc.test_mystery_deep import deep_raw


class MysterySessionTest(unittest.TestCase):
    def setUp(self):
        self.session = LegacySession(parse_story(deep_raw()))
        self.session.start()

    def act(self, action_id, **values):
        return self.session.dispatch(ActionRequest(action_id, self.session.snapshot().revision, values))

    def action_ids(self):
        view = self.session.snapshot()
        return [a.id for a in view.choices + view.actions]

    def test_examine_action_reveals_deeper_clue(self):
        self.act('choice:lens')
        self.act('choice:desk')
        result = self.act('mystery:examine', clue='letter')
        self.assertTrue(result.ok, result.messages)
        self.assertIn('seal', [c.id for c in result.view.clues])
        self.assertNotIn('mystery:examine', self.action_ids())

    def test_ask_action_uses_suspect_topic_id(self):
        result = self.act('mystery:ask', topic='butler/night')
        self.assertTrue(result.ok)
        self.assertIn('我一直在酒窖。', result.messages)
        ask = next(a for a in result.view.actions if a.id == 'mystery:ask')
        self.assertEqual(ask.parameters[0].options[0].description, '已问过')

    def test_absent_topic_is_rejected_by_session(self):
        result = self.act('mystery:ask', topic='maid/night')
        self.assertEqual(result.error_code, 'invalid_parameters')

    def test_accuse_needs_every_reason(self):
        self.act('choice:pot')
        self.assertEqual(self.act('mystery:accuse', suspect='butler').error_code, 'invalid_parameters')
        result = self.act('mystery:accuse', suspect='butler', motive='money', evidence='knife')
        self.assertTrue(result.ok)
        self.assertEqual(result.view.ending_id, 'good')

    def test_accuse_is_disabled_until_every_reason_has_options(self):
        accuse = next(a for a in self.session.snapshot().actions if a.id == 'mystery:accuse')
        self.assertFalse(accuse.enabled)
        self.assertIn('关键证据', accuse.disabled_reason)
        self.assertEqual(self.act('mystery:accuse', suspect='butler', motive='money', evidence='x').error_code,
                         'invalid_action')

    def test_act_interlude_reaches_feedback(self):
        self.act('choice:lens')
        self.act('choice:desk')
        self.act('choice:pot')
        result = self.act('mystery:examine', clue='letter')
        self.assertIn('—— 第二幕 · 天亮 ——', result.messages)

    def test_restore_keeps_mystery_progress_and_rejects_bad_fields(self):
        self.act('choice:desk')
        self.act('mystery:ask', topic='butler/night')
        saved = self.session.export_save()
        fresh = LegacySession(parse_story(deep_raw()))
        fresh.start()
        self.assertTrue(fresh.restore(saved).ok)
        self.assertEqual(fresh.export_save()['state'], saved['state'])
        for field, value in (('asked', 'butler/night'), ('examined', [1]), ('act', 5)):
            bad = copy.deepcopy(saved)
            bad['state']['ext']['mystery'][field] = value
            with self.subTest(field=field):
                self.assertEqual(fresh.restore(bad).error_code, 'invalid_save')

    def test_snapshot_reads_do_not_change_save(self):
        self.act('choice:desk')
        before = self.session.export_save()
        for _ in range(3):
            self.session.snapshot()
        self.assertEqual(self.session.export_save(), before)


class CliHintTest(unittest.TestCase):
    def test_cli_only_hint_line_is_hidden_in_graphic_view(self):
        raw = deep_raw()
        raw['scenes'][0]['text'] = '书房。\n（输入“问 管家”审问在场的人。）'
        view = LegacySession(parse_story(raw)).start().view
        self.assertEqual(view.text, '书房。')


if __name__ == '__main__':
    unittest.main()
