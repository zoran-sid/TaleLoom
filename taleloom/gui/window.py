"""Tkinter + ttk 桌面窗口。负责人：ZRS。

窗口只负责绘制 GameController 的 view 并转发点击；游戏规则、存档与
错误判断都在会话层，界面不读取引擎状态。所有玩家操作可点击完成：
场景选项、使用／组合／用在某处道具、存读档、重新开始与返回书架。

键盘：场景标题获得焦点，Tab 在按钮间移动；回车执行当前按钮。
查看背包、线索与资源只是重绘，不会推进回合。
"""

from __future__ import annotations
from tkinter import filedialog

import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from ..ui_contract import ActionSpec, ViewSnapshot, StorageError
from .controller import GameController

FONT_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI")
SERIF_CANDIDATES = ("Songti SC", "SimSun", "Georgia", "Times New Roman")
SIDEBAR_WIDTH = 258
INK = "#292e2b"
MUTED = "#62665f"
PAPER = "#f3f2ee"
WHITE = "#fffefa"
ACCENT = "#315c4d"
LINE = "#cfcec5"


class ScrollableFrame(ttk.Frame):
    """纵向滚动容器；内容宽度跟随窗口，长文本与大量按钮始终可达。"""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=PAPER)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(sequence, self._on_wheel)

    def _on_resize(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event: tk.Event) -> None:
        delta = 0
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        elif getattr(event, "delta", 0):
            delta = -1 if event.delta > 0 else 1
        if delta:
            self.canvas.yview_scroll(delta * 3, "units")

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0.0)


class TaleLoomWindow:
    """书架与游戏页；一次只显示一页，状态来自 controller。"""

    def __init__(self, root: tk.Tk, controller: GameController):
        self.root = root
        self.controller = controller
        self._busy = False
        self._narrow = False
        self._story_buttons: dict[str, ttk.Button] = {}
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self._setup_fonts()
        self._setup_styles()
        self._build_library()
        self._build_game()
        self.show_library()

    # ---------- 外观 ----------
    def _setup_fonts(self) -> None:
        families = set(tkfont.families(self.root))
        self.font_ui = tkfont.Font(
            root=self.root, family=next((f for f in FONT_CANDIDATES if f in families), "TkDefaultFont"),
            size=11)
        self.font_title = tkfont.Font(
            root=self.root, family=next((f for f in SERIF_CANDIDATES if f in families), self.font_ui.actual("family")),
            size=20, weight="normal")
        self.font_scene = tkfont.Font(
            root=self.root, family=next((f for f in SERIF_CANDIDATES if f in families), self.font_ui.actual("family")),
            size=13)
        self.font_small = tkfont.Font(root=self.root, family=self.font_ui.actual("family"), size=10)

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=PAPER)
        style.configure("Card.TFrame", background=WHITE, relief="solid", borderwidth=1)
        style.configure("TLabel", background=PAPER, foreground=INK, font=self.font_ui)
        style.configure("Muted.TLabel", foreground=MUTED, font=self.font_small)
        style.configure("Title.TLabel", font=self.font_title, foreground=INK)
        style.configure("Scene.TLabel", font=self.font_scene, foreground=INK)
        style.configure("Card.TLabel", background=WHITE, foreground=INK)
        style.configure("CardMuted.TLabel", background=WHITE, foreground=MUTED, font=self.font_small)
        style.configure("TButton", padding=(12, 7), font=self.font_ui)
        style.configure("Primary.TButton", padding=(14, 8), font=self.font_ui)
        style.map("Primary.TButton",
                  background=[("active", "#234738"), ("disabled", "#7e968b")],
                  foreground=[("disabled", "#efefef")])
        style.configure("Choice.TButton", anchor="w", padding=(14, 11), font=self.font_ui)
        style.configure("TNotebook", background=PAPER)
        style.configure("TCombobox", padding=(6, 5))
        style.configure("Section.TLabel", font=self.font_small, foreground=MUTED)

    def _wrap(self) -> int:
        """按页面实际可视宽度换行；窄窗口下笔记移到底部，正文占满整行。"""
        width = self.scroller.canvas.winfo_width() if hasattr(self, "scroller") else 640
        if width <= 1:
            width = self.root.winfo_width() or 640
        available = width - 24 if self._narrow else width - SIDEBAR_WIDTH - 48
        return max(320, available)

    # ---------- 书架 ----------
    def _build_library(self) -> None:
        self.library = ttk.Frame(self.root, padding=(32, 24))
        self.library.grid(row=0, column=0, sticky="nsew")
        self.library.columnconfigure(0, weight=1)
        ttk.Label(self.library, text="TaleLoom 织境", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.library, text="原创文字冒险 · 选择一部剧本开始阅读", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 18))
        self.catalog_problem = ttk.Label(self.library, style="Muted.TLabel", wraplength=760)
        self.catalog_problem.grid(row=2, column=0, sticky="w")
        self.open_error = ttk.Label(self.library, style="Muted.TLabel", wraplength=760, foreground="#8a3324")
        self.open_error.grid(row=3, column=0, sticky="w", pady=(0, 8))
        self.open_error.grid_remove()
        self.shelf = ttk.Frame(self.library)
        self.shelf.grid(row=4, column=0, sticky="nsew")
        self.shelf.columnconfigure(0, weight=1)
        self.library.rowconfigure(4, weight=1)

    def _fill_shelf(self) -> None:
        for child in self.shelf.winfo_children():
            child.destroy()
        self._story_buttons.clear()
        for row, entry in enumerate(self.controller.stories):
            card = ttk.Frame(self.shelf, style="Card.TFrame", padding=(20, 16))
            card.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            card.columnconfigure(0, weight=1)
            ttk.Label(card, text=entry.genre, style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=entry.title, style="Title.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 6))
            ttk.Label(card, text=f"目录 {entry.id}", style="CardMuted.TLabel").grid(row=2, column=0, sticky="w")
            buttons = ttk.Frame(card, style="Card.TFrame")
            buttons.grid(row=1, column=1, rowspan=2, sticky="e")
            start = ttk.Button(buttons, text="开始阅读", style="Primary.TButton",
                               command=lambda i=entry.id: self._start(i, False))
            start.pack(side="left", padx=(6, 0))
            self._story_buttons[entry.id] = start
            if self.controller.has_save(entry.id):
                ttk.Button(buttons, text="继续阅读", command=lambda i=entry.id: self._start(i, True)).pack(
                    side="left", padx=(6, 0))
        problems = self.controller.problems
        self.catalog_problem.configure(text="\n".join(problems), foreground="#8a3324")

    def show_library(self) -> None:
        self.controller.home()
        self.controller.load_catalog()
        self._fill_shelf()
        self.open_error.grid_remove()
        self.game.grid_remove()
        self.library.grid()
        self._set_busy(False)
        first = next(iter(self._story_buttons.values()), None)
        if first is not None:
            first.focus_set()

    # ---------- 游戏页 ----------
    def _build_game(self) -> None:
        self.game = ttk.Frame(self.root, padding=(28, 18))
        self.game.grid(row=0, column=0, sticky="nsew")
        self.game.columnconfigure(0, weight=1)
        self.game.rowconfigure(1, weight=1)

        nav = ttk.Frame(self.game)
        nav.grid(row=0, column=0, sticky="ew")
        nav.columnconfigure(1, weight=1)
        self.home_button = ttk.Button(nav, text="← 返回书架", command=self._go_home)
        self.home_button.grid(row=0, column=0, sticky="w")
        self.story_label = ttk.Label(nav, style="Muted.TLabel")
        self.story_label.grid(row=0, column=1, sticky="w", padx=14)
        self.save_button = ttk.Button(nav, text="保存进度", command=self._save)
        self.save_button.grid(row=0, column=2, padx=(0, 6))
        self.load_button = ttk.Button(nav, text="读取存档", command=self._load)
        self.load_button.grid(row=0, column=3, padx=(0, 6))
        slotbar = ttk.Frame(nav)
        slotbar.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(6, 0))
        self.slot_name = tk.StringVar(value="快速存档")
        ttk.Label(slotbar, text="存档位置：").pack(side="left")
        ttk.Combobox(slotbar, textvariable=self.slot_name, state="readonly", width=12,
                     values=("快速存档", "存档 1", "存档 2", "存档 3", "自动存档")).pack(side="left")
        ttk.Button(slotbar, text="存档列表", command=self._list_saves).pack(side="left", padx=6)
        ttk.Button(slotbar, text="导出", command=self._export_json).pack(side="left", padx=2)
        ttk.Button(slotbar, text="导入", command=self._import_json).pack(side="left", padx=2)

        self.restart_button = ttk.Button(nav, text="重新开始", command=self._restart)
        self.restart_button.grid(row=0, column=4)
        ttk.Separator(self.game).grid(row=0, column=0, sticky="sew", pady=(44, 0))

        self.scroller = ScrollableFrame(self.game)
        self.scroller.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self.body = self.scroller.body
        self.body.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, minsize=258, weight=0)

        page = ttk.Frame(self.body)
        page.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
        page.columnconfigure(0, weight=1)
        self.page = page
        self.chapter_label = ttk.Label(page, style="Muted.TLabel")
        self.chapter_label.grid(row=0, column=0, sticky="w")
        self.scene_title = ttk.Label(page, style="Title.TLabel")
        self.scene_title.grid(row=1, column=0, sticky="w", pady=(10, 10))
        self.scene_text = ttk.Label(page, style="Scene.TLabel", justify="left")
        self.scene_text.grid(row=2, column=0, sticky="w")
        self.messages = tk.Label(page, justify="left", anchor="w", background="#e9ece4", foreground=INK,
                                 font=self.font_ui, padx=12, pady=8, wraplength=self._wrap())
        self.messages.grid(row=3, column=0, sticky="ew", pady=(16, 0))

        self.choices_title = ttk.Label(page, text="你的下一步", style="Section.TLabel")
        self.choices = ttk.Frame(page)
        self.actions_title = ttk.Label(page, text="道具与行动", style="Section.TLabel")
        self.actions = ttk.Frame(page)
        self.ending = ttk.Frame(page, style="Card.TFrame", padding=(18, 14))
        self.status_label = ttk.Label(page, style="Muted.TLabel", wraplength=self._wrap(), foreground="#8a3324")

        self.body.bind("<Configure>", self._on_body_resize)

        sidebar = ttk.Frame(self.body)
        sidebar.grid(row=0, column=1, sticky="nsew")
        self.sidebar = sidebar
        ttk.Label(sidebar, text="随身笔记", style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        self.resources = ttk.Frame(sidebar)
        self.resources.pack(anchor="w", fill="x")
        ttk.Label(sidebar, text="背包", style="Section.TLabel").pack(anchor="w", pady=(10, 4))
        self.inventory = ttk.Frame(sidebar)
        self.inventory.pack(anchor="w", fill="x")
        ttk.Label(sidebar, text="已发现的线索", style="Section.TLabel").pack(anchor="w", pady=(14, 4))
        self.clues = ttk.Frame(sidebar)
        self.clues.pack(anchor="w", fill="x")
        ttk.Label(sidebar, text="阅读笔记不会消耗回合。", style="Muted.TLabel").pack(anchor="w", pady=(14, 0))

    def _on_body_resize(self, event: tk.Event) -> None:
        """窗口较窄时把笔记移到正文下方，避免正文被挤成一条窄栏。"""
        narrow = event.width < 760
        if narrow != self._narrow:
            self._narrow = narrow
            gap = (0, 22) if narrow else (0, 24)
            self.page.grid_configure(row=0, column=0, columnspan=2 if narrow else 1, padx=gap,
                                     pady=(26, 0) if narrow else (0, 0))
            self.sidebar.grid_configure(row=1 if narrow else 0, column=0 if narrow else 1, sticky="nsew")
        self._refresh_wrap()

    def _refresh_wrap(self) -> None:
        width = self._wrap()
        self.scene_text.configure(wraplength=width)
        self.messages.configure(wraplength=width)
        self.status_label.configure(wraplength=width)

    def _start(self, story_id: str, resume: bool) -> None:
        if self.controller.start(story_id, resume):
            self._show_game()
            return
        # 失败时留在书架并显示原因；show_library 会清掉 controller.error。
        failed = self.controller.error or "无法打开这个剧本。"
        self.controller.home()
        self.controller.load_catalog()
        self._fill_shelf()
        self.game.grid_remove()
        self.library.grid()
        self._set_busy(False)
        self.open_error.configure(text=failed)
        self.open_error.grid()
        first = next(iter(self._story_buttons.values()), None)
        if first is not None:
            first.focus_set()

    def _show_game(self) -> None:
        self.library.grid_remove()
        self.game.grid()
        self.render()
        self.scene_title_focus()

    def render(self) -> None:
        view = self.controller.view
        if view is None:
            return
        self.story_label.configure(
            text=f"{view.story_title} · 第 {view.turn} 回合 · 进度{'未保存' if self.controller.dirty else '已保存'}")
        self.chapter_label.configure(
            text=f"结局 · {view.ending_title or view.ending_id}" if view.ended else "故事进行中")
        self.scene_title.configure(text=view.scene_title)
        self.scene_text.configure(text=view.text, wraplength=self._wrap())
        if self.controller.messages:
            self.messages.configure(text="\n".join(self.controller.messages))
            self.messages.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        else:
            self.messages.grid_remove()
        if self.controller.error:
            self.status_label.configure(text=self.controller.error)
            self.status_label.grid(row=9, column=0, sticky="w", pady=(12, 0))
        else:
            self.status_label.grid_remove()
        self._render_choices(view)
        self._render_actions(view)
        self._render_notebook(view)
        self._render_ending(view)

    def _render_choices(self, view: ViewSnapshot) -> None:
        for child in self.choices.winfo_children():
            child.destroy()
        if view.ended or not view.choices:
            self.choices_title.grid_remove()
            self.choices.grid_remove()
            return
        self.choices_title.grid(row=4, column=0, sticky="w", pady=(20, 6))
        self.choices.grid(row=5, column=0, sticky="ew")
        self.choices.columnconfigure(0, weight=1)
        for row, choice in enumerate(view.choices, 1):
            text = f"{row}. {choice.label}" if len(view.choices) > 1 else choice.label
            ttk.Button(
                self.choices, text=text, style="Choice.TButton",
                command=lambda c=choice: self._submit_values(c.id, {}),
                state="normal" if choice.enabled else "disabled",
            ).grid(row=row - 1, column=0, sticky="ew", pady=(0, 2))

    def _render_actions(self, view: ViewSnapshot) -> None:
        for child in self.actions.winfo_children():
            child.destroy()
        self.actions_title.grid(row=6, column=0, sticky="w", pady=(18, 6))
        self.actions.grid(row=7, column=0, sticky="ew")
        if not view.actions or view.ended:
            self.actions_title.grid_remove()
            self.actions.grid_remove()
            return
        for index, action in enumerate(view.actions):
            self._render_action_form(action, index)
            self.actions.columnconfigure(index, weight=1)

    def _render_action_form(self, action: ActionSpec, row: int) -> None:
        """每个参数一行：标签在上、控件占满整行，递交按钮单独一行。

        指认需要四个参数；横排会让表单比窗口还宽，递交按钮被挤出可视区域，
        所以这里按纵向排布，任何窗口宽度下都能完整操作。
        """
        card = ttk.Frame(self.actions, style="Card.TFrame", padding=(14, 12))
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=action.label, style="Card.TLabel").grid(row=0, column=0, sticky="w")
        if action.disabled_reason:
            ttk.Label(card, text=action.disabled_reason, style="CardMuted.TLabel").grid(
                row=1, column=0, sticky="w", pady=(4, 0))
        variables = {}
        next_row = 2
        for parameter in action.parameters:
            ttk.Label(card, text=parameter.label, style="CardMuted.TLabel").grid(
                row=next_row, column=0, sticky="w", pady=(8, 2))
            if parameter.kind == "text":
                var = tk.StringVar()
                control = ttk.Entry(card, textvariable=var)
            else:
                labels = [option.label for option in parameter.options]
                var = tk.StringVar(value=labels[0] if labels else "")
                if parameter.key == "second" and len(labels) > 1:
                    var.set(labels[1])
                control = ttk.Combobox(
                    card, textvariable=var, values=labels,
                    state="disabled" if not action.enabled else "readonly")
            if action.enabled and parameter.kind == "text":
                control.configure(state="normal")
            control.grid(row=next_row + 1, column=0, sticky="ew")
            variables[parameter.key] = (var, parameter)
            next_row += 2
        ttk.Button(
            card, text=action.label, state="disabled" if (self._busy or not action.enabled) else "normal",
            command=lambda spec=action, vars_=variables: self._submit_parameters(spec, vars_),
        ).grid(row=next_row, column=0, sticky="ew", pady=(10, 0))

    def _submit_parameters(self, action: ActionSpec, variables: dict) -> None:
        values = {}
        for key, (var, parameter) in variables.items():
            text = var.get().strip()
            if parameter.kind == "text":
                if not text:
                    self._status(f"请填写{parameter.label}。")
                    return
                values[key] = text
                continue
            option = next((o for o in parameter.options if o.label == text), None)
            if option is None:
                self._status(f"请选择有效的{parameter.label}。")
                return
            values[key] = option.id
        if action.id == "mystery:accuse":
            if not messagebox.askyesno("确认指认", "指认会直接决定故事结局，确定要指认吗？", parent=self.root):
                return
        self._submit_values(action.id, values)

    def _submit_values(self, action_id: str, values: dict[str, str]) -> None:
        self._set_busy(True)
        self.root.update_idletasks()
        try:
            result = self.controller.submit(action_id, values)
        finally:
            self._set_busy(False)
        self.render()
        if result is not None and result.ok and not result.view.ended:
            self.scene_title_focus()

    def _render_notebook(self, view: ViewSnapshot) -> None:
        for child in self.resources.winfo_children():
            child.destroy()
        for resource in view.resources:
            maximum = f" / {resource.maximum}" if resource.maximum is not None else ""
            row = ttk.Frame(self.resources)
            row.pack(fill="x", pady=(0, 4))
            ttk.Label(row, text=resource.label, style="Muted.TLabel").pack(side="left")
            tk.Label(row, text=f"{resource.value}{maximum}", background=PAPER, foreground=INK,
                     font=self.font_title).pack(side="right")
        _fill_notes(self.inventory, view.inventory, "尚未携带物品。", self.font_ui, self.font_small)
        _fill_notes(self.clues, view.clues, "还没有发现线索。", self.font_ui, self.font_small)

    def _render_ending(self, view: ViewSnapshot) -> None:
        for child in self.ending.winfo_children():
            child.destroy()
        if not view.ended:
            self.ending.grid_remove()
            return
        self.ending.grid(row=8, column=0, sticky="ew", pady=(18, 0))
        failed = self.controller.failed
        title = "这一页，任务失败。" if failed else "这一页，已写下结局。"
        ttk.Label(self.ending, text=title, style="Card.TLabel").pack(anchor="w")
        if failed:
            ttk.Label(self.ending, style="CardMuted.TLabel",
                      text=f"还剩 {self.controller.chances_left} 次机会回到上一个选择；"
                           f"回到存档点不消耗机会。").pack(anchor="w", pady=(6, 0))
        buttons = ttk.Frame(self.ending, style="Card.TFrame")
        buttons.pack(anchor="w", pady=(10, 0))
        if self.controller.can_rewind:
            ttk.Button(buttons, text=f"回到上一个选择（还剩 {self.controller.chances_left} 次）",
                       style="Primary.TButton", command=self._rewind).pack(side="left")
        ttk.Button(buttons, text="再读一遍", style="Primary.TButton", command=self._restart).pack(
            side="left", padx=(8, 0))
        ttk.Button(buttons, text="返回书架", command=self._go_home).pack(side="left", padx=(8, 0))
        self._render_checkpoints(failed)

    def _render_checkpoints(self, failed: bool) -> None:
        """结局页列出关键节点自动存档；失败时可直接回到任一存档点。"""
        rows = self.controller.checkpoints
        if not rows:
            return
        box = ttk.Frame(self.ending, style="Card.TFrame")
        box.pack(anchor="w", fill="x", pady=(14, 0))
        ttk.Label(box, text="关键节点自动存档", style="CardMuted.TLabel").pack(anchor="w")
        for row in rows:
            line = ttk.Frame(box, style="Card.TFrame")
            line.pack(anchor="w", fill="x", pady=(4, 0))
            ttk.Label(line, style="CardMuted.TLabel",
                      text=f"{row['label']} · 回合 {row['turn']}").pack(side="left")
            ttk.Button(line, text="回到这里", command=lambda slot=row["slot"]: self._rollback(slot)).pack(
                side="left", padx=(10, 0))

    def _rewind(self) -> None:
        if not messagebox.askyesno(
                "回到上一个选择",
                f"回到上一个选择会消耗 1 次机会（还剩 {self.controller.chances_left} 次），继续吗？",
                parent=self.root):
            return
        if self.controller.rewind():
            self.render()

    def _rollback(self, slot: str) -> None:
        if not messagebox.askyesno(
                "回到存档点", "回到存档点后，这个存档点之后的进度会作废。继续吗？", parent=self.root):
            return
        if self.controller.rollback_to(slot):
            self.render()

    # ---------- 操作 ----------
    def _status(self, message: str) -> None:
        self.controller.error = message
        self.status_label.configure(text=message, wraplength=self._wrap())
        self.status_label.grid(row=9, column=0, sticky="w", pady=(12, 0))

    def _export_json(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json", filetypes=[("JSON 存档", "*.json")])
        if path:
            self.controller.export_json(path)
            self.render()

    def _import_json(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("JSON 存档", "*.json")])
        if path and messagebox.askyesno("导入存档", "导入会替换当前未保存的进度，继续吗？", parent=self.root):
            self.controller.import_json(path)
            self.render()

    def _selected_slot(self) -> str:
        return {"快速存档": "quick", "自动存档": "auto", "存档 1": "1", "存档 2": "2", "存档 3": "3"}[self.slot_name.get()]

    def _list_saves(self) -> None:
        try:
            rows = self.controller.list_saves()
        except StorageError as exc:
            self._status(str(exc))
            return
        text = "\n".join(f"{r['slot']}  {r.get('saved_at', '')}\n场景 {r.get('scene', '未知')} · 回合 {r.get('turn', '?')} {r.get('error', '')}" for r in rows)
        messagebox.showinfo("存档列表", text or "还没有存档。", parent=self.root)

    def _save(self) -> None:
        slots = self._available_slots()
        if slots is None:
            return
        if self.controller._slot(self.controller.story.id, self._selected_slot()) in slots:
            if not messagebox.askyesno("覆盖存档", "已经有存档，覆盖它吗？", parent=self.root):
                return
        self.controller.save(self._selected_slot())
        self.render()

    def _available_slots(self):
        try:
            return self.controller.store.list_slots()
        except StorageError as exc:
            self._status(str(exc))
            return None

    def _load(self) -> None:
        selected = self.controller._slot(self.controller.story.id, self._selected_slot())
        slots = self._available_slots()
        if slots is None:
            return
        if selected not in slots:
            self._status("还没有保存过这个位置的进度，先点“保存进度”。")
            return
        if not messagebox.askyesno("读取存档", "读取存档会替换当前未保存的进度，继续吗？", parent=self.root):
            return
        self.controller.load(self._selected_slot())
        self.render()

    def _restart(self) -> None:
        if self.controller.dirty and not messagebox.askyesno(
                "重新开始", "重新开始会离开当前未保存的进度，继续吗？", parent=self.root):
            return
        if self.controller.restart():
            self.render()

    def _go_home(self) -> None:
        if self.controller.dirty and not messagebox.askyesno(
                "返回书架", "返回书架会离开当前未保存的进度，继续吗？", parent=self.root):
            return
        self.show_library()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for name in ("home_button", "save_button", "load_button", "restart_button"):
            getattr(self, name).configure(state="disabled" if busy else "normal")

    def scene_title_focus(self) -> None:
        """把焦点放到场景标题；屏幕阅读与键盘用户从新场景开始 Tab。"""
        self.scene_title.configure(takefocus=1)
        self.scene_title.focus_set()

    def on_close(self) -> None:
        if self.controller.dirty:
            if not messagebox.askyesno("退出", "当前进度还没有保存，确定退出吗？", parent=self.root):
                return
        self.root.destroy()


def _fill_notes(container: ttk.Frame, items, empty: str, font_ui, font_small) -> None:
    for child in container.winfo_children():
        child.destroy()
    if not items:
        ttk.Label(container, text=empty, style="Muted.TLabel").pack(anchor="w")
        return
    for item in items:
        card = ttk.Frame(container, style="Card.TFrame", padding=(10, 8))
        card.pack(fill="x", pady=(0, 6))
        ttk.Label(card, text=item.label, style="Card.TLabel", font=font_ui).pack(anchor="w")
        if item.description:
            ttk.Label(card, text=item.description, style="CardMuted.TLabel",
                      wraplength=240, justify="left").pack(anchor="w", pady=(3, 0))
