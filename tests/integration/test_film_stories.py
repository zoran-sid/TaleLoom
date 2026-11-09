"""影像版剧本（stories/film/）：线性分支、不上书架、每个结局都有通关脚本。负责人：ZC。

影像版只供影像模式（cinematic.html）使用：文字版书架、桌面 GUI 和命令行菜单
都只列出 stories/*/ 下的剧本，所以这里单独检查它的校验、回放与结构。
"""

import io
import unittest
from contextlib import redirect_stdout

import main
from taleloom import replay
from taleloom.loader import load_story
from taleloom.session_factory import create_session
from taleloom.ui_contract import ActionRequest
from taleloom.validator import validate
from tests.fixtures import ROOT, STORIES
from tools import build_web

FILM_DIRS = sorted(p.parent for p in (STORIES / "film").glob("*/story.json"))


def forward_edges(story):
    """场景之间由选项或进入效果产生的跳转（指认只会去结局，不会形成回路）。"""
    edges = {}
    for sid, scene in story.scenes.items():
        targets = {c.goto for c in scene.choices if c.goto}
        targets |= {e["goto"] for c in scene.choices for e in c.effects if "goto" in e}
        targets |= {e["goto"] for e in scene.on_enter if "goto" in e}
        edges[sid] = targets
    return edges


class FilmStoriesTest(unittest.TestCase):
    def test_there_is_a_film_story(self):
        self.assertTrue(FILM_DIRS, "stories/film/ 下应至少有一个影像版剧本")

    def test_validates_without_errors_or_warnings(self):
        for d in FILM_DIRS:
            with self.subTest(story=d.name):
                self.assertEqual([str(i) for i in validate(load_story(d))], [])

    def test_walkthroughs_reach_every_ending(self):
        for d in FILM_DIRS:
            story = load_story(d)
            results = [replay.check(story, replay.load_walkthrough(p)) for p in replay.walkthroughs_for(d)]
            for result in results:
                with self.subTest(story=d.name, walkthrough=result.walkthrough):
                    self.assertTrue(result.ok, result.message + "\n" + "\n".join(result.transcript))
            all_endings, covered = replay.ending_coverage(story, results)
            self.assertEqual(all_endings - covered, set(), d.name)

    def test_every_choice_moves_forward_without_loops(self):
        for d in FILM_DIRS:
            story = load_story(d)
            edges = forward_edges(story)
            state = {}

            def visit(node, path):
                state[node] = "open"
                for nxt in edges.get(node, ()):
                    if state.get(nxt) == "open":
                        self.fail(f"{d.name} 出现回路：{' → '.join(path + [nxt])}")
                    if nxt not in state:
                        visit(nxt, path + [nxt])
                state[node] = "done"

            visit(story.start, [story.start])
            for sid, scene in story.scenes.items():
                with self.subTest(story=d.name, scene=sid):
                    if not scene.ending:
                        self.assertTrue(scene.choices, "每个剧情节点都要有向前的选择")
                        self.assertTrue(all(c.goto for c in scene.choices), "影像版的每个选择都进入下一段剧情")
                        self.assertTrue(any(not c.when for c in scene.choices), "至少一个选择总是可用，避免卡住")

    def test_not_listed_on_shelf_desktop_or_cli(self):
        listed, films = build_web.catalogs(ROOT)
        film_ids = {load_story(d).id for d in FILM_DIRS}
        self.assertFalse(film_ids & {entry["id"] for entry in listed})
        self.assertEqual(film_ids, {entry["id"] for entry in films})
        self.assertFalse(set(FILM_DIRS) & set(main.story_dirs()))

    def test_main_validate_also_checks_film_stories(self):
        with redirect_stdout(io.StringIO()) as buf:
            code = main.main(["validate"])
        self.assertEqual(code, 0, buf.getvalue())
        for d in FILM_DIRS:
            self.assertIn(d.name, buf.getvalue())
        self.assertEqual(main.resolve(FILM_DIRS[0].name), FILM_DIRS[0])

    def test_failure_endings_are_reached_by_choices(self):
        """中途失败的结局 id 以 fail_ 开头，并且由普通选择进入，影像模式才能退回上一个选择。"""
        for d in FILM_DIRS:
            story = load_story(d)
            fails = {sid for sid, s in story.scenes.items() if s.ending and s.ending["id"].startswith("fail_")}
            self.assertTrue(fails, d.name)
            reached = {c.goto for s in story.scenes.values() for c in s.choices}
            self.assertLessEqual(fails, reached)

    def test_pressing_without_evidence_makes_suspect_wary(self):
        story = load_story(STORIES / "film" / "fog_harbor_film")
        session = create_session(story)
        view = session.start().view
        self.assertEqual({(r.id, r.value, r.maximum) for r in view.resources},
                         {("wary_gu", 0, 1), ("wary_zhou", 0, 1), ("wary_ayun", 0, 1)})
        result = session.dispatch(ActionRequest("choice:bluff", view.revision))
        self.assertTrue(result.ok)
        self.assertTrue(any(m.startswith("【戒备】") for m in result.messages))
        self.assertIn(("wary_gu", 1), {(r.id, r.value) for r in result.view.resources})

    def test_key_nodes_announce_checkpoints(self):
        """关键节点进入时发出“【存档点】名称”，影像模式据此自动存档；名称不重复。"""
        for d in FILM_DIRS:
            story = load_story(d)
            labels = [e["say"][len("【存档点】"):] for s in story.scenes.values() for e in s.on_enter
                      if isinstance(e.get("say"), str) and e["say"].startswith("【存档点】")]
            self.assertGreaterEqual(len(labels), 2, d.name)
            self.assertEqual(len(labels), len(set(labels)), d.name)
            session = create_session(story)
            view = session.start().view
            result = session.dispatch(ActionRequest("choice:office", view.revision))
            self.assertIn("【存档点】第一幕 · 账房", result.messages)


if __name__ == "__main__":
    unittest.main()
