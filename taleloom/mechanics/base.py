"""机制插件基类。负责人：ZQO（接口），各插件由其负责人实现。

一个剧本在 "mechanics" 字段里声明要启用的插件。插件可以：
1. 在 register() 中注册新的条件和效果；
2. 在 verbs 中声明新的玩家动词，并在 handle() 中处理；
3. 在 validate() 中检查剧本里属于自己的数据段。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..model import Command, Issue, Story
from ..rules import Context, Registry

if TYPE_CHECKING:
    from ..engine import Engine


class Mechanic:
    name: str = ""
    # 动词 -> 玩家可输入的别名（解析器据此识别命令）
    verbs: dict[str, list[str]] = {}
    # 本插件注册的条件/效果名，供 validator 在插件未启用时给出准确提示
    provides_conditions: tuple[str, ...] = ()
    provides_effects: tuple[str, ...] = ()

    def register(self, registry: Registry) -> None:
        """注册条件与效果。"""

    def handle(self, engine: "Engine", cmd: Command, ctx: Context) -> bool:
        """处理本插件的动词，输出写入 ctx。返回 True 表示消耗一个回合。"""
        raise NotImplementedError

    def validate(self, story: Story) -> list[Issue]:
        return []

    def help_lines(self) -> list[str]:
        return []
