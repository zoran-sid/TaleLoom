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


if __name__ == "__main__":
    unittest.main()
