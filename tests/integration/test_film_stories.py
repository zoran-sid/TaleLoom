"""影像版剧本（stories/film/）：线性分支、不上书架、每个结局都有通关脚本。负责人：ZC。

影像版只供影像模式（cinematic.html）使用：文字版书架、桌面 GUI 和命令行菜单
都只列出 stories/*/ 下的剧本，所以这里单独检查它的校验、回放与结构。
"""

import io
import json
import unittest
from contextlib import redirect_stdout
from itertools import product

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


def choices_cover_conditions(choices):
    """穷举条件真假组合，允许互补分支而不强求某个按钮无条件显示。"""
    atoms = set()

    def evaluate(condition, values=None):
        if not condition:
            return True
        if 'all' in condition:
            return all([evaluate(c, values) for c in condition['all']])
        if 'any' in condition:
            return any([evaluate(c, values) for c in condition['any']])
        if 'not' in condition:
            return not evaluate(condition['not'], values)
        key = json.dumps(condition, sort_keys=True)
        atoms.add(key)
        return values[key] if values is not None else False

    for choice in choices:
        evaluate(choice.when)
    keys = sorted(atoms)
    return all(any(evaluate(c.when, dict(zip(keys, values))) for c in choices)
               for values in product((False, True), repeat=len(keys)))


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

    def test_session_walkthroughs_match_native_states_and_preserve_rewind_saves(self):
        """全部影像脚本逐步对照正式会话与 CLI，结局存档也能恢复。"""
        from tools.web_vectors import build_vectors
        vectors = build_vectors(d / 'story.json' for d in FILM_DIRS)
        self.assertTrue(vectors)
        stories = {load_story(d).id: load_story(d) for d in FILM_DIRS}
        for vector in vectors:
            with self.subTest(story=vector['story_id'], walkthrough=vector['name']):
                session = create_session(stories[vector['story_id']])
                session.start()
                restored = session.restore(vector['save'])
                self.assertTrue(restored.ok, restored.messages)
                self.assertEqual(session.export_save(), vector['save'])
                self.assertEqual(restored.view.ending_id, vector['ending'])
                if restored.view.ending_kind == 'failure':
                    self.assertTrue(session.rewind(restored.view.revision).ok)
                    self.assertFalse(session.snapshot().ended)

    def test_packaged_session_imports_without_workspace_modules(self):
        """网页 ZIP 必须含正式会话的全部依赖，不能借用工作区模块。"""
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'game.zip'
            archive.write_bytes(build_web.make_archive(ROOT, []))
            result = subprocess.run(
                [sys.executable, '-B', '-I', '-c',
                 f"import sys; sys.path.insert(0, {str(archive)!r}); from taleloom.session import GameSession"],
                cwd=directory, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

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
            units = story.data.get("units", {})
            for sid, scene in story.scenes.items():
                with self.subTest(story=d.name, scene=sid):
                    if not scene.ending:
                        self.assertTrue(any(c.goto for c in scene.choices), "每个剧情节点都要有向前的选择")
                        # 场景内的搜证与追问（once、无 goto）只给反馈；其余选择都进入下一段剧情。
                        self.assertTrue(all(c.goto or c.once for c in scene.choices), "影像版的每个选择都进入下一段剧情")
                        here = [u for u in units.values() if sid in u.get("scenes", [])]
                        self.assertTrue(here or choices_cover_conditions(scene.choices),
                                        "任意条件组合下都应有选择可用，或本场景有调查单元可推进")

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
        """中途失败的结局（ending.kind 为 failure 或旧的 fail_ 前缀）由普通选择进入，影像模式才能退回上一个选择。

        《未结的账》按剧本不设中途失败：选错的代价是人物戒备、材料缺失和不同的结局。
        """
        with_failures = 0
        for d in FILM_DIRS:
            story = load_story(d)
            fails = {sid for sid, s in story.scenes.items() if s.ending and (
                s.ending.get("kind") == "failure" or s.ending["id"].startswith("fail_"))}
            with_failures += bool(fails)
            reached = {c.goto for s in story.scenes.values() for c in s.choices}
            self.assertLessEqual(fails, reached, d.name)
        self.assertGreaterEqual(with_failures, 2)

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

    def test_key_nodes_declare_checkpoints(self):
        """每部影像版至少有两个存档点，名称不重复；正式的 checkpoint 字段与旧的“【存档点】”提示都算。"""
        for d in FILM_DIRS:
            story = load_story(d)
            labels = set()
            for scene in story.scenes.values():
                field = getattr(scene, "checkpoint", None)
                said = [e["say"][len("【存档点】"):] for e in scene.on_enter
                        if isinstance(e.get("say"), str) and e["say"].startswith("【存档点】")]
                names = ({field} if field else set()) | set(said)
                self.assertLessEqual(len(names), 1, f"{d.name}/{scene.id} 的存档点名称前后不一致")
                labels |= names
            self.assertGreaterEqual(len(labels), 2, d.name)

    def test_fog_film_office_announces_checkpoint(self):
        story = load_story(STORIES / "film" / "fog_harbor_film")
        session = create_session(story)
        view = session.start().view
        result = session.dispatch(ActionRequest("choice:office", view.revision))
        self.assertTrue(result.ok, result.messages)
        self.assertIn("【存档点】第一幕 · 账房", result.messages)

if __name__ == "__main__":
    unittest.main()
