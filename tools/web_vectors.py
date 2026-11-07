"""将现有通关脚本转换为浏览器动作，并与原生引擎结果逐步对照。"""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from taleloom.engine import Engine
from taleloom.loader import load_story
from taleloom.parser import parse
from taleloom.replay import load_walkthrough
from taleloom.ui_contract import ActionRequest
from taleloom.mechanics.puzzle import resolve_item
from web.runtime.factory import create_session


def build_vectors() -> list:
    """返回真实脚本的结构化动作、逐步状态与预期结局。"""
    vectors = []
    for story_file in sorted((ROOT / 'stories').glob('*/story.json')):
        story = load_story(story_file)
        for file in sorted((story_file.parent / 'walkthroughs').glob('*.txt')):
            walkthrough = load_walkthrough(file)
            native = Engine(story)
            output = native.start()
            session = create_session(story)
            session.start()
            actions = []
            for text in walkthrough.commands:
                cmd = parse(text, output.choices, native.verb_aliases())
                if cmd.verb in ('clues', 'look', 'inventory', 'help', 'noop'):
                    # 网页已在快照展示这些纯阅读信息，不记录阅读命令。
                    continue
                values = {}
                if cmd.verb == 'choose':
                    choices = native.available_choices()
                    choice = choices[int(cmd.target) - 1] if cmd.target.isdigit() else next(c for c in choices if c.id == cmd.target)
                    action_id = f'choice:{choice.id}'
                    cmd.args = [choice.id]
                elif cmd.verb in ('use', 'combine'):
                    ids = [resolve_item(story, native.state, arg) for arg in cmd.args]
                    keys = ['item'] if cmd.verb == 'use' else ['first', 'second']
                    values = dict(zip(keys, ids))
                    cmd.args = ids
                    action_id = f'puzzle:{cmd.verb}'
                elif cmd.verb == 'accuse':
                    suspects = story.data['accusation']['suspects']
                    target = next(sid for sid, suspect in suspects.items()
                                  if cmd.target in [sid, suspect.get('name')] + suspect.get('aliases', []))
                    values = {'suspect': target}
                    cmd.args = [target]
                    action_id = 'mystery:accuse'
                else:
                    raise AssertionError(f'新增动词需要网页操作：{cmd.verb}')
                cmd.raw = ' '.join([cmd.verb] + cmd.args)
                output = native.handle(cmd)
                result = session.dispatch(ActionRequest(action_id, session.snapshot().revision, values))
                assert result.ok, (file, text, result.messages)
                assert session.export_save()['state'] == native.state.to_dict(), (file, text)
                actions.append({'action_id': action_id, 'values': values})
            assert session.snapshot().ending_id == walkthrough.expect, file
            vectors.append({'story_id': story.id, 'name': walkthrough.name,
                            'actions': actions, 'ending': walkthrough.expect,
                            'save': session.export_save()})
    return vectors


if __name__ == '__main__':
    print(json.dumps(build_vectors(), ensure_ascii=False))
