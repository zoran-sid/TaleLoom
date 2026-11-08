"""桌面 GUI 包入口。负责人：ZRS。

``run(stories_dir, saves_dir) -> int`` 是 main.py 无参数启动时调用的约定入口，
返回进程退出码。窗口打开失败（没有显示器、Tcl/Tk 损坏）返回 1 并说明原因。
"""

from __future__ import annotations

import sys
from pathlib import Path


def run(stories_dir: Path, saves_dir: Path) -> int:
    """打开桌面窗口，直到玩家关闭窗口后返回 0。"""
    try:
        import tkinter as tk
    except ImportError:
        print("当前 Python 没有安装 Tkinter（Tcl/Tk），无法打开桌面界面。", file=sys.stderr)
        print("请安装带 Tcl/Tk 的 Python，或改用 python main.py play 在命令行游玩。", file=sys.stderr)
        return 1
    from ..session_factory import create_session
    from .controller import GameController
    from .window import TaleLoomWindow

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"无法打开桌面窗口：{exc}", file=sys.stderr)
        print("当前环境可能没有图形显示；可以改用 python main.py play 在命令行游玩。", file=sys.stderr)
        return 1
    root.title("TaleLoom 织境")
    root.geometry("1020x720")
    root.minsize(560, 420)
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    root.option_add("*tearOff", False)
    root.configure(background="#f3f2ee")
    controller = GameController(stories_dir, saves_dir, create_session)
    window = TaleLoomWindow(root, controller)
    root.protocol("WM_DELETE_WINDOW", window.on_close)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()
    return 0
