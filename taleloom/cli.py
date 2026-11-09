"""命令行交互界面。负责人：ZRS。

input_fn / print_fn 可以注入，测试时不需要真实终端。
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Callable

from .engine import Engine
from .model import Output, Story
from .parser import parse
from .rules import RuleError
from .save import SaveError, load_game, save_game
from .storage import FileSaveStore, valid_slot

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
    save_path = Path(save_path)
    store = FileSaveStore(save_path.parent)
    engine = Engine(story)
    engine.state.random_seed = secrets.randbits(53)
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
        if cmd.verb in ("save", "load"):
            slot = cmd.args[0] if cmd.args else "quick"
            if slot in ("列表", "list"):
                for row in store.describe_slots(story.id):
                    print_fn(f"存档 {row['slot']} | {row.get('saved_at', '')} | 场景 {row.get('scene', '?')} | 回合 {row.get('turn', '?')} {row.get('error', '')}")
                continue
            if not valid_slot(slot):
                print_fn("存档槽无效：请使用数字或简单名称。")
                continue
            path = save_path if slot == "quick" else save_path.with_name(f"{save_path.stem}-{slot}.json")
            try:
                if cmd.verb == "save":
                    save_game(engine.state, story, path)
                    print_fn(f"已存档：{path}")
                else:
                    state, notes = load_game(path, story)
                    for note in notes:
                        print_fn(note)
                    engine = Engine(story, state)
                    out = engine.start()
                    render(out, print_fn)
            except SaveError as exc:
                print_fn(f"存读档失败：{exc}")
            continue
        before_turn = engine.state.turn
        try:
            out = engine.handle(cmd)
        except RuleError as exc:
            # 剧本错误不应让玩家看到崩溃；validator 应在开发阶段拦截这类问题
            print_fn(f"[剧本错误] {exc}")
            continue
        if engine.state.turn != before_turn or (out.ended and cmd.verb == "choose"):
            try:
                save_game(engine.state, story, save_path.with_name(f"{save_path.stem}-auto.json"))
            except SaveError as exc:
                print_fn(f"自动存档失败，当前进度仍保留：{exc}")
        render(out, print_fn)
