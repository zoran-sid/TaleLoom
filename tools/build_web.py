"""准备可公开发布的网页资源；只打包明确列出的 Python 文件和 story.json。"""

import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / '.web-public'
CORE = [
    '__init__.py', 'engine.py', 'model.py', 'state.py', 'rules.py', 'loader.py',
    'save.py', 'walk.py', 'ui_contract.py', 'mechanics/__init__.py',
    'mechanics/base.py', 'mechanics/mystery.py', 'mechanics/puzzle.py',
]
RUNTIME = ['__init__.py', 'legacy_session.py', 'factory.py', 'bridge.py']
PYODIDE_FILES = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm',
                 'python_stdlib.zip', 'pyodide-lock.json']


def game_files(root: Path) -> list[Path]:
    """返回游戏包白名单，不含测试、攻略、存档、桌面或部署凭据。"""
    return ([root / 'taleloom' / name for name in CORE]
            + [root / 'web' / '__init__.py']
            + [root / 'web' / 'runtime' / name for name in RUNTIME]
            + sorted((root / 'stories').glob('*/story.json')))


def make_archive(root: Path, catalog: list) -> bytes:
    """生成内容确定的 ZIP，使用稳定时间戳便于复现和内容寻址。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in game_files(root):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
        archive.writestr(zipfile.ZipInfo('catalog.json'), json.dumps(catalog, ensure_ascii=False))
    return buffer.getvalue()


def main():
    """复制锁定的本地 Pyodide，产出目录与文件大小均可检查。"""
    package = ROOT / 'node_modules' / 'pyodide'
    version = json.loads((package / 'package.json').read_text())['version']
    catalog = []
    for path in sorted((ROOT / 'stories').glob('*/story.json')):
        story = json.loads(path.read_text(encoding='utf-8'))
        if path.parent.name != story['id']:
            raise ValueError(f'网页剧本目录与 ID 必须一致：{path}')
        catalog.append({'id': story['id'], 'title': story['title'],
                        'genre': story.get('meta', {}).get('genre', '文字冒险')})
    archive = make_archive(ROOT, catalog)
    name = f'game-{hashlib.sha256(archive).hexdigest()[:16]}.zip'
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    runtime_dir = PUBLIC / 'pyodide' / version
    runtime_dir.mkdir(parents=True)
    for filename in PYODIDE_FILES:
        shutil.copyfile(package / filename, runtime_dir / filename)
    (PUBLIC / name).write_bytes(archive)
    (PUBLIC / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
    (PUBLIC / 'runtime.json').write_text(json.dumps({
        'package': '/' + name, 'pyodide': f'/pyodide/{version}/',
    }), encoding='utf-8')
    for filename in ('worker.js', '_headers', 'THIRD_PARTY_NOTICES.txt'):
        shutil.copyfile(ROOT / 'web' / 'runtime' / filename, PUBLIC / filename)
    for path in PUBLIC.rglob('*'):
        if path.is_file() and path.stat().st_size > 25 * 1024 * 1024:
            raise ValueError(f'文件超过 Static Assets 25 MiB 上限：{path.name}')
    print(f'网页资源准备完成：{len(catalog)} 个剧本，Pyodide {version}，游戏包 {len(archive)} 字节')


if __name__ == '__main__':
    main()
