"""把配音清单渲染成前端数据；生成文件不手改。

    python tools/render_voice.py

读取 ``tools/voice_spec.json``（人物、原句、声线与素材 id）和
``web/cinematic/audio/manifest.json``（请求 ID、响度、校验和），输出：

- ``web/cinematic/voice-lines.generated.js``：场景 → 原句 → 素材 id
- ``web/cinematic/voice-assets.generated.js``：素材 id → 文件 URL

缺任何一条录音时失败并列出缺少的 id，避免页面引用不存在的文件。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'tools' / 'voice_spec.json'
MANIFEST = ROOT / 'web' / 'cinematic' / 'audio' / 'manifest.json'
LINES_OUT = ROOT / 'web' / 'cinematic' / 'voice-lines.generated.js'
ASSETS_OUT = ROOT / 'web' / 'cinematic' / 'voice-assets.generated.js'


def main() -> int:
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    ready = {record['id'] for record in manifest.get('voices', [])}
    missing = [line['id'] for line in spec['lines'] if line['id'] not in ready]
    if missing:
        raise SystemExit('缺少配音录音：' + '、'.join(missing) + '；先运行 python tools/audio_pipeline.py --voice')

    scenes = []
    for scene, lines in spec['scenes'].items():
        rows = ',\n'.join(
            '    { speaker: %s, text: %s, asset: %s }' % (
                json.dumps(line['speaker'], ensure_ascii=False),
                json.dumps(line['text'], ensure_ascii=False),
                json.dumps(line['asset'], ensure_ascii=False))
            for line in lines)
        scenes.append('  %s: [\n%s,\n  ]' % (json.dumps(scene, ensure_ascii=False), rows))
    LINES_OUT.write_text(
        '/** 生成文件：python tools/render_voice.py；数据来自 tools/voice_spec.json。 */\n'
        'export const VOICE_LINES = {\n' + ',\n'.join(scenes) + ',\n};\n', encoding='utf-8')

    assets = []
    for line in spec['lines']:
        assets.append('  %s: { url: new URL(%s, import.meta.url).href, layer: \'voice\', gain: 1 }' % (
            json.dumps(line['id'], ensure_ascii=False),
            json.dumps('./audio/' + line['file'], ensure_ascii=False)))
    ASSETS_OUT.write_text(
        '/** 生成文件：python tools/render_voice.py；数据来自 tools/voice_spec.json。 */\n'
        'export const VOICE_ASSETS = Object.freeze({\n' + ',\n'.join(assets) + ',\n});\n',
        encoding='utf-8')
    print(f'渲染 {len(spec["lines"])} 条配音、{sum(len(v) for v in spec["scenes"].values())} 处场景引用')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
