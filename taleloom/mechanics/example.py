"""最小示例：铃铛插件。负责人：ZQO。

在 mechanics 中加入 example；bell_rung 条件检查是否摇过铃，
ring_bell 效果（参数为 null）摇一次铃，ring 动词演示命令与图形动作。
只修改 state.ext['example']，不修改剧本或其他插件状态，不读写文件。
"""
from .base import Mechanic
from ..rules import RuleError
from ..ui_contract import ActionSpec


class BellMechanic(Mechanic):
    """可独立启用的教学插件，演示条件、效果、动词和图形动作。"""
    name = 'example'
    verbs = {'ring': ['摇铃', 'ring']}
    provides_conditions = ('bell_rung',)
    provides_effects = ('ring_bell',)

    def register(self, registry):
        """登记条件和效果；重名由 Registry 拒绝。"""
        registry.register_condition('bell_rung', self._rung)
        registry.register_effect('ring_bell', self._ring)

    @staticmethod
    def _rung(ctx, expected):
        if type(expected) is not bool:
            raise RuleError('bell_rung 参数应为布尔值')
        return (ctx.state.ext.get('example', {}).get('rings', 0) > 0) == expected

    @staticmethod
    def _ring(ctx, value):
        if value is not None:
            raise RuleError('ring_bell 参数应为 null')
        data = ctx.state.plugin('example')
        data['rings'] = data.get('rings', 0) + 1
        ctx.say('铃响了一声。')

    def handle(self, engine, cmd, ctx):
        """摇铃消耗一个回合，非法参数不修改状态。"""
        if cmd.args:
            ctx.say('摇铃不需要参数。')
            return False
        engine.registry.apply(ctx, [{'ring_bell': None}])
        return True

    def actions(self, engine):
        """提供与命令行等价的图形操作。"""
        return [ActionSpec('example:ring', '摇铃')]

    def help_lines(self):
        """返回示例动词说明。"""
        return ['示例命令：摇铃（ring）。']
