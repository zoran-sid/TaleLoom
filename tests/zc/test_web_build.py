"""发布白名单保证测试、攻略、存档及环境文件不进入游戏包。"""
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.build_web import CORE, RUNTIME, catalogs, make_archive


class WebBuildTest(unittest.TestCase):
    def test_archive_is_deterministic_and_excludes_private_and_test_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = (['taleloom/' + name for name in CORE]
                     + ['web/runtime/' + name for name in RUNTIME]
                     + ['web/__init__.py', 'stories/mini/story.json'])
            for name in paths + ['.env', 'saves/private.json', 'tests/answer.py',
                                  'stories/mini/walkthroughs/answer.txt', 'taleloom/gui/window.py']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture', encoding='utf-8')
            first = make_archive(root, [])
            self.assertEqual(first, make_archive(root, []))
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertEqual(set(archive.namelist()), set(paths) | {'catalog.json'})

    def test_film_stories_are_packaged_but_not_on_the_shelf(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ['taleloom/' + n for n in CORE] + ['web/runtime/' + n for n in RUNTIME] + ['web/__init__.py']:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text('fixture', encoding='utf-8')
            for name, story in [('stories/mini/story.json', '{"id": "mini", "title": "迷你"}'),
                                ('stories/film/mini_film/story.json',
                                 '{"id": "mini_film", "title": "迷你影像版", "meta": {"genre": "互动影像"}}')]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(story, encoding='utf-8')
            listed, films = catalogs(root)
            self.assertEqual([e['id'] for e in listed], ['mini'])
            self.assertEqual(films, [{'id': 'mini_film', 'title': '迷你影像版', 'genre': '互动影像',
                                      'path': 'stories/film/mini_film/story.json', 'listed': False}])
            with zipfile.ZipFile(io.BytesIO(make_archive(root, listed + films))) as archive:
                self.assertIn('stories/film/mini_film/story.json', archive.namelist())


if __name__ == '__main__':
    unittest.main()
