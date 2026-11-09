"""通关脚本回放：把一串玩家输入喂给引擎，检查是否到达预期结局。负责人：LQ。

通关脚本是纯文本，每行一条玩家输入；以 # 开头的行是注释，
``# expect: <结局id>`` 声明预期结局。示例见 stories/*/walkthroughs/。
集成测试会自动回放所有剧本的全部通关脚本。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import random

from .engine import Engine
from .model import Story
from .parser import parse


@dataclass
class Walkthrough:
    name: str
    commands: list[str]
    expect: str | None = None
    seed: int = 0


@dataclass
class ReplayResult:
    walkthrough: str
    ok: bool
    ending: str | None
    message: str
    transcript: list[str] = field(default_factory=list)


def load_walkthrough(path: str | Path) -> Walkthrough:
    path = Path(path)
    commands, expect, seed = [], None, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            body = stripped.lstrip("#").strip()
            if body.lower().startswith("expect:"):
                expect = body.split(":", 1)[1].strip()
            if body.lower().startswith('seed:'):
                try:
                    seed = int(body.split(':', 1)[1].strip())
                except ValueError as exc:
                    raise ValueError(f'{path}: seed 应为整数') from exc
            continue
        if stripped:
            commands.append(stripped)
    return Walkthrough(path.stem, commands, expect, seed)


def run_commands(story: Story, commands: list[str], *, seed: int = 0) -> tuple[Engine, list[str]]:
    """固定种子驱动 CLI；同一条脚本可在 CPython 与浏览器中重放。"""
    if type(seed) is not int:
        raise ValueError('seed 应为整数')
    engine = Engine(story)
    engine.state.random_seed = seed
    out = engine.start()
    transcript = list(out.lines)
    for text in commands:
        cmd = parse(text, out.choices, engine.verb_aliases())
        out = engine.handle(cmd)
        transcript.append(f"> {text}")
        transcript.extend(out.lines)
    return engine, transcript


def check(story: Story, wt: Walkthrough) -> ReplayResult:
    engine, transcript = run_commands(story, wt.commands, seed=wt.seed)
    ending = engine.state.ending
    if wt.expect is None:
        return ReplayResult(wt.name, True, ending, "未声明预期结局，仅检查可运行", transcript)
    ok = ending == wt.expect
    msg = "到达预期结局" if ok else f"预期结局 {wt.expect}，实际为 {ending or '未结束'}"
    return ReplayResult(wt.name, ok, ending, msg, transcript)


def walkthroughs_for(story_dir: str | Path) -> list[Path]:
    return sorted(Path(story_dir).glob("walkthroughs/*.txt"))


def ending_coverage(story: Story, results: list[ReplayResult]) -> tuple[set[str], set[str]]:
    """返回 (全部结局id, 被通关脚本覆盖的结局id)。"""
    all_endings = {s.ending.get("id", sid) for sid, s in story.endings().items()}
    covered = {r.ending for r in results if r.ok and r.ending}
    return all_endings, covered


class ExplorationError(AssertionError):
    """随机探索发现异常，错误中包含可复现的种子和操作路线。"""


@dataclass
class ExplorationResult:
    """一次探索的实际步数、种子、结局及结构化操作。"""
    seed: int
    steps: int
    ending: str | None
    route: list[dict]
    state: dict


def explore(story: Story, *, seed: int = 0, runs: int = 20, steps: int = 100) -> list[ExplorationResult]:
    """独立探索随机数驱动当前合法动作，每步检查状态与纯读取；失败不吞异常。"""
    from .session_factory import create_session
    from .save import decode_save
    from .ui_contract import ActionRequest
    if type(seed) is not int or type(runs) is not int or type(steps) is not int or runs < 1 or steps < 1:
        raise ValueError('seed 应为整数，runs/steps 应为正整数')
    results = []
    for index in range(runs):
        game_seed = seed + index
        rng = random.Random(game_seed)
        session = create_session(story, seed=game_seed)
        route = []
        try:
            session.start()
            for _ in range(steps):
                view = session.snapshot()
                before = session.export_save()
                decode_save(before, story)
                assert session.snapshot().to_dict() == view.to_dict(), '读取改变快照'
                assert session.export_save() == before, '读取改变游戏状态'
                if view.ended:
                    break
                actions = [a for a in view.choices + view.actions if a.enabled
                           and all(p.options or p.kind == 'text' or not p.required for p in a.parameters)]
                if not actions:
                    raise AssertionError('非结局场景没有可用动作')
                action = rng.choice(actions)
                values = {p.key: rng.choice(p.options).id if p.options else '探索'
                          for p in action.parameters if p.required or p.options}
                if action.id == 'puzzle:combine' and values.get('first') == values.get('second'):
                    choices = [x.id for x in action.parameters[1].options if x.id != values['first']]
                    if choices:
                        values['second'] = rng.choice(choices)
                route.append({'action_id': action.id, 'values': values})
                result = session.dispatch(ActionRequest(action.id, view.revision, values))
                assert result.ok, (result.error_code, result.messages)
                decode_save(session.export_save(), story)
            state = session.export_save()['state']
            results.append(ExplorationResult(game_seed, len(route), state['ending'], route, state))
        except Exception as exc:
            raise ExplorationError(f'{story.id}: seed={game_seed}, step={len(route)}, route={json.dumps(route, ensure_ascii=False)}: {exc}') from exc
    return results


if __name__ == '__main__':
    import argparse
    from .loader import load_story
    parser = argparse.ArgumentParser(description='固定种子随机探索两个剧本；异常时退出失败')
    parser.add_argument('--stories', type=Path, default=Path('stories'))
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--runs', type=int, default=20)
    parser.add_argument('--steps', type=int, default=100)
    args = parser.parse_args()
    for path in sorted(args.stories.glob('*/story.json')):
        results = explore(load_story(path), seed=args.seed, runs=args.runs, steps=args.steps)
        print(f'{path.parent.name}: {len(results)} 次，{sum(r.steps for r in results)} 步，无异常；seed={args.seed}')
