"""引擎核心：接收 Command，修改 GameState，返回 Output。负责人：ZQO。

引擎不读写文件、不调用 input/print，界面与存档都在外层，
因此可以在单元测试里直接驱动。
"""

from __future__ import annotations

from .mechanics import create_mechanic
from .mechanics.base import Mechanic
from .model import Choice, Command, Output, Scene, Story
from .rules import Context, Registry, RuleError, default_registry
from .state import GameState

MAX_CHAINED_MOVES = 20


class Engine:
    def __init__(
        self,
        story: Story,
        state: GameState | None = None,
        registry: Registry | None = None,
    ) -> None:
        self.story = story
        self.registry = registry or default_registry()
        self.mechanics: dict[str, Mechanic] = {}
        for name in story.mechanics:
            mech = create_mechanic(name)
            mech.register(self.registry)
            self.mechanics[name] = mech
        self._resumed = state is not None
        self.state = state or GameState(
            story_id=story.id, scene=story.start, vars=dict(story.initial_vars)
        )

    # ---------- 对外接口 ----------
    def start(self) -> Output:
        ctx = self._ctx()
        if self._resumed:
            ctx.say(f"（继续游戏：第 {self.state.turn} 回合）")
            self._describe(self.scene, ctx)
        else:
            ctx.say(f"《{self.story.title}》")
            self._move(ctx, self.story.start)
        return self._output(ctx)

    def handle(self, cmd: Command) -> Output:
        ctx = self._ctx()
        if cmd.raw and cmd.verb not in ("noop", "unknown"):
            self.state.history.append(cmd.raw)

        if self.state.ending and cmd.verb not in ("look", "help", "inventory", "noop"):
            ctx.say("故事已经结束。可以读档或重新开始。")
            return self._output(ctx)

        if cmd.verb == "choose":
            self._choose(cmd.target, ctx)
        elif cmd.verb == "look":
            self._describe(self.scene, ctx)
        elif cmd.verb == "inventory":
            self._inventory(ctx)
        elif cmd.verb == "help":
            self._help(ctx)
        elif cmd.verb == "noop":
            pass
        else:
            mech = self._mechanic_for(cmd.verb)
            if mech is None:
                ctx.say(f"无法理解“{cmd.raw or cmd.verb}”。输入“帮助”查看可用命令。")
            elif mech.handle(self, cmd, ctx):
                self._move(ctx, ctx.goto)
                self._end_turn(ctx)
        return self._output(ctx)

    @property
    def scene(self) -> Scene:
        return self.story.scenes[self.state.scene]

    def available_choices(self) -> list[Choice]:
        if self.state.ending:
            return []
        ctx = self._ctx()
        result = []
        for choice in self.scene.choices:
            key = f"{self.scene.id}/{choice.id}"
            if choice.once and key in self.state.used_choices:
                continue
            if self.registry.check(ctx, choice.when):
                result.append(choice)
        return result

    def verb_aliases(self) -> dict[str, list[str]]:
        """所有已启用插件的动词别名，交给解析器使用。"""
        merged: dict[str, list[str]] = {}
        for mech in self.mechanics.values():
            for verb, aliases in mech.verbs.items():
                merged.setdefault(verb, []).extend(aliases)
        return merged

    # ---------- 内部流程 ----------
    def _ctx(self) -> Context:
        return Context(story=self.story, state=self.state)

    def _choose(self, target: str, ctx: Context) -> None:
        choices = self.available_choices()
        choice = None
        if target.isdigit() and 1 <= int(target) <= len(choices):
            choice = choices[int(target) - 1]
        else:
            choice = next((c for c in choices if c.id == target), None)
        if choice is None:
            ctx.say(f"没有编号为“{target}”的选项。")
            return
        if choice.message:
            ctx.say(choice.message)
        self.registry.apply(ctx, choice.effects)
        if choice.once:
            self.state.used_choices.append(f"{self.scene.id}/{choice.id}")
        self._move(ctx, ctx.goto or choice.goto)
        self._end_turn(ctx)

    def _move(self, ctx: Context, target: str | None) -> None:
        hops = 0
        while target:
            hops += 1
            if hops > MAX_CHAINED_MOVES:
                raise RuleError(f"场景跳转超过 {MAX_CHAINED_MOVES} 次，可能存在循环")
            ctx.goto = None
            self._enter(target, ctx)
            target = ctx.goto
        ctx.goto = None

    def _enter(self, scene_id: str, ctx: Context) -> None:
        if scene_id not in self.story.scenes:
            raise RuleError(f"跳转目标不存在：{scene_id}")
        self.state.scene = scene_id
        if scene_id not in self.state.visited:
            self.state.visited.append(scene_id)
        scene = self.scene
        self._describe(scene, ctx)
        self.registry.apply(ctx, scene.on_enter)
        if scene.ending:
            self.state.ending = scene.ending.get("id", scene_id)
            ctx.say(f"【结局】{scene.ending.get('title', self.state.ending)}")

    def _end_turn(self, ctx: Context) -> None:
        if self.state.ending:
            return
        self.state.turn += 1
        self.registry.apply(ctx, self.story.every_turn)
        for trig in self.story.triggers:
            if trig.once and trig.id in self.state.fired_triggers:
                continue
            if self.registry.check(ctx, trig.when):
                if trig.once:
                    self.state.fired_triggers.append(trig.id)
                self.registry.apply(ctx, trig.effects)
                if ctx.goto:
                    break
        self._move(ctx, ctx.goto)

    def _describe(self, scene: Scene, ctx: Context) -> None:
        if scene.title:
            ctx.say(f"== {scene.title} ==")
        ctx.say(scene.text)

    def _inventory(self, ctx: Context) -> None:
        if not self.state.inventory:
            ctx.say("你身上什么也没有。")
            return
        ctx.say("你携带着：")
        for item_id in self.state.inventory:
            item = self.story.items.get(item_id)
            name = item.name if item else item_id
            desc = f"——{item.description}" if item and item.description else ""
            ctx.say(f"  · {name}{desc}")

    def _help(self, ctx: Context) -> None:
        ctx.say("输入选项编号进行选择。通用命令：看（look）、背包（i）、存档（save）、读档（load）、帮助（help）、退出（quit）。")
        for mech in self.mechanics.values():
            for line in mech.help_lines():
                ctx.say(line)

    def _mechanic_for(self, verb: str) -> Mechanic | None:
        return next((m for m in self.mechanics.values() if verb in m.verbs), None)

    def _output(self, ctx: Context) -> Output:
        choices = [(i + 1, c.text) for i, c in enumerate(self.available_choices())]
        return Output(
            lines=ctx.lines,
            choices=choices,
            ended=self.state.ending is not None,
            ending=self.state.ending,
        )
