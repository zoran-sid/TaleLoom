"""通关脚本回放：把一串玩家输入喂给引擎，检查是否到达预期结局。负责人：LQ。

通关脚本是纯文本，每行一条玩家输入；以 # 开头的行是注释，
``# expect: <结局id>`` 声明预期结局。示例见 stories/*/walkthroughs/。
集成测试会自动回放所有剧本的全部通关脚本。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .engine import Engine
from .model import Story
from .parser import parse


@dataclass
class Walkthrough:
    name: str
    commands: list[str]
    expect: str | None = None


@dataclass
class ReplayResult:
    walkthrough: str
    ok: bool
    ending: str | None
    message: str
    transcript: list[str] = field(default_factory=list)


def load_walkthrough(path: str | Path) -> Walkthrough:
    path = Path(path)
    commands, expect = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            body = stripped.lstrip("#").strip()
            if body.lower().startswith("expect:"):
                expect = body.split(":", 1)[1].strip()
            continue
        if stripped:
            commands.append(stripped)
    return Walkthrough(path.stem, commands, expect)


def run_commands(story: Story, commands: list[str]) -> tuple[Engine, list[str]]:
    engine = Engine(story)
    out = engine.start()
    transcript = list(out.lines)
    for text in commands:
        cmd = parse(text, out.choices, engine.verb_aliases())
        out = engine.handle(cmd)
        transcript.append(f"> {text}")
        transcript.extend(out.lines)
    return engine, transcript


def check(story: Story, wt: Walkthrough) -> ReplayResult:
    engine, transcript = run_commands(story, wt.commands)
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
