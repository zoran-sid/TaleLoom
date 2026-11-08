"""生成课程提交用的 groupX_project.zip。负责人：ZC。

    python tools/package.py --group 3            # 在项目根目录生成 group3_project.zip
    python tools/package.py --group 3 --out dist # 指定输出目录

压缩包包含全部源文件、剧本数据和说明文件，解压后在 group3_project/ 下运行
``python main.py`` 即可。文件清单优先取 Git 跟踪及未被忽略的文件；没有 Git 时
按下面的排除规则遍历目录。依赖目录、构建产物、存档、缓存和私密环境文件不打包。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 任意层级出现即整体跳过的目录。
EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", "saves", "dist", ".web-public", ".cloudflare",
    ".wrangler", "test-results", "playwright-report", ".venv", "venv", ".idea", "_tmp",
}
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}
# .vscode 只保留团队共享的启动配置。
VSCODE_KEEP = {"launch.json"}


def archive_name(group: str) -> str:
    """压缩包与顶层文件夹名；组号只能是数字，或尚未确定时用占位符 X。

    >>> archive_name("3")
    'group3_project'
    """
    if group != "X" and not re.fullmatch(r"[0-9]+", group or ""):
        raise ValueError(f"组号应为数字（尚未确定时写 X），收到：{group!r}")
    return f"group{group}_project"


def _excluded(relative: Path) -> bool:
    parts = relative.parts
    if any(part in EXCLUDED_DIRS for part in parts[:-1]):
        return True
    name = parts[-1]
    if name in EXCLUDED_NAMES or relative.suffix in EXCLUDED_SUFFIXES:
        return True
    if name == ".env" or name.startswith(".env."):
        return True
    return parts[0] == ".vscode" and name not in VSCODE_KEEP


def walk_files(root: Path) -> list[Path]:
    """不依赖 Git 时的文件清单：遍历 root，按排除规则过滤，返回相对路径。"""
    files = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not _excluded(relative):
            files.append(relative)
    return files


def project_files(root: Path = ROOT) -> list[Path]:
    """提交用的文件清单：Git 跟踪与未忽略的新文件，再套用排除规则。"""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root, check=True, capture_output=True,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return walk_files(root)
    files = {Path(name) for name in listed.split("\0") if name}
    return sorted(p for p in files if (root / p).is_file() and not _excluded(p))


def build_zip(group: str, out_dir: Path = ROOT, root: Path = ROOT, files: list[Path] | None = None) -> Path:
    """把文件写入 out_dir/groupN_project.zip，压缩包内统一放在 groupN_project/ 下。"""
    name = archive_name(group)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.zip"
    files = project_files(root) if files is None else files
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for relative in files:
            zf.write(root / relative, f"{name}/{relative.as_posix()}")
    return target


def main(argv: list[str] | None = None) -> int:
    """命令行入口；组号无效时给出提示并返回 2。"""
    ap = argparse.ArgumentParser(description="生成课程提交用的 groupX_project.zip")
    ap.add_argument("--group", default="X", help="小组编号，例如 3；尚未确定时默认 X")
    ap.add_argument("--out", default=str(ROOT), help="输出目录，默认项目根目录")
    args = ap.parse_args(argv)
    try:
        archive_name(args.group)
    except ValueError as exc:
        print(f"组号无效：{exc}")
        return 2
    files = project_files(ROOT)
    path = build_zip(args.group, Path(args.out), ROOT, files)
    print(f"已生成 {path}（{len(files)} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
