"""LQ：真实剧本的公开资源，验证桌面与网页共用的快照。"""
import unittest
from pathlib import Path

from taleloom.loader import load_story
from taleloom.session_factory import create_session
from taleloom.ui_contract import ActionRequest


class DeepSpaceResourcesTest(unittest.TestCase):
    def test_oxygen_is_public_and_reflects_the_saved_state(self):
        root = Path(__file__).resolve().parents[2]
        session = create_session(load_story(root / 'stories/deep_space'))
        first = session.start().view
        oxygen = next((r for r in first.resources if r.id == 'oxygen'), None)
        self.assertIsNotNone(oxygen, '剧本必须公开氧气，否则桌面与网页无法显示')
        self.assertEqual((oxygen.label, oxygen.value, oxygen.maximum), ('氧气', 8, None))
        session.dispatch(ActionRequest('choice:out', first.revision))
        saved = session.export_save()
        session.restore(saved)
        value = next(r.value for r in session.snapshot().resources if r.id == 'oxygen')
        self.assertEqual(value, saved['state']['vars']['oxygen'])
