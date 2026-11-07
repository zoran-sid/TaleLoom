"""命令行交互界面。负责人：ZRS。

input_fn / print_fn 可以注入，测试时不需要真实终端。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .engine import Engine
from .model import Output, Story
from .parser import parse
from .rules import RuleError
from .save import SaveError, load_game, save_game

PROMPT = "> "


def render(out: Output, print_fn: Callable[[str], None] = print) -> None:
    for line in out.lines:
        print_fn(line)
    if out.choices:
        print_fn("")
        for index, text in out.choices:
            print_fn(f"  [{index}] {text}")
    if out.ended:
        print_fn("\n（故事结束。输入“读档”回到存档，或“退出”离开。）")


def play(
    story: Story,
    save_path: str | Path,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> None:
    engine = Engine(story)
    out = engine.start()
    render(out, print_fn)
    while True:
        try:
            line = input_fn(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print_fn("\n再见。")
            return
        cmd = parse(line, out.choices, engine.verb_aliases())
        if cmd.verb == "quit":
            print_fn("再见。")
            return
        if cmd.verb == "save":
            path = save_game(engine.state, story, save_path)
            print_fn(f"已存档：{path}")
            continue
        if cmd.verb == "load":
            try:
                state, notes = load_game(save_path, story)
            except SaveError as exc:
                print_fn(f"读档失败：{exc}")
                continue
            for note in notes:
                print_fn(note)
            engine = Engine(story, state)
            out = engine.start()
            render(out, print_fn)
            continue
        try:
            out = engine.handle(cmd)
        except RuleError as exc:
            # 剧本错误不应让玩家看到崩溃；validator 应在开发阶段拦截这类问题
            print_fn(f"[剧本错误] {exc}")
            continue
        render(out, print_fn)
