"""ZC：提交用压缩包 groupX_project.zip 的打包脚本。"""

import io
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from tools import package


def make_project(root: Path) -> None:
    """在临时目录里放一个最小“项目”，包含应打包与应排除的文件。"""
    files = {
        "main.py": "print('hi')\n",
        "README.md": "# 说明\n",
        "taleloom/engine.py": "",
        "stories/demo/story.json": "{}",
        ".vscode/launch.json": "{}",
        ".vscode/settings.json": "{}",
        "taleloom/__pycache__/engine.cpython-313.pyc": "x",
        "node_modules/vite/index.js": "",
        "saves/demo.json": "{}",
        "dist/index.html": "",
        ".DS_Store": "",
        ".env": "TOKEN=secret",
        "group1_project.zip": "old",
        "tests/yht/_tmp/scratch.txt": "",
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


class CollectFilesTest(unittest.TestCase):
    def test_walk_keeps_sources_and_skips_generated_and_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)
            names = {p.as_posix() for p in package.walk_files(root)}
        self.assertEqual(names, {
            "main.py", "README.md", "taleloom/engine.py", "stories/demo/story.json", ".vscode/launch.json",
        })

    def test_real_project_listing_has_entry_point_and_no_dependencies(self):
        names = {p.as_posix() for p in package.project_files(package.ROOT)}
        for required in ("main.py", "README.md", "taleloom/engine.py", "stories/fog_harbor/story.json"):
            self.assertIn(required, names)
        self.assertFalse([n for n in names if n.startswith(("node_modules/", "saves/", ".git/"))])
        self.assertFalse([n for n in names if "__pycache__" in n or n.endswith(".zip")])


class BuildZipTest(unittest.TestCase):
    def test_zip_name_and_single_top_folder(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as out:
            root = Path(tmp)
            make_project(root)
            path = package.build_zip("7", out_dir=Path(out), root=root, files=package.walk_files(root))
            self.assertEqual(path.name, "group7_project.zip")
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                self.assertIn("group7_project/main.py", names)
                self.assertTrue(all(n.startswith("group7_project/") for n in names))
                self.assertEqual(zf.read("group7_project/README.md").decode("utf-8"), "# 说明\n")

    def test_group_must_be_number_or_placeholder(self):
        for bad in ("", "3a", "../x", "-1"):
            with self.subTest(group=bad), self.assertRaises(ValueError):
                package.archive_name(bad)
        self.assertEqual(package.archive_name("X"), "groupX_project")
        self.assertEqual(package.archive_name("12"), "group12_project")

    def test_cli_reports_path_and_count(self):
        with tempfile.TemporaryDirectory() as out:
            with redirect_stdout(io.StringIO()) as buf:
                code = package.main(["--group", "3", "--out", out])
            self.assertEqual(code, 0)
            self.assertTrue((Path(out) / "group3_project.zip").is_file())
        self.assertIn("group3_project.zip", buf.getvalue())

    def test_cli_rejects_bad_group_with_message(self):
        with redirect_stdout(io.StringIO()) as buf:
            code = package.main(["--group", "abc"])
        self.assertEqual(code, 2)
        self.assertIn("组号", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
