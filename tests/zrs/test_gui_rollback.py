"""ZRS：桌面失败回退——回到上一个选择、回到存档点、自动存档列表。

规则只经会话接口（export_save / restore），与影像页同一套口径：
每次提交前记一个检查点；失败结局可退回上一个选择（整局 3 次机会）；
“【存档点】”提示出现时自动存档，可随时回到存档点（不消耗机会）。
"""

import json
import tempfile
import unittest
from pathlib import Path

from taleloom.gui.controller import GameController
from taleloom.ui_contract import ActionSpec, SessionResult, ViewSnapshot
from tests.ui_fakes import FakeGameSession


class RollbackSession(FakeGameSession):
    """线性四步：大堂 →（冒险）失败 或 账房（存档点）→ 结局。"""

    def __init__(self):
        super().__init__()
        self.step = 0
        self.revision = 0
        self._started = True

    STEPS = [
        dict(scene='hall', title='大堂', text='雾很重。', choices=[
            ('choice:risky', '趁夜下码头'), ('choice:safe', '先看账本')]),
        dict(scene='fail', title='失足', text='潮水把你卷走。', ending='fail_tide',
             ending_title='失足', choices=[]),
        dict(scene='office', title='账房', text='账本在这里。', choices=[('choice:go', '去对质')]),
        dict(scene='end', title='雾散', text='天亮了。', ending='truth', ending_title='雾散', choices=[]),
    ]

    def snapshot(self):
        cur = self.STEPS[self.step]
        return ViewSnapshot(
            story_id='film_demo', story_title='影像测试剧本',
            scene_id=cur['scene'], scene_title=cur['title'], text=cur['text'],
            revision=self.revision, turn=self.step,
            choices=[ActionSpec(cid, label) for cid, label in cur['choices']],
            ended='ending' in cur, ending_id=cur.get('ending'), ending_title=cur.get('ending_title'),
        )

    def dispatch(self, request):
        view = self.snapshot()
        if request.expected_revision != self.revision:
            return SessionResult(view, ['画面已更新，请重新选择。'], 'stale_revision')
        if request.action_id not in {c.id for c in view.choices}:
            return SessionResult(view, ['当前不能执行这个操作。'], 'invalid_action')
        self.step = {'choice:risky': 1, 'choice:safe': 2, 'choice:go': 3}[request.action_id]
        self.revision += 1
        messages = ['操作完成。']
        if self.step == 2:
            messages.append('【存档点】账房')
        return SessionResult(self.snapshot(), messages)

    def export_save(self):
        return {'fixture': 'rollback', 'step': self.step}

    def restore(self, payload):
        view = self.snapshot()
        if not isinstance(payload, dict) or payload.get('fixture') != 'rollback' \
                or type(payload.get('step')) is not int or payload['step'] not in range(4):
            return SessionResult(view, ['测试存档无效。'], 'invalid_save')
        self.step = payload['step']
        self.revision += 1
        return SessionResult(self.snapshot(), ['已恢复。'])


STORY = {
    "format_version": 1, "id": "film_demo", "title": "影像测试剧本", "start": "hall",
    "scenes": [
        {"id": "hall", "title": "大堂", "text": "雾很重。", "choices": [
            {"id": "risky", "text": "趁夜下码头", "goto": "fail"},
            {"id": "safe", "text": "先看账本", "goto": "office"}]},
        {"id": "fail", "title": "失足", "text": "潮水把你卷走。", "ending": {"id": "fail_tide", "title": "失足"}},
        {"id": "office", "title": "账房", "text": "账本在这里。", "on_enter": [{"say": "【存档点】账房"}],
         "choices": [{"id": "go", "text": "去对质", "goto": "end"}]},
        {"id": "end", "title": "雾散", "text": "天亮了。", "ending": {"id": "truth", "title": "雾散"}},
    ],
}


def make(root: Path) -> GameController:
    folder = root / "stories" / "film_demo"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "story.json").write_text(json.dumps(STORY, ensure_ascii=False), encoding="utf-8")
    controller = GameController(root / "stories", root / "saves", lambda story: RollbackSession())
    controller.load_catalog()
    return controller


class RollbackTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.controller = make(self.root)
        self.assertTrue(self.controller.start("film_demo"))

    def tearDown(self):
        self.folder.cleanup()

    def test_failure_offers_rewind_with_three_chances(self):
        self.controller.submit("choice:risky")
        self.assertTrue(self.controller.view.ended)
        self.assertTrue(self.controller.can_rewind)
        self.assertEqual(self.controller.chances_left, 3)

    def test_rewind_returns_to_previous_choice_and_spends_a_chance(self):
        self.controller.submit("choice:risky")
        self.assertTrue(self.controller.rewind())
        self.assertEqual(self.controller.view.scene_id, "hall")
        self.assertFalse(self.controller.view.ended)
        self.assertEqual(self.controller.chances_left, 2)
        self.assertEqual(self.controller.mistakes, 1)

    def test_rewind_is_refused_after_three_uses(self):
        for _ in range(3):
            self.controller.submit("choice:risky")
            self.assertTrue(self.controller.rewind())
        self.controller.submit("choice:risky")
        self.assertEqual(self.controller.chances_left, 0)
        self.assertFalse(self.controller.can_rewind)
        self.assertFalse(self.controller.rewind())
        self.assertTrue(self.controller.view.ended)

    def test_rewind_is_only_offered_after_a_failure(self):
        self.assertFalse(self.controller.can_rewind)
        self.controller.submit("choice:safe")
        self.assertFalse(self.controller.can_rewind)

    def test_checkpoint_is_autosaved_when_notice_appears(self):
        self.controller.submit("choice:safe")
        labels = [row["label"] for row in self.controller.checkpoints]
        self.assertIn("账房", labels)

    def test_rollback_to_checkpoint_restores_without_spending_a_chance(self):
        self.controller.submit("choice:safe")
        self.controller.submit("choice:go")
        self.assertTrue(self.controller.view.ended)
        before = self.controller.chances_left
        target = next(row for row in self.controller.checkpoints if row["label"] == "账房")
        self.assertTrue(self.controller.rollback_to(target["slot"]))
        self.assertEqual(self.controller.view.scene_id, "office")
        self.assertEqual(self.controller.chances_left, before)

    def test_rollback_to_checkpoint_drops_later_checkpoints(self):
        self.controller.submit("choice:safe")
        first = next(row for row in self.controller.checkpoints if row["label"] == "账房")
        self.controller.submit("choice:go")
        self.assertTrue(self.controller.rollback_to(first["slot"]))
        labels = [row["label"] for row in self.controller.checkpoints]
        self.assertEqual(labels.count("账房"), 1)

    def test_normal_ending_has_no_rewind(self):
        self.controller.submit("choice:safe")
        self.controller.submit("choice:go")
        self.assertTrue(self.controller.view.ended)
        self.assertFalse(self.controller.can_rewind)
        self.assertFalse(self.controller.rewind())

    def test_start_resets_chances(self):
        self.controller.submit("choice:risky")
        self.controller.rewind()
        self.assertEqual(self.controller.chances_left, 2)
        self.controller.restart()
        self.assertEqual(self.controller.chances_left, 3)
        self.assertEqual(self.controller.mistakes, 0)


if __name__ == "__main__":
    unittest.main()
