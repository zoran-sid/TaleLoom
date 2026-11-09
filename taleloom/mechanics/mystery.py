"""推理机制：线索、深入搜证、审问、分幕与带理由的指认。负责人：ZC。

玩法借鉴剧本杀：线索可以再次调查得到下一级线索；向嫌疑人提问或出示线索
解锁新证词；剧情分幕推进；指认时说明动机、手段与证据，按理由的对错决定结局档次。
除 ``clues`` 与 ``accusation`` 的基本字段外全部可省略，旧剧本不用修改。

剧本数据段::

    "clues": {
        "<线索id>": {
            "name": "被撕去的账页", "text": "...",
            "examine": {"when": <条件>, "hint": "条件不满足时的提示",
                        "text": "深入调查的发现", "effects": [<效果>, ...]}
        }
    },
    "acts": [{"id": "fog", "title": "第一幕 · 雾夜"},
             {"id": "ebb", "title": "第二幕 · 退潮", "text": "过场文字"}],
    "accusation": {
        "when": <条件>,
        "suspects": {
            "<嫌疑人id>": {
                "name": "周文", "aliases": ["周"], "scenes": ["<可以审问他的场景>"],
                "topics": [{"id": "alibi", "name": "案发时在做什么", "aliases": [],
                            "clue": "<出示这条线索才能问>", "when": <条件>,
                            "text": "回答", "effects": [<效果>, ...]}]
            }
        },
        "reasons": [
            {"id": "motive", "label": "动机",
             "options": [{"id": "debt", "name": "欠债", "aliases": [], "when": <条件>}]},
            {"id": "evidence", "label": "关键证据", "from": "clues"}
        ],
        "outcomes": [{"suspect": "<id>", "reasons": {"motive": "debt", "evidence": ["a", "b"]},
                      "min_correct": 2, "when": <条件>, "goto": "<结局场景>"}],
        "default": "<没有匹配时的结局场景>"
    }

条件：``has_clue``（已获得线索）、``clues_found``（已获得线索数 ≥ N）、
``act``（已进入该幕或之后的幕）。效果：``add_clue``、``start_act``（只会向后推进）。

玩家命令：``线索``、``调查 <线索>``、``问 <嫌疑人> <话题或线索>``、
``指认 <嫌疑人> <各项理由…>``。图形界面使用 :func:`build_actions` 生成的
``mystery:examine``（参数 clue）、``mystery:ask``（参数 topic，值为
``嫌疑人id/话题id``）与 ``mystery:accuse``（参数 suspect 及各理由 id）。
候选只含玩家已经知道或当前可以使用的内容，不提示正确答案。

``outcomes`` 从上到下取第一个匹配项：嫌疑人相同、``when`` 成立，且答对的理由
不少于 ``min_correct``（省略时要求 ``reasons`` 里列出的全部答对）；都不匹配时去
``default``。一项理由可以接受多个正确答案，写成数组。
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any, Iterable

from ..model import Command, Issue, Story
from ..rules import Context, Registry, RuleError, default_registry
from ..state import GameState
from ..ui_contract import ActionParameter, ActionSpec, DisplayItem
from ..walk import expand_condition, iter_conditions, iter_effects
from .base import Mechanic

if TYPE_CHECKING:
    from ..engine import Engine

PLUGIN = "mystery"
CLUE_SOURCE = "clues"


class MysteryMechanic(Mechanic):
    """推理插件：线索笔记、深入调查、审问、分幕与指认。"""

    name = PLUGIN
    verbs = {
        "clues": ["线索", "笔记", "clues", "notes"],
        "examine": ["调查", "细查", "examine"],
        "ask": ["问", "审问", "询问", "出示", "ask"],
        "accuse": ["指认", "指控", "accuse"],
    }
    provides_conditions = ("has_clue", "clues_found", "act")
    provides_effects = ("add_clue", "start_act")

    def register(self, registry: Registry) -> None:
        """注册条件与效果；条件只读取状态，读取快照时不会改变存档。"""
        registry.register_condition("has_clue", lambda ctx, cid: cid in found_clues(ctx.state))
        registry.register_condition("clues_found", lambda ctx, n: len(found_clues(ctx.state)) >= n)
        registry.register_condition("act", lambda ctx, act: act_reached(ctx.story, ctx.state, act))
        registry.register_effect("add_clue", self._add_clue)
        registry.register_effect("start_act", self._start_act)

    # ---- 效果 ----
    @staticmethod
    def _mine(ctx: Context) -> dict[str, Any]:
        return ctx.state.plugin(PLUGIN)

    def _add_clue(self, ctx: Context, clue_id: str) -> None:
        found = self._mine(ctx).setdefault("clues", [])
        if clue_id in found:
            return
        found.append(clue_id)
        clue = clue_data(ctx.story).get(clue_id, {})
        ctx.say(f"【获得线索】{clue.get('name', clue_id)}：{clue.get('text', '')}".rstrip("："))

    def _start_act(self, ctx: Context, act_id: str) -> None:
        acts = act_list(ctx.story)
        target = _act_index(acts, act_id)
        if target < 0:
            raise RuleError(f"幕不存在：{act_id}")
        if target <= _act_index(acts, current_act(ctx.story, ctx.state)):
            return
        self._mine(ctx)["act"] = act_id
        ctx.say(f"—— {acts[target].get('title') or act_id} ——")
        if acts[target].get("text"):
            ctx.say(acts[target]["text"])

    # ---- 命令 ----
    def handle(self, engine: "Engine", cmd: Command, ctx: Context) -> bool:
        """处理推理命令；只有获得新信息或作出指认才消耗回合。"""
        if cmd.verb == "clues":
            self._list_clues(ctx)
            return False
        if cmd.verb == "examine":
            return self._examine(engine, cmd.args, ctx)
        if cmd.verb == "ask":
            return self._ask(engine, cmd.args, ctx)
        return self._accuse(engine, cmd.args, ctx)

    def _list_clues(self, ctx: Context) -> None:
        found = found_clues(ctx.state)
        if not found:
            ctx.say("你的笔记本还是空的。")
            return
        clues = clue_data(ctx.story)
        ctx.say(f"已收集线索（{len(found)}/{len(clues)}）：")
        for cid in found:
            clue = clues.get(cid, {})
            ctx.say(f"  · {clue.get('name', cid)}：{clue.get('text', '')}")

    def _examine(self, engine: "Engine", args: list[str], ctx: Context) -> bool:
        clues = clue_data(ctx.story)
        found = [c for c in found_clues(ctx.state) if c in clues]
        if not args:
            options = examinable_clues(ctx.story, ctx.state)
            names = "、".join(_clue_name(ctx.story, c) for c in options)
            ctx.say(f"要深入调查哪条线索？可选：{names}" if names
                    else "要深入调查哪条线索？你的笔记里还没有能深入调查的线索。")
            return False
        text = "".join(args)
        cid = _match(text, ((c, _clue_names(ctx.story, c)) for c in found))
        if cid is None:
            ctx.say(f"你的笔记里没有“{text}”。")
            return False
        name = _clue_name(ctx.story, cid)
        spec = clues[cid].get("examine")
        if not isinstance(spec, dict):
            ctx.say(f"“{name}”暂时看不出更多东西。")
            return False
        if cid in _str_list(_data(ctx.state).get("examined")):
            ctx.say(f"你已经仔细查看过“{name}”了。")
            return False
        if not engine.registry.check(ctx, spec.get("when")):
            ctx.say(spec.get("hint") or f"眼下还看不出“{name}”有什么新东西。")
            return False
        self._mine(ctx).setdefault("examined", []).append(cid)
        ctx.say(f"【深入调查】{name}")
        if spec.get("text"):
            ctx.say(spec["text"])
        engine.registry.apply(ctx, spec.get("effects") or [])
        return True

    def _ask(self, engine: "Engine", args: list[str], ctx: Context) -> bool:
        suspects = suspect_data(ctx.story)
        if not suspects:
            ctx.say("这个故事里没有可以审问的人。")
            return False
        if not args:
            here = "、".join(_name(s, sid) for sid, s in suspects.items()
                            if _present(s, ctx.state.scene))
            ctx.say(f"要审问谁？在场的人：{here}" if here else "要审问谁？这里没有可以审问的人。")
            return False
        topic_text = "".join(args[1:])
        sid, slash, topic_id = args[0].partition("/")
        if not (len(args) == 1 and slash and sid in suspects):
            sid, topic_id = _resolve_suspect(suspects, args[0]), ""
        if sid is None:
            ctx.say(f"这里没有叫“{args[0]}”的人。")
            return False
        suspect = suspects[sid]
        name = _name(suspect, sid)
        if not _present(suspect, ctx.state.scene):
            ctx.say(f"{name}不在这里。")
            return False
        topics = available_topics(ctx.story, ctx.state, engine.registry, sid)
        if not topic_text and not topic_id:
            labels = "、".join(topic_label(ctx.story, t) for t in topics)
            ctx.say(f"可以问{name}：{labels}" if labels else f"{name}现在没什么可说的。")
            return False
        if topic_id:
            topic = next((t for t in topics if t["id"] == topic_id), None)
        else:
            topic = _match(topic_text, ((t, _topic_names(ctx.story, t)) for t in topics))
        if topic is None:
            ctx.say(f"{name}对“{topic_text or topic_id}”没什么可说的。")
            return False
        key = f"{sid}/{topic['id']}"
        if key in _str_list(_data(ctx.state).get("asked")):
            ctx.say("（你又问了一遍。）")
            ctx.say(topic.get("text", ""))
            return False
        self._mine(ctx).setdefault("asked", []).append(key)
        ctx.say(f"【审问】{name} · {topic_label(ctx.story, topic)}")
        ctx.say(topic.get("text", ""))
        engine.registry.apply(ctx, topic.get("effects") or [])
        return True

    def _accuse(self, engine: "Engine", args: list[str], ctx: Context) -> bool:
        acc = accusation_data(ctx.story)
        if not acc:
            ctx.say("这个故事里不需要指认任何人。")
            return False
        if not engine.registry.check(ctx, acc.get("when")):
            ctx.say("你还没有足够的把握，现在不是指认的时候。")
            return False
        suspects = suspect_data(ctx.story)
        names = "、".join(_name(s, sid) for sid, s in suspects.items())
        if not args:
            ctx.say(f"你要指认谁？可选：{names}")
            return False
        sid = _resolve_suspect(suspects, args[0])
        if sid is None:
            ctx.say(f"嫌疑人里没有“{args[0]}”。可选：{names}")
            return False
        reasons = reason_list(ctx.story)
        given: dict[str, str] = {}
        labels: list[str] = []
        if reasons:
            if len(args) - 1 != len(reasons):
                self._reason_prompt(ctx, engine.registry, reasons)
                return False
            for reason, text in zip(reasons, args[1:]):
                label = reason.get("label") or reason["id"]
                options = reason_options(ctx.story, ctx.state, engine.registry, reason)
                oid = _match(text, ((o["id"], _option_names(o)) for o in options))
                if oid is None:
                    choices = "、".join(_name(o, o["id"]) for o in options) or "（暂无）"
                    ctx.say(f"“{text}”不是可选的{label}。可选：{choices}")
                    return False
                given[reason["id"]] = oid
                option = next(o for o in options if o["id"] == oid)
                labels.append(f"{label}：{_name(option, oid)}")
        ctx.say(f"你指认了{_name(suspects[sid], sid)}。")
        if labels:
            ctx.say("；".join(labels) + "。")
        for outcome in acc.get("outcomes") or []:
            if (outcome.get("suspect") == sid and engine.registry.check(ctx, outcome.get("when"))
                    and _enough_reasons(outcome, given)):
                ctx.goto = outcome["goto"]
                return True
        ctx.goto = acc.get("default")
        return True

    @staticmethod
    def _reason_prompt(ctx: Context, registry: Registry, reasons: list[dict]) -> None:
        slots = " ".join(f"<{r.get('label') or r['id']}>" for r in reasons)
        ctx.say(f"请说明理由：指认 <嫌疑人> {slots}")
        for reason in reasons:
            options = reason_options(ctx.story, ctx.state, registry, reason)
            choices = "、".join(_name(o, o["id"]) for o in options) or "（暂无）"
            ctx.say(f"  {reason.get('label') or reason['id']}可选：{choices}")

    def help_lines(self) -> list[str]:
        return ["推理命令：线索（查看笔记）、调查 <线索>（深入搜证）、问 <人物> <话题或线索>（审问或出示），"
                "指认 <嫌疑人> <理由…>（给出结论；只输入“指认 名字”会提示需要的理由）。"]

    # ---- 校验 ----
    def validate(self, story: Story) -> list[Issue]:
        """检查本插件数据段的结构与引用；数据写坏时报告问题而不是抛异常。"""
        return _Validator(story).run()


# ---- 只读查询：快照与校验共用，不修改状态 ----

def _data(state: GameState) -> dict[str, Any]:
    data = state.ext.get(PLUGIN)
    return data if isinstance(data, dict) else {}


def _str_list(value: Any) -> list[str]:
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def found_clues(state: GameState) -> list[str]:
    """玩家已获得的线索 id，按获得顺序。"""
    return _str_list(_data(state).get("clues"))


def clue_data(story: Story) -> dict[str, dict]:
    """剧本的线索表；格式错误时返回空表，由校验报告。"""
    clues = story.data.get("clues")
    if not isinstance(clues, dict):
        return {}
    return {k: v for k, v in clues.items() if isinstance(v, dict)}


def accusation_data(story: Story) -> dict[str, Any]:
    """剧本的指认数据段；缺失或格式错误时为空字典。"""
    acc = story.data.get("accusation")
    return acc if isinstance(acc, dict) else {}


def suspect_data(story: Story) -> dict[str, dict]:
    """嫌疑人表：id → 人物数据。"""
    suspects = accusation_data(story).get("suspects")
    if not isinstance(suspects, dict):
        return {}
    return {k: v for k, v in suspects.items() if isinstance(v, dict)}


def act_list(story: Story) -> list[dict]:
    """剧本声明的幕，按先后顺序；格式错误的项被忽略。"""
    acts = story.data.get("acts")
    if not isinstance(acts, list):
        return []
    return [a for a in acts if isinstance(a, dict) and isinstance(a.get("id"), str)]


def reason_list(story: Story) -> list[dict]:
    """指认需要说明的理由项，按输入顺序。"""
    reasons = accusation_data(story).get("reasons")
    if not isinstance(reasons, list):
        return []
    return [r for r in reasons if isinstance(r, dict) and isinstance(r.get("id"), str)]


def _act_index(acts: list[dict], act_id: str | None) -> int:
    return next((i for i, a in enumerate(acts) if a["id"] == act_id), -1)


def current_act(story: Story, state: GameState) -> str | None:
    """当前所在的幕；尚未推进时为第一幕，剧本没有分幕时为 None。"""
    acts = act_list(story)
    act = _data(state).get("act")
    if _act_index(acts, act) >= 0:
        return act
    return acts[0]["id"] if acts else None


def act_reached(story: Story, state: GameState, act_id: str) -> bool:
    """是否已经进入 act_id 或之后的幕；未知的幕视为未到达。"""
    acts = act_list(story)
    target = _act_index(acts, act_id)
    return target >= 0 and _act_index(acts, current_act(story, state)) >= target


def examinable_clues(story: Story, state: GameState) -> list[str]:
    """已获得、可以深入调查且还没调查过的线索。"""
    clues = clue_data(story)
    examined = _str_list(_data(state).get("examined"))
    return [c for c in found_clues(state)
            if isinstance(clues.get(c, {}).get("examine"), dict) and c not in examined]


def _topics(suspect: dict) -> list[dict]:
    topics = suspect.get("topics")
    if not isinstance(topics, list):
        return []
    return [t for t in topics if isinstance(t, dict) and isinstance(t.get("id"), str)]


def _present(suspect: dict, scene: str) -> bool:
    scenes = suspect.get("scenes")
    return not isinstance(scenes, list) or not scenes or scene in scenes


def available_topics(story: Story, state: GameState, registry: Registry, suspect_id: str) -> list[dict]:
    """嫌疑人此刻可以回答的话题：需要的线索已获得，且 when 条件成立。"""
    suspect = suspect_data(story).get(suspect_id)
    if suspect is None:
        return []
    found = found_clues(state)
    ctx = Context(story, state)
    return [t for t in _topics(suspect)
            if (not t.get("clue") or t["clue"] in found) and registry.check(ctx, t.get("when"))]


def topic_label(story: Story, topic: dict) -> str:
    """话题的显示名；只写了 clue 的话题显示为“出示「线索名」”。"""
    if topic.get("name"):
        return topic["name"]
    if topic.get("clue"):
        return f"出示「{_clue_name(story, topic['clue'])}」"
    return topic["id"]


def reason_options(story: Story, state: GameState, registry: Registry, reason: dict) -> list[dict]:
    """某项理由当前可选的答案；``from: clues`` 表示从已获得的线索中选。"""
    if reason.get("from") == CLUE_SOURCE:
        clues = clue_data(story)
        return [{"id": c, "name": _clue_name(story, c)} for c in found_clues(state) if c in clues]
    options = reason.get("options")
    if not isinstance(options, list):
        return []
    ctx = Context(story, state)
    return [o for o in options if isinstance(o, dict) and isinstance(o.get("id"), str)
            and registry.check(ctx, o.get("when"))]


def build_actions(story: Story, state: GameState, registry: Registry) -> list[ActionSpec]:
    """生成推理插件的界面动作；只读状态，不推进回合、不触发剧情。

    深入调查只列出可调查且未调查过的已获得线索；审问只列出在场人物此刻可用的
    话题（值为 ``嫌疑人id/话题id``，已问过的在说明中标出，可以重读）；指认在
    ``accusation.when`` 成立后出现，某项理由暂无候选时动作不可用并说明原因。
    """
    if state.ending:
        return []
    actions = []
    clues = clue_data(story)
    examine = [DisplayItem(c, _clue_name(story, c), clues[c].get("text", ""))
               for c in examinable_clues(story, state)]
    if examine:
        actions.append(ActionSpec("mystery:examine", "深入调查", [
            ActionParameter("clue", "线索", options=examine)]))
    asked = _str_list(_data(state).get("asked"))
    topics = []
    for sid, suspect in suspect_data(story).items():
        if not _present(suspect, state.scene):
            continue
        for topic in available_topics(story, state, registry, sid):
            key = f"{sid}/{topic['id']}"
            topics.append(DisplayItem(key, f"{_name(suspect, sid)} · {topic_label(story, topic)}",
                                      "已问过" if key in asked else ""))
    if topics:
        actions.append(ActionSpec("mystery:ask", "审问", [ActionParameter("topic", "问题", options=topics)]))
    acc = accusation_data(story)
    if acc and registry.check(Context(story, state), acc.get("when")):
        params = [ActionParameter("suspect", "指认对象", options=[
            DisplayItem(sid, _name(s, sid)) for sid, s in suspect_data(story).items()])]
        for reason in reason_list(story):
            options = reason_options(story, state, registry, reason)
            params.append(ActionParameter(reason["id"], reason.get("label") or reason["id"], options=[
                DisplayItem(o["id"], _name(o, o["id"])) for o in options]))
        missing = [p.label for p in params if not p.options]
        actions.append(ActionSpec(
            "mystery:accuse", "作出指认", params, enabled=not missing,
            disabled_reason=f"还没有可选的{'、'.join(missing)}。" if missing else ""))
    return actions


def action_values(story: Story, state: GameState, registry: Registry, cmd: Command) -> dict[str, str] | None:
    """把一条文字命令换算成对应界面动作的参数；无法对应时返回 None。

    供通关脚本转换为图形操作（tools/web_vectors.py），换算规则与命令处理一致：
    ``调查 账页`` → ``{"clue": "torn_ledger"}``；``问 周文 账页`` →
    ``{"topic": "zhou/ledger"}``；``指认 周文 欠债 …`` → ``{"suspect": "zhou", "motive": …}``。
    """
    if cmd.verb == "examine":
        cid = _match("".join(cmd.args), ((c, _clue_names(story, c)) for c in found_clues(state)))
        return {"clue": cid} if cid else None
    suspects = suspect_data(story)
    if not cmd.args:
        return None
    if cmd.verb == "ask":
        sid, slash, tid = cmd.args[0].partition("/")
        if len(cmd.args) == 1 and slash and sid in suspects:
            return {"topic": cmd.args[0]}
        sid = _resolve_suspect(suspects, cmd.args[0])
        topics = available_topics(story, state, registry, sid) if sid else []
        topic = _match("".join(cmd.args[1:]), ((t, _topic_names(story, t)) for t in topics))
        return {"topic": f"{sid}/{topic['id']}"} if topic else None
    if cmd.verb == "accuse":
        sid = _resolve_suspect(suspects, cmd.args[0])
        reasons = reason_list(story)
        if sid is None or len(cmd.args) - 1 != len(reasons):
            return None
        values = {"suspect": sid}
        for reason, text in zip(reasons, cmd.args[1:]):
            options = reason_options(story, state, registry, reason)
            oid = _match(text, ((o["id"], _option_names(o)) for o in options))
            if oid is None:
                return None
            values[reason["id"]] = oid
        return values
    return None


def accusation_targets(story: Story) -> list[str]:
    """推理插件可能到达的场景（指认结局、审问与深入调查里的 goto），validator 用它计算可达性。"""
    acc = accusation_data(story)
    outcomes = acc.get("outcomes") if isinstance(acc.get("outcomes"), list) else []
    targets = [o.get("goto") for o in outcomes if isinstance(o, dict)]
    targets.append(acc.get("default"))
    targets += [arg for _, key, arg in _plugin_effects(story) if key == "goto"]
    return [t for t in targets if isinstance(t, str) and t]


# ---- 名称匹配 ----

def _norm(text: Any) -> str:
    return unicodedata.normalize("NFKC", text).strip().lower() if isinstance(text, str) else ""


def _match(text: str, candidates: Iterable[tuple[Any, list[str]]]) -> Any:
    wanted = _norm(text)
    if not wanted:
        return None
    for value, names in candidates:
        if wanted in {_norm(n) for n in names if _norm(n)}:
            return value
    return None


def _name(entry: dict, default: str) -> str:
    return entry.get("name") or default


def _option_names(option: dict) -> list[str]:
    aliases = option.get("aliases") if isinstance(option.get("aliases"), list) else []
    return [option["id"], option.get("name", "")] + aliases


def _clue_name(story: Story, cid: str) -> str:
    return clue_data(story).get(cid, {}).get("name") or cid


def _clue_names(story: Story, cid: str) -> list[str]:
    return _option_names({"id": cid, **clue_data(story).get(cid, {})})


def _topic_names(story: Story, topic: dict) -> list[str]:
    names = _option_names(topic) + [topic_label(story, topic)]
    if topic.get("clue"):
        names += _clue_names(story, topic["clue"])
    return names


def _resolve_suspect(suspects: dict[str, dict], text: str) -> str | None:
    return _match(text, ((sid, _option_names({"id": sid, **s})) for sid, s in suspects.items()))


def _enough_reasons(outcome: dict, given: dict[str, str]) -> bool:
    expected = outcome.get("reasons")
    if not isinstance(expected, dict) or not expected:
        return True
    correct = sum(1 for key, answer in expected.items()
                  if given.get(key) in (answer if isinstance(answer, list) else [answer]))
    need = outcome.get("min_correct", len(expected))
    return correct >= need


# ---- 校验 ----

def _plugin_conditions(story: Story) -> list[tuple[str, Any]]:
    """本插件新增字段里的条件：(位置, 条件)。accusation.when 与 outcomes 由 validator 遍历。"""
    found = []
    for cid, clue in clue_data(story).items():
        spec = clue.get("examine")
        if isinstance(spec, dict):
            found.append((f"clues.{cid}.examine.when", spec.get("when")))
    for sid, suspect in suspect_data(story).items():
        for topic in _topics(suspect):
            found.append((f"accusation.suspects.{sid}.topics.{topic['id']}.when", topic.get("when")))
    for reason in reason_list(story):
        options = reason.get("options")
        for i, option in enumerate(options if isinstance(options, list) else []):
            if isinstance(option, dict):
                found.append((f"accusation.reasons.{reason['id']}.options[{i}].when", option.get("when")))
    return [(path, cond) for path, cond in found if cond is not None]


def _plugin_effect_lists(story: Story) -> list[tuple[str, Any]]:
    found = []
    for cid, clue in clue_data(story).items():
        spec = clue.get("examine")
        if isinstance(spec, dict):
            found.append((f"clues.{cid}.examine.effects", spec.get("effects")))
    for sid, suspect in suspect_data(story).items():
        for topic in _topics(suspect):
            found.append((f"accusation.suspects.{sid}.topics.{topic['id']}.effects", topic.get("effects")))
    return [(path, effects) for path, effects in found if effects is not None]


def _plugin_effects(story: Story) -> list[tuple[str, str, Any]]:
    """本插件新增字段里格式正确的效果：(位置, 效果名, 参数)。"""
    result = []
    for path, effects in _plugin_effect_lists(story):
        if not isinstance(effects, list):
            continue
        for i, effect in enumerate(effects):
            if isinstance(effect, dict) and len(effect) == 1:
                ((key, arg),) = effect.items()
                result.append((f"{path}[{i}]", key, arg))
    return result


class _Validator:
    """逐项检查推理数据段，问题收集到 issues。"""

    def __init__(self, story: Story):
        self.story = story
        self.issues: list[Issue] = []
        self.clues = clue_data(story)
        self.acts = {a["id"] for a in act_list(story)}

    def error(self, path: str, message: str) -> None:
        self.issues.append(Issue("error", path, message))

    def run(self) -> list[Issue]:
        self._check_clues()
        self._check_acts()
        self._check_suspects()
        self._check_reasons()
        self._check_outcomes()
        self._check_plugin_rules()
        self._check_references()
        return self.issues

    def _check_clues(self) -> None:
        clues = self.story.data.get("clues", {})
        if not isinstance(clues, dict):
            self.error("clues", "clues 应为对象：线索id → {name, text}。")
            return
        for cid, clue in clues.items():
            if not isinstance(clue, dict):
                self.error(f"clues.{cid}", "线索应为对象，包含 name 与 text。")
            elif "examine" in clue and not isinstance(clue["examine"], dict):
                self.error(f"clues.{cid}.examine", "examine 应为对象：{when, hint, text, effects}。")

    def _check_acts(self) -> None:
        acts = self.story.data.get("acts")
        if acts is None:
            return
        if not isinstance(acts, list):
            self.error("acts", "acts 应为数组，按顺序列出各幕。")
            return
        seen: set[str] = set()
        for i, act in enumerate(acts):
            aid = act.get("id") if isinstance(act, dict) else None
            if not isinstance(aid, str) or not aid.strip():
                self.error(f"acts[{i}].id", "幕 id 应为非空字符串。")
            elif aid in seen:
                self.error(f"acts[{i}].id", f"幕 id 重复：{aid}")
            else:
                seen.add(aid)

    def _check_suspects(self) -> None:
        acc = accusation_data(self.story)
        suspects = acc.get("suspects", {}) if acc else {}
        if not isinstance(suspects, dict):
            self.error("accusation.suspects", "suspects 应为对象：嫌疑人id → 人物数据。")
            return
        for sid, suspect in suspects.items():
            path = f"accusation.suspects.{sid}"
            if "/" in sid:
                self.error(path, "嫌疑人 id 不能包含“/”（审问动作用它分隔嫌疑人和话题）。")
            if not isinstance(suspect, dict):
                self.error(path, "嫌疑人应为对象，至少包含 name。")
                continue
            scenes = suspect.get("scenes")
            if scenes is not None:
                if not isinstance(scenes, list):
                    self.error(f"{path}.scenes", "scenes 应为场景 id 数组。")
                else:
                    for scene in scenes:
                        if scene not in self.story.scenes:
                            self.error(f"{path}.scenes", f"场景不存在：{scene}")
            self._check_topics(path, suspect.get("topics"))

    def _check_topics(self, path: str, topics: Any) -> None:
        if topics is None:
            return
        if not isinstance(topics, list):
            self.error(f"{path}.topics", "topics 应为话题数组。")
            return
        seen: set[str] = set()
        for i, topic in enumerate(topics):
            tid = topic.get("id") if isinstance(topic, dict) else None
            if not isinstance(tid, str) or not tid.strip():
                self.error(f"{path}.topics[{i}].id", "话题 id 应为非空字符串。")
                continue
            if tid in seen:
                self.error(f"{path}.topics[{i}].id", f"话题 id 重复：{tid}")
            seen.add(tid)
            if not isinstance(topic.get("text"), str):
                self.error(f"{path}.topics.{tid}.text", "话题需要回答文字 text。")
            if not topic.get("name") and not topic.get("clue"):
                self.error(f"{path}.topics.{tid}", "话题需要 name，或用 clue 指定要出示的线索。")
            if topic.get("clue") is not None and topic["clue"] not in self.clues:
                self.error(f"{path}.topics.{tid}.clue", f"线索不存在：{topic['clue']}")

    def _check_reasons(self) -> None:
        reasons = accusation_data(self.story).get("reasons")
        if reasons is None:
            return
        if not isinstance(reasons, list):
            self.error("accusation.reasons", "reasons 应为数组。")
            return
        seen: set[str] = set()
        for i, reason in enumerate(reasons):
            path = f"accusation.reasons[{i}]"
            rid = reason.get("id") if isinstance(reason, dict) else None
            if not isinstance(rid, str) or not rid.strip():
                self.error(f"{path}.id", "理由 id 应为非空字符串。")
                continue
            if rid == "suspect":
                self.error(f"{path}.id", "理由 id 不能是 suspect（已用于指认对象）。")
            if rid in seen:
                self.error(f"{path}.id", f"理由 id 重复：{rid}")
            seen.add(rid)
            if reason.get("from") == CLUE_SOURCE:
                continue
            if reason.get("from") is not None:
                self.error(f"{path}.from", f"from 只能是 {CLUE_SOURCE}。")
                continue
            options = reason.get("options")
            if not isinstance(options, list) or not options:
                self.error(f"{path}.options", "理由需要非空的 options 数组，或写 \"from\": \"clues\"。")
                continue
            ids: set[str] = set()
            for j, option in enumerate(options):
                oid = option.get("id") if isinstance(option, dict) else None
                if not isinstance(oid, str) or not oid.strip():
                    self.error(f"{path}.options[{j}].id", "选项 id 应为非空字符串。")
                elif oid in ids:
                    self.error(f"{path}.options[{j}].id", f"选项 id 重复：{oid}")
                ids.add(oid)

    def _option_ids(self, reason: dict) -> set[str]:
        if reason.get("from") == CLUE_SOURCE:
            return set(self.clues)
        options = reason.get("options")
        return {o.get("id") for o in options if isinstance(o, dict)} if isinstance(options, list) else set()

    def _check_outcomes(self) -> None:
        acc = accusation_data(self.story)
        if not acc:
            return
        if acc.get("when") is not None and not isinstance(acc["when"], dict):
            self.error("accusation.when", "指认条件应为条件对象，例如 {\"visited\": \"office\"}（mystery 插件）。")
        suspects = suspect_data(self.story)
        reasons = {r["id"]: r for r in reason_list(self.story)}
        outcomes = acc.get("outcomes", [])
        if not isinstance(outcomes, list):
            self.error("accusation.outcomes", "outcomes 应为数组。")
            outcomes = []
        for i, outcome in enumerate(outcomes):
            path = f"accusation.outcomes[{i}]"
            if not isinstance(outcome, dict):
                self.error(path, "结局规则应为对象。")
                continue
            if outcome.get("suspect") not in suspects:
                self.error(path, f"嫌疑人不存在：{outcome.get('suspect')}")
            if outcome.get("goto") not in self.story.scenes:
                self.error(path, f"结局场景不存在：{outcome.get('goto')}")
            if outcome.get("when") is not None and not isinstance(outcome["when"], dict):
                self.error(f"{path}.when", "结局条件应为条件对象（mystery 插件）。")
            expected = outcome.get("reasons", {})
            if not isinstance(expected, dict):
                self.error(f"{path}.reasons", "reasons 应为对象：理由id → 正确答案。")
                continue
            for key, answer in expected.items():
                if key not in reasons:
                    self.error(f"{path}.reasons.{key}", f"理由不存在：{key}")
                    continue
                answers = answer if isinstance(answer, list) else [answer]
                valid = self._option_ids(reasons[key])
                for value in answers:
                    if value not in valid:
                        self.error(f"{path}.reasons.{key}", f"选项不存在：{value}")
            need = outcome.get("min_correct")
            if need is not None and (type(need) is not int or not 0 <= need <= len(expected)):
                self.error(f"{path}.min_correct", f"min_correct 应为 0 到 {len(expected)} 之间的整数。")
        if acc.get("default") not in self.story.scenes:
            self.error("accusation.default", f"场景不存在：{acc.get('default')}")

    def _check_plugin_rules(self) -> None:
        """插件数据里的条件与效果：名称已注册、参数指向存在的线索、幕、场景和物品。"""
        registry = _registry_for(self.story)
        for path, cond in _plugin_conditions(self.story):
            if not isinstance(cond, dict):
                self.error(path, "条件应为对象，例如 {\"has_clue\": \"线索id\"}。")
                continue
            for sub_path, key, _ in expand_condition(path, cond):
                if key not in registry.conditions:
                    self.error(sub_path, f"未知条件：{key}")
        for path, effects in _plugin_effect_lists(self.story):
            if not isinstance(effects, list):
                self.error(path, "effects 应为效果数组。")
                continue
            for i, effect in enumerate(effects):
                if not isinstance(effect, dict) or len(effect) != 1:
                    self.error(f"{path}[{i}]", "每个效果只能有一个键，例如 {\"add_clue\": \"线索id\"}。")
                elif next(iter(effect)) not in registry.effects:
                    self.error(f"{path}[{i}]", f"未知效果：{next(iter(effect))}")

    def _check_references(self) -> None:
        conditions = list(iter_conditions(self.story))
        acc = accusation_data(self.story)
        if isinstance(acc.get("when"), dict):
            conditions += list(expand_condition("accusation.when", acc["when"]))
        for i, outcome in enumerate(acc.get("outcomes") if isinstance(acc.get("outcomes"), list) else []):
            if isinstance(outcome, dict) and isinstance(outcome.get("when"), dict):
                conditions += list(expand_condition(f"accusation.outcomes[{i}].when", outcome["when"]))
        for path, cond in _plugin_conditions(self.story):
            if isinstance(cond, dict):
                conditions += list(expand_condition(path, cond))
        for path, key, arg in conditions:
            self._check_arg(path, key, arg)
        for path, key, arg in list(iter_effects(self.story)) + _plugin_effects(self.story):
            self._check_arg(path, key, arg)

    def _check_arg(self, path: str, key: str, arg: Any) -> None:
        if key in ("has_clue", "add_clue"):
            if arg not in self.clues:
                self.error(path, f"线索不存在：{arg}")
        elif key in ("act", "start_act"):
            if arg not in self.acts:
                self.error(path, f"幕不存在：{arg}")
        elif key == "clues_found":
            if type(arg) is not int or arg < 0:
                self.error(path, "clues_found 的参数应为非负整数。")
        elif path.startswith(("clues.", "accusation.suspects.", "accusation.reasons.")):
            # 核心字段由 validator 检查；这里只补插件数据段里的场景和物品引用。
            if key in ("goto", "visited") and arg not in self.story.scenes:
                self.error(path, f"场景不存在：{arg}")
            elif key in ("give_item", "take_item", "has_item") and arg not in self.story.items:
                self.error(path, f"物品不存在：{arg}")


def _registry_for(story: Story) -> Registry:
    """核心规则加上剧本启用的全部插件，用于检查插件数据里的条件与效果名。"""
    from . import create_mechanic

    registry = default_registry()
    for name in dict.fromkeys(story.mechanics):
        try:
            create_mechanic(name).register(registry)
        except (ValueError, RuleError):
            continue
    return registry
