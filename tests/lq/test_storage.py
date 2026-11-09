"""LQ：接管 ZRS 文件存储回归测试，并验证正式实现。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from taleloom.storage import FileSaveStore, valid_slot
from taleloom.ui_contract import StorageError


class FileSaveStoreTest(unittest.TestCase):
    def test_metadata_and_invalid_json_preserve_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            store = FileSaveStore(folder)
            store.write('story-2', {'story_id': 'story', 'state': {'scene': 'room', 'turn': 2}})
            row = store.describe_slots('story')[0]
            self.assertEqual((row['scene'], row['turn']), ('room', 2))
            self.assertIn('T', row['saved_at'])
            for bad in [None, {'bad': float('nan')}, {1: 'wrong key'}]:
                with self.assertRaises(StorageError):
                    store.write('story-2', bad)
            self.assertEqual(store.read('story-2')['state']['turn'], 2)

    def test_write_read_and_list_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            store = FileSaveStore(folder)
            store.write("quick", {"save_version": 1, "state": {"turn": 2}})
            store.write("slot-2", {"state": {"turn": 3}})
            self.assertEqual(store.list_slots(), ["quick", "slot-2"])
            self.assertEqual(store.read("quick")["state"]["turn"], 2)

    def test_missing_slot_raises_storage_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(StorageError):
                FileSaveStore(folder).read("quick")

    def test_corrupt_file_raises_storage_error(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "quick.json").write_text("{坏档", encoding="utf-8")
            with self.assertRaises(StorageError):
                FileSaveStore(folder).read("quick")

    def test_invalid_slot_names_cannot_escape_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            store = FileSaveStore(folder)
            for slot in ("../escape", "quick.json", "", "x" * 61):
                with self.subTest(slot=slot), self.assertRaises(StorageError):
                    store.write(slot, {})
            self.assertEqual(list(Path(folder).glob("*")), [])
        self.assertFalse(valid_slot("a/b"))
        self.assertTrue(valid_slot("deep_space-2"))

    def test_failed_write_keeps_previous_save(self):
        with tempfile.TemporaryDirectory() as folder:
            store = FileSaveStore(folder)
            store.write("quick", {"state": {"turn": 1}})
            target = Path(folder) / "quick.json"
            original = target.read_text(encoding="utf-8")
            with self.assertRaises(StorageError):
                store.write("quick", {"state": object()})   # not JSON serializable
            self.assertEqual(target.read_text(encoding="utf-8"), original)
