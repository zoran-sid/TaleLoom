"""Cloudflare 与 GitHub 共用的 Python 发布检查；失败立即停止。"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    """执行全部测试、剧本校验和每个剧本的现有回放。"""
    commands = [
        ['-m', 'unittest', 'discover', '-s', 'tests', '-t', '.'],
        ['main.py', 'validate'],
    ]
    stories = sorted((ROOT / 'stories').glob('*/story.json')) + sorted((ROOT / 'stories' / 'film').glob('*/story.json'))
    commands += [['main.py', 'replay', str(p.parent)] for p in stories]
    for command in commands:
        subprocess.run([sys.executable, '-B', *command], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
