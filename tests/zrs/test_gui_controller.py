"""ZRS：桌面界面状态机——用测试替身驱动，不打开窗口。"""

import json
import tempfile
import unittest
from pathlib import Path

from taleloom.gui.controller import (
    FileSaveStore, GameController, QUICK_SLOT, load_catalog, valid_slot,
)
from taleloom.ui_contract import ActionRequest, StorageError
from tests.ui_fakes import FakeGameSession, MemorySaveStore


def catalog_controller(root: Path, session_factory=None, make_store=None):
    """用测试构造的剧本目录，避免依赖 stories/ 的真实剧情。"""
    story_dir = root / "stories" / "ui_demo"
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "story.json").write_text(json.dumps(minimal_story(), ensure_ascii=False), encoding="utf-8")
    return GameController(root / "stories", root / "saves", session_factory or (lambda story: FakeGameSession()),
                          make_store=make_store)


def minimal_story():
    return {
        "format_version": 1, "id": "ui_demo", "title": "界面测试剧本", "start": "hall",
        "scenes": [{"id": "hall", "title": "门厅", "text": "门边有一把钥匙。",
                    "choices": [{"id": "take", "text": "捡起钥匙", "once": True},
                                {"id": "open", "text": "打开房门", "goto": "out"}]},
                   {"id": "out", "title": "门外", "text": "你出来了。", "ending": {"id": "out", "title": "出门"}}],
    }


class CatalogTest(unittest.TestCase):
    def test_catalog_reads_title_and_genre(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = minimal_story()
            raw["meta"] = {"genre": "测试类型"}
            (Path(folder) / "ui_demo").mkdir()
            (Path(folder) / "ui_demo" / "story.json").write_text(json.dumps(raw), encoding="utf-8")
            entries, problems = load_catalog(folder)
        self.assertEqual([(e.id, e.title, e.genre) for e in entries], [("ui_demo", "界面测试剧本", "测试类型")])
        self.assertEqual(problems, [])

    def test_broken_story_is_reported_without_blocking_others(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "good").mkdir()
            (root / "good" / "story.json").write_text(json.dumps(minimal_story() | {"id": "good"}), encoding="utf-8")
            (root / "broken").mkdir()
            (root / "broken" / "story.json").write_text("{不是 JSON", encoding="utf-8")
            entries, problems = load_catalog(root)
        self.assertEqual([e.id for e in entries], ["good"])
        self.assertEqual(len(problems), 1)
        self.assertIn("broken", problems[0])

    def test_missing_folder_returns_empty_catalog(self):
        entries, problems = load_catalog(Path(tempfile.gettempdir()) / "taleloom-missing-dir")
        self.assertEqual((entries, problems), ([], []))


class FileSaveStoreTest(unittest.TestCase):
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


class ControllerTest(unittest.TestCase):
    def test_start_loads_catalog_and_shows_first_scene(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            self.assertTrue(controller.start("ui_demo"))
            self.assertEqual(controller.view.scene_title, "门厅")
            self.assertEqual([c.id for c in controller.view.choices], ["choice:take"])
            self.assertTrue(controller.dirty)

    def test_unknown_story_reports_error(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            self.assertFalse(controller.start("missing"))
            self.assertIn("找不到", controller.error)

    def test_submit_advances_and_marks_dirty(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            controller.start("ui_demo")
            result = controller.submit("choice:take")
            self.assertTrue(result.ok)
            self.assertEqual([i.id for i in controller.view.inventory], ["key"])
            self.assertTrue(controller.dirty)

    def test_stale_action_is_rejected_without_losing_state(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            controller.start("ui_demo")
            old_revision = controller.view.revision
            controller.submit("choice:take")
            after_take = controller.view.to_dict()
            stale = controller.session.dispatch(ActionRequest("choice:open", old_revision))
            self.assertEqual(stale.error_code, "stale_revision")
            self.assertEqual(controller.view.to_dict(), after_take)
            controller.submit("choice:open")
            self.assertEqual(controller.view.scene_title, "门外")

    def test_submit_while_busy_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            controller.start("ui_demo")
            controller.busy = True
            self.assertIsNone(controller.submit("choice:take"))
            controller.busy = False
            self.assertEqual(controller.view.turn, 0)

    def test_save_and_resume_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = catalog_controller(root)
            first.load_catalog()
            first.start("ui_demo")
            first.submit("choice:take")
            self.assertTrue(first.save())
            self.assertFalse(first.dirty)
            second = catalog_controller(root)
            second.load_catalog()
            self.assertTrue(second.has_save("ui_demo"))
            self.assertTrue(second.start("ui_demo", resume=True))
            self.assertEqual([i.id for i in second.view.inventory], ["key"])
            self.assertFalse(second.dirty)

    def test_resume_without_save_starts_fresh_with_note(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            self.assertTrue(controller.start("ui_demo", resume=True))
            self.assertIn("从头开始", controller.error)
            self.assertEqual(controller.view.turn, 0)

    def test_load_missing_save_keeps_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            controller.start("ui_demo")
            controller.submit("choice:take")
            before = controller.view.to_dict()
            self.assertFalse(controller.load())
            self.assertIn("没有找到存档", controller.error)
            self.assertEqual(controller.view.to_dict(), before)

    def test_corrupt_save_keeps_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            controller = catalog_controller(root)
            controller.load_catalog()
            controller.start("ui_demo")
            controller.submit("choice:take")
            before = controller.view.to_dict()
            (root / "saves").mkdir()
            (root / "saves" / f"ui_demo-{QUICK_SLOT}.json").write_text("{坏档", encoding="utf-8")
            self.assertFalse(controller.load())
            self.assertEqual(controller.view.to_dict(), before)
            self.assertIn("无法读取", controller.error)

    def test_save_error_keeps_current_progress(self):
        class BrokenStore(MemorySaveStore):
            def write(self, slot, payload):
                raise StorageError("磁盘已满")

        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder), make_store=None)
            controller._make_store = lambda saves: BrokenStore()
            controller.load_catalog()
            controller.start("ui_demo")
            self.assertFalse(controller.save())
            self.assertEqual(controller.error, "磁盘已满")
            self.assertIsNotNone(controller.view)

    def test_restart_and_home_reset_session(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = catalog_controller(Path(folder))
            controller.load_catalog()
            controller.start("ui_demo")
            controller.submit("choice:take")
            self.assertTrue(controller.restart())
            self.assertEqual(controller.view.inventory, [])
            controller.home()
            self.assertIsNone(controller.session)
            self.assertIsNone(controller.view)

    def test_saves_are_isolated_per_story(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            controller = catalog_controller(root)
            controller.load_catalog()
            controller.start("ui_demo")
            controller.submit("choice:take")
            controller.save()
            self.assertTrue((root / "saves" / f"ui_demo-{QUICK_SLOT}.json").is_file())
            self.assertEqual(controller.store.list_slots(), [f"ui_demo-{QUICK_SLOT}"])


if __name__ == "__main__":
    unittest.main()
