"""命令解析：玩家输入的文字 → model.Command。负责人：ZRS。

支持中英文命令、全角字符、选项编号、直接输入选项文字。
解析器不了解剧情，只依赖当前可选项文字和插件声明的动词别名。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from .model import Command

BUILTIN_VERBS: dict[str, list[str]] = {
    "look": ["look", "l", "看", "查看", "观察", "环顾"],
    "inventory": ["inventory", "inv", "i", "背包", "物品", "道具"],
    "help": ["help", "h", "?", "帮助", "说明"],
    "quit": ["quit", "exit", "q", "退出"],
    "save": ["save", "存档"],
    "load": ["load", "读档"],
    "choose": ["choose", "选", "选择"],
}

_ARG_SPLIT = re.compile(r"\s+|和|与|跟|,|，|、")
# “把 扳手 用在 控制面板 上”“扳手用在控制面板上” → use_on [扳手, 控制面板]
_USE_ON = re.compile(r"^(?:把\s*)?(.+?)\s*用在\s*(.+?)\s*上?$")


def normalize(text: str) -> str:
    """统一全角/半角、大小写和空白。

    >>> normalize("  ＬＯＯＫ　 ")
    'look'
    >>> normalize("指认　管家")
    '指认 管家'
    >>> normalize("３")
    '3'
    """
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def split_args(rest: str) -> list[str]:
    """拆分动词后面的参数。

    >>> split_args("扳手 胶带")
    ['扳手', '胶带']
    >>> split_args("扳手和胶带")
    ['扳手', '胶带']
    >>> split_args("")
    []
    """
    return [a for a in _ARG_SPLIT.split(rest.strip()) if a]


def parse(
    text: str,
    choices: Iterable[tuple[int, str]] = (),
    extra_verbs: dict[str, list[str]] | None = None,
) -> Command:
    """把一行输入解析为 Command。

    >>> parse("2").verb, parse("2").args
    ('choose', ['2'])
    >>> parse("背包").verb
    'inventory'
    >>> parse("走进书房", choices=[(1, "走进书房"), (2, "离开")]).args
    ['1']
    >>> parse("xyzzy").verb
    'unknown'
    """
    raw = text
    t = normalize(text)
    if not t:
        return Command("noop", raw=raw)
    if t.isdigit():
        return Command("choose", [t], raw)

    choices = list(choices)
    for index, label in choices:
        if t == normalize(label):
            return Command("choose", [str(index)], raw)

    aliases = _alias_table(extra_verbs)
    if "use_on" in (extra_verbs or {}):
        match = _USE_ON.match(t)
        if match:
            items = [a.strip() for a in match.groups() if a.strip()]
            return Command("use_on", items, raw)

    head, _, rest = t.partition(" ")
    if head in aliases:
        return Command(aliases[head], split_args(rest), raw)
    # 中文常不加空格：“指认管家”“组合扳手和胶带”
    for alias in sorted(aliases, key=len, reverse=True):
        if not alias.isascii() and t.startswith(alias):
            return Command(aliases[alias], split_args(t[len(alias):]), raw)

    matches = [i for i, label in choices if len(t) >= 2 and t in normalize(label)]
    if len(matches) == 1:
        return Command("choose", [str(matches[0])], raw)
    return Command("unknown", [], raw)


def _alias_table(extra: dict[str, list[str]] | None) -> dict[str, str]:
    table: dict[str, str] = {}
    for source in (BUILTIN_VERBS, extra or {}):
        for verb, names in source.items():
            for name in names:
                table[normalize(name)] = verb
    return table
