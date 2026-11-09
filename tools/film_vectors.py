"""影像版浏览器测试用的数据：通关脚本的结构化动作，以及沿途每个场景的标准存档。负责人：ZC。

``python3 -B tools/film_vectors.py fog_harbor_ledger`` 输出 JSON::

    {"vectors": [...],                      # 同 tools/web_vectors.py 的结构
     "scenes": {"<通关脚本>": {"<场景id>": <首次进入该场景后的标准存档>}}}

存档带着会话的存档点记录（ext.session），浏览器读入后可以继续回到存档点。
只读剧本与通关脚本，不写任何文件。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from taleloom.loader import load_story  # noqa: E402
from taleloom.session_factory import create_session  # noqa: E402
from taleloom.ui_contract import ActionRequest  # noqa: E402
from tools.web_vectors import build_vectors  # noqa: E402


def build(story_id: str) -> dict:
    """回放影像版剧本的全部通关脚本，记下每个场景首次进入时的存档。"""
    story_file = ROOT / 'stories' / 'film' / story_id / 'story.json'
    story = load_story(story_file.parent)
    vectors = build_vectors([story_file])
    scenes = {}
    for vector in vectors:
        session = create_session(story, seed=0)
        session.start()
        session.restore(vector['initial_save'])
        view = session.snapshot()
        saves = {view.scene_id: session.export_save()}
        for step in vector['actions']:
            view = session.dispatch(ActionRequest(step['action_id'], view.revision, step['values'])).view
            if view.scene_id not in saves and not view.ended:
                saves[view.scene_id] = session.export_save()
        scenes[vector['name']] = saves
    return {'vectors': vectors, 'scenes': scenes}


if __name__ == '__main__':
    print(json.dumps(build(sys.argv[1] if len(sys.argv) > 1 else 'fog_harbor_ledger'), ensure_ascii=False))
