"""LQ：关键节点持久化，用迷你剧本验证，不读取 stories。"""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from taleloom.storage import FileSaveStore, CheckpointStore
from taleloom.session_factory import create_session
from taleloom.ui_contract import StorageError, ActionRequest
from tests.fixtures import mini_story


class CheckpointStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.story = mini_story()
        self.session = create_session(self.story, seed=6181)
        view = self.session.start().view
        self.entry = {'label': '开场', 'scene': view.scene_title, 'turn': view.turn,
                      'at': 1, 'save': self.session.export_save()}
        self.files = FileSaveStore(self.temp.name)
        self.store = CheckpointStore(self.files, self.story.id)

    def test_refresh_and_export_import_preserve_independent_entries(self):
        self.store.write_entries([self.entry])
        self.entry['save']['state']['flags'].append('outside')
        fresh = CheckpointStore(FileSaveStore(self.temp.name), self.story.id)
        entries = fresh.read_entries()
        self.assertNotIn('outside', entries[0]['save']['state']['flags'])
        bundle = fresh.export_bundle()
        other = CheckpointStore(FileSaveStore(Path(self.temp.name) / 'other'), self.story.id)
        other.import_bundle(bundle)
        self.assertEqual(other.read_entries(), entries)
        self.assertTrue(self.session.restore(entries[0]['save']).ok)

    def test_invalid_bundle_and_failed_write_keep_old_checkpoint(self):
        self.store.write_entries([self.entry])
        original = self.store.export_bundle()
        mutations = [('checkpoint_version', True), ('story_id', 'other'), ('entries', None)]
        for key, value in mutations:
            bad = copy.deepcopy(original); bad[key] = value
            with self.assertRaises(StorageError):
                self.store.import_bundle(bad)
        for field, value in [('label', ''), ('turn', -1), ('at', float('nan')), ('save', {})]:
            bad = copy.deepcopy(self.entry); bad[field] = value
            with self.assertRaises(StorageError):
                self.store.write_entries([bad])
        bad = copy.deepcopy(self.entry); bad['save']['state']['story_id'] = 'other'
        with self.assertRaises(StorageError):
            self.store.write_entries([bad])
        with self.assertRaises(StorageError):
            self.store.write_entries([self.entry, self.entry])
        with patch('taleloom.save.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(StorageError):
                self.store.write_entries([])
        self.assertEqual(self.store.export_bundle(), original)

    def test_pruning_uses_one_atomic_bundle_and_does_not_touch_quick_save(self):
        self.files.write(self.story.id + '-quick', self.entry['save'])
        self.session.dispatch(ActionRequest('choice:take', self.session.snapshot().revision))
        second = {'label': '门前', 'scene': '门厅', 'turn': 1, 'at': 2,
                  'save': self.session.export_save()}
        self.store.write_entries([self.entry, second])
        self.store.write_entries([self.entry])
        self.assertEqual(len(self.store.read_entries()), 1)
        self.assertEqual(self.files.read(self.story.id + '-quick')['state']['turn'], 0)
        self.assertEqual(CheckpointStore(self.files, 'other').read_entries(), [])
