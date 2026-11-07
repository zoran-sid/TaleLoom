"""发布白名单保证测试、攻略、存档及环境文件不进入游戏包。"""
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.build_web import CORE, RUNTIME, make_archive


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
