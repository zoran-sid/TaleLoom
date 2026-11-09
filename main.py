"""TaleLoom 启动文件（课程要求的 main.py）。负责人：ZC。

    python main.py                        打开桌面 GUI（尚未完成时自动改用命令行）
    python main.py play [fog_harbor]      命令行游玩
    python main.py validate               校验 stories/ 下全部剧本
    python main.py graph fog_harbor       输出剧本的 Mermaid 场景图
    python main.py replay fog_harbor      回放该剧本的全部通关脚本

影像版专用剧本放在 stories/film/<id>/：不出现在命令行菜单、桌面与网页书架，
只由影像模式页面（cinematic.html）使用；validate 不带参数时也会校验它们。

桌面 GUI 的接入约定（ZRS 实现）：包 taleloom.gui 提供
``run(stories_dir: Path, saves_dir: Path) -> int``，返回进程退出码。
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from taleloom import cli, replay
from taleloom.loader import StoryFormatError, load_story
from taleloom.validator import errors, format_report, render_mermaid, validate

ROOT = Path(__file__).resolve().parent
STORIES = ROOT / "stories"
FILMS = STORIES / "film"
SAVES = ROOT / "saves"


def story_dirs() -> list[Path]:
    """书架上的剧本（命令行菜单、桌面与网页都会列出）。"""
    return sorted(p.parent for p in STORIES.glob("*/story.json"))


def film_dirs() -> list[Path]:
    """影像版专用剧本，只给影像模式使用。"""
    return sorted(p.parent for p in FILMS.glob("*/story.json"))


def resolve(name: str) -> Path:
    path = Path(name)
    if path.exists():
        return path if path.is_dir() else path.parent
    for base in (STORIES, FILMS):
        candidate = base / name
        if (candidate / "story.json").is_file():
            return candidate
    names = ", ".join(p.name for p in story_dirs() + film_dirs())
    raise SystemExit(f"找不到剧本“{name}”。可用剧本：{names}")


def cmd_play(name: str | None) -> int:
    if name is None:
        dirs = story_dirs()
        print("选择剧本：")
        for i, d in enumerate(dirs, 1):
            print(f"  [{i}] {load_story(d).title}（{d.name}）")
        choice = input("> ").strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(dirs):
            print("请输入列表中的编号。")
            return 1
        story_dir = dirs[int(choice) - 1]
    else:
        story_dir = resolve(name)
    story = load_story(story_dir)
    problems = errors(validate(story))
    if problems:
        print(f"剧本《{story.title}》未通过校验，无法开始：")
        for issue in problems:
            print(f"  {issue}")
        return 2
    cli.play(story, SAVES / f"{story.id}.json")
    return 0


def cmd_gui() -> int:
    """无参数启动：优先打开桌面 GUI，缺少 GUI 模块或 Tkinter 时改用命令行。"""
    if importlib.util.find_spec("taleloom.gui") is None:
        print("（桌面界面尚未完成，使用命令行模式。）")
        return cmd_play(None)
    if importlib.util.find_spec("tkinter") is None:
        print("（当前 Python 没有安装 Tkinter（Tcl/Tk），使用命令行模式。）")
        return cmd_play(None)
    from taleloom.gui import run

    return run(stories_dir=STORIES, saves_dir=SAVES)


def cmd_validate(names: list[str]) -> int:
    dirs = [resolve(n) for n in names] or story_dirs() + film_dirs()
    failed = 0
    for d in dirs:
        try:
            story = load_story(d)
        except StoryFormatError as exc:
            print(f"[失败] {d.name}: {exc}")
            failed += 1
            continue
        issues = validate(story)
        bad = errors(issues)
        mark = "[失败]" if bad else "[通过]"
        print(f"{mark} {d.name}《{story.title}》 场景 {len(story.scenes)}，结局 {len(story.endings())}，"
              f"错误 {len(bad)}，警告 {len(issues) - len(bad)}")
        report = format_report(issues, story)
        if report:
            print(report)
        failed += bool(bad)
    return 1 if failed else 0


def cmd_graph(name: str) -> int:
    story = load_story(resolve(name))
    print(render_mermaid(story))
    return 0


def cmd_replay(name: str, verbose: bool) -> int:
    story_dir = resolve(name)
    story = load_story(story_dir)
    results = [replay.check(story, replay.load_walkthrough(p)) for p in replay.walkthroughs_for(story_dir)]
    if not results:
        print("没有通关脚本（stories/<剧本>/walkthroughs/*.txt）。")
        return 1
    for r in results:
        print(f"{'[通过]' if r.ok else '[失败]'} {r.walkthrough}: {r.message}")
        if verbose or not r.ok:
            print("    " + "\n    ".join(r.transcript))
    all_endings, covered = replay.ending_coverage(story, results)
    print(f"结局覆盖：{len(covered)}/{len(all_endings)}；未覆盖：{', '.join(sorted(all_endings - covered)) or '无'}")
    return 0 if all(r.ok for r in results) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="main.py", description="TaleLoom 织境 文字冒险引擎")
    sub = ap.add_subparsers(dest="command")
    p = sub.add_parser("play", help="命令行游玩剧本")
    p.add_argument("story", nargs="?")
    v = sub.add_parser("validate", help="校验剧本")
    v.add_argument("stories", nargs="*")
    g = sub.add_parser("graph", help="输出剧本的 Mermaid 场景图")
    g.add_argument("story")
    r = sub.add_parser("replay", help="回放通关脚本")
    r.add_argument("story")
    r.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.command == "validate":
            return cmd_validate(args.stories)
        if args.command == "graph":
            return cmd_graph(args.story)
        if args.command == "replay":
            return cmd_replay(args.story, args.verbose)
        if args.command == "play":
            return cmd_play(args.story)
        return cmd_gui()
    except StoryFormatError as exc:
        print(f"剧本格式错误：{exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
