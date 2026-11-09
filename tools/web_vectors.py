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
from taleloom.mechanics import mystery
from taleloom.mechanics.puzzle import resolve_item, resolve_target
from taleloom.session_factory import create_session


def build_vectors(story_files=None) -> list:
    """返回真实脚本的结构化动作、逐步状态与预期结局。"""
    vectors = []
    if story_files is None:
        story_files = (ROOT / 'stories').glob('*/story.json')
    for story_file in sorted(story_files):
        story = load_story(story_file)
        for file in sorted((story_file.parent / 'walkthroughs').glob('*.txt')):
            walkthrough = load_walkthrough(file)
            native = Engine(story)
            native.state.random_seed = walkthrough.seed
            output = native.start()
            session = create_session(story, seed=walkthrough.seed)
            session.start()
            initial_save = session.export_save()
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
                elif cmd.verb == 'use_on':
                    values = {'item': resolve_item(story, native.state, cmd.args[0]),
                              'target': resolve_target(story, cmd.args[1], native.state.scene)}
                    assert all(values.values()), (file, text, '未知物品或目标')
                    cmd.args = list(values.values())
                    action_id = 'puzzle:use_on'
                elif cmd.verb in ('use', 'combine'):
                    ids = [resolve_item(story, native.state, arg) for arg in cmd.args]
                    keys = ['item'] if cmd.verb == 'use' else ['first', 'second']
                    values = dict(zip(keys, ids))
                    cmd.args = ids
                    action_id = f'puzzle:{cmd.verb}'
                elif cmd.verb in ('examine', 'ask', 'accuse', 'inspect', 'solve', 'hint'):
                    values = mystery.action_values(story, native.state, native.registry, cmd)
                    assert values is not None, (file, text, '通关脚本中的推理命令无法对应到界面动作')
                    # 动作参数顺序即命令参数顺序：suspect／unit 在前，各理由、各栏位按剧本声明的顺序。
                    cmd.args = list(values.values())
                    action_id = f'mystery:{cmd.verb}'
                else:
                    raise AssertionError(f'新增动词需要网页操作：{cmd.verb}')
                cmd.raw = ' '.join([cmd.verb] + cmd.args)
                output = native.handle(cmd)
                result = session.dispatch(ActionRequest(action_id, session.snapshot().revision, values))
                assert result.ok, (file, text, result.messages)
                actual_state = session.export_save()['state']
                # 会话独有的回退元数据不属于 CLI 剧情状态；其余字段逐项相等。
                actual_state['ext'].pop('session', None)
                assert actual_state == native.state.to_dict(), (file, text)
                actions.append({'action_id': action_id, 'values': values})
            assert session.snapshot().ending_id == walkthrough.expect, file
            vectors.append({'story_id': story.id, 'name': walkthrough.name,
                            'actions': actions, 'ending': walkthrough.expect, 'initial_save': initial_save,
                            'save': session.export_save()})
    return vectors


if __name__ == '__main__':
    print(json.dumps(build_vectors(), ensure_ascii=False))
