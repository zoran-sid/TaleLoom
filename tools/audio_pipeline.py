"""用 fal 生成并加工影像版声音素材；开发工具，不参与网页或桌面运行时。

    python tools/audio_pipeline.py --list
    python tools/audio_pipeline.py                 # 生成 spec 中缺失的素材
    python tools/audio_pipeline.py --only harbor_arrival --force
    python tools/audio_pipeline.py --dry-run

凭据只从环境变量 ``FAL_KEY`` 或仓库根目录的 ``.fal-key`` 读取，不写入日志。
生成原始文件放在 ``web/cinematic/audio/raw/``（已忽略），成品 MP3、响度、SHA-256
与请求 ID 写入 ``web/cinematic/audio/manifest.json``，供声音设计文档引用。
素材参数在 ``tools/audio_spec.json``，模型、授权与费用记录见 ``docs/audio-direction.md``。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / 'tools' / 'audio_spec.json'
AUDIO_DIR = ROOT / 'web' / 'cinematic' / 'audio'
RAW_DIR = AUDIO_DIR / 'raw'
MANIFEST = AUDIO_DIR / 'manifest.json'
QUEUE = 'https://queue.fal.run/'
POLL_SECONDS = 2
POLL_LIMIT = 900


def load_key() -> str:
    """读取 fal 凭据；只返回，不打印。"""
    key = (os.environ.get('FAL_KEY') or os.environ.get('FAL_API_KEY') or '').strip()
    if key:
        return key
    for path in (ROOT / '.fal-key', Path.home() / '.fal-key'):
        if path.is_file():
            value = path.read_text(encoding='utf-8').strip()
            if value:
                return value
    raise SystemExit('缺少 fal 凭据：请设置 FAL_KEY，或把单行 key 写入仓库根目录的 .fal-key。')


def request_json(url: str, key: str, payload: dict | None = None, timeout: int = 120) -> dict:
    """发一次 JSON 请求；错误信息保留状态码与响应正文，不包含请求头。"""
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, method='POST' if payload is not None else 'GET')
    request.add_header('Authorization', f'Key {key}')
    request.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')[:800]
        raise SystemExit(f'fal 请求失败：HTTP {exc.code} {body}') from None
    except urllib.error.URLError as exc:
        raise SystemExit(f'无法连接 fal：{exc.reason}') from None


def submit(endpoint: str, payload: dict, key: str) -> tuple[str, dict]:
    """提交到 fal 队列，返回请求 ID 与可轮询的状态地址。"""
    body = request_json(f'{QUEUE}{endpoint}', key, payload)
    request_id = body.get('request_id')
    if not request_id:
        raise SystemExit(f'fal 没有返回 request_id：{body}')
    status_url = body.get('status_url') or f'{QUEUE}{endpoint}/requests/{request_id}/status'
    response_url = body.get('response_url') or f'{QUEUE}{endpoint}/requests/{request_id}'
    return request_id, {'status': status_url, 'response': response_url}


def wait_for_result(endpoint: str, request_id: str, urls: dict, key: str) -> dict:
    """轮询直到完成；超时或失败给出可执行的提示。"""
    deadline = time.monotonic() + POLL_LIMIT
    while time.monotonic() < deadline:
        status = request_json(urls['status'], key, timeout=60)
        state = status.get('status')
        if state == 'COMPLETED':
            return request_json(urls['response'], key, timeout=300)
        if state in {'FAILED', 'ERROR', 'CANCELLED'}:
            raise SystemExit(f'{endpoint} 生成失败：{status}')
        time.sleep(POLL_SECONDS)
    raise SystemExit(f'{endpoint} 超过 {POLL_LIMIT} 秒仍未完成，request_id={request_id}')


def audio_url(result: dict) -> str:
    """兼容模型把音频放在 audio、audios 或字符串里的不同返回形状。"""
    audio = result.get('audio')
    if isinstance(audio, dict) and audio.get('url'):
        return audio['url']
    if isinstance(audio, str) and audio.startswith('http'):
        return audio
    for item in result.get('audios') or []:
        if isinstance(item, dict) and item.get('url'):
            return item['url']
    raise SystemExit(f'返回结果里没有音频地址：{result}')


def download(url: str, destination: Path) -> Path:
    """下载原始音频；扩展名按 URL 或内容类型决定。"""
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix not in {'.wav', '.mp3', '.flac', '.aac'}:
        suffix = '.wav'
    destination = destination.with_suffix(suffix)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            destination.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f'下载素材失败：HTTP {exc.code}') from None
    return destination


def looped_wav(source: Path, destination: Path, loop: int) -> None:
    """把首尾各 loop 秒交叉，得到可无缝循环的中间 WAV。"""
    graph = ("[0:a]asplit=2[main][head];"
             f"[main]atrim=start={loop},asetpts=PTS-STARTPTS[m];"
             f"[head]atrim=end={loop},asetpts=PTS-STARTPTS[h];"
             f"[m][h]acrossfade=d={loop}:c1=tri:c2=tri[out]")
    command = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(source),
               '-filter_complex', graph, '-map', '[out]', '-ar', '44100', '-ac', '2',
               '-c:a', 'pcm_s16le', str(destination)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f'ffmpeg 交叉淡入失败：{result.stderr.strip()[:800]}')


def process(source: Path, destination: Path, post: dict, workdir: Path) -> None:
    """先循环化，再按实测响度补增益，最后编码 MP3；峰值不越过上限。"""
    looped = workdir / (destination.stem + '.loop.wav')
    looped_wav(source, looped, post['loop'])
    before = probe(looped)
    gain = post['lufs'] - before['lufs']
    if before['peak'] + gain > post['tp']:
        gain = post['tp'] - before['peak']
    command = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(looped),
               '-af', f'volume={gain:.2f}dB', '-ar', '44100', '-ac', '2',
               '-c:a', 'libmp3lame', '-b:a', '128k', str(destination)]
    result = subprocess.run(command, capture_output=True, text=True)
    looped.unlink(missing_ok=True)
    if result.returncode:
        raise SystemExit(f'ffmpeg 编码失败：{result.stderr.strip()[:800]}')


def probe(path: Path) -> dict:
    """读取成品时长与综合响度，作为试听前的数值记录。"""
    info = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                           '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    duration = round(float(json.loads(info.stdout)['format']['duration']), 2)
    scan = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
                           '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-'],
                          capture_output=True, text=True)
    loudness = re.findall(r'I:\s+(-?\d+(?:\.\d+)?) LUFS', scan.stderr)
    peak = re.findall(r'Peak:\s+(-?\d+(?:\.\d+)?) dBFS', scan.stderr)
    return {'duration': duration,
            'lufs': float(loudness[-1]) if loudness else None,
            'peak': float(peak[-1]) if peak else None}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load_manifest() -> list[dict]:
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text(encoding='utf-8')).get('assets', [])
    return []


def save_manifest(records: list[dict], order: list[str]) -> None:
    index = {record['id']: record for record in records}
    ordered = [index[name] for name in order if name in index]
    MANIFEST.write_text(json.dumps({'assets': ordered}, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='生成《未结的账》序章与第一章的声音素材')
    parser.add_argument('--spec', type=Path, default=SPEC_PATH)
    parser.add_argument('--only', action='append', default=[], metavar='ID')
    parser.add_argument('--force', action='store_true', help='覆盖已存在的 MP3')
    parser.add_argument('--dry-run', action='store_true', help='只显示将要提交的请求')
    parser.add_argument('--reuse-raw', action='store_true', help='复用 raw/ 中的原始文件，不再调用 fal')
    parser.add_argument('--list', action='store_true', help='列出 spec 中的素材')
    args = parser.parse_args(argv)

    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    assets = spec['assets']
    if args.list:
        for asset in assets:
            print(f"{asset['id']:16} {asset['layer']:9} {asset['endpoint']}")
        return 0

    selected = [a for a in assets if not args.only or a['id'] in args.only]
    if not selected:
        raise SystemExit('没有匹配的素材；用 --list 查看 ID。')
    missing = set(args.only) - {a['id'] for a in assets}
    if missing:
        raise SystemExit(f'未知素材：{", ".join(sorted(missing))}')
    for command in ('ffmpeg', 'ffprobe'):
        if shutil.which(command) is None:
            raise SystemExit(f'需要 {command}，请先安装 FFmpeg。')

    key = '' if args.dry_run else load_key()
    records = load_manifest()
    saved: list[str] = []
    for asset in selected:
        identifier = asset['id']
        destination = AUDIO_DIR / f'{identifier}.mp3'
        if destination.exists() and not args.force:
            print(f'跳过 {identifier}：{destination.name} 已存在（--force 可重做）')
            continue
        payload = asset['input']
        print(f"生成 {identifier} ← {asset['endpoint']}（{payload.get('seconds_total') or payload.get('duration')} 秒）")
        if args.dry_run:
            continue
        previous = next((r for r in records if r['id'] == identifier), {})
        if args.reuse_raw:
            candidates = sorted(RAW_DIR.glob(f'{identifier}.*'))
            if not candidates:
                raise SystemExit(f'缺少 {identifier} 的原始文件；先去 --force 生成一次。')
            source, request_id = candidates[0], previous.get('request_id', '')
        else:
            request_id, urls = submit(asset['endpoint'], payload, key)
            result = wait_for_result(asset['endpoint'], request_id, urls, key)
            source = download(audio_url(result), RAW_DIR / identifier)
        process(source, destination, asset['post'], RAW_DIR)
        stats = probe(destination)
        record = {
            'id': identifier,
            'layer': asset['layer'],
            'endpoint': asset['endpoint'],
            'request_id': request_id,
            'seed': payload.get('seed'),
            'duration': stats['duration'],
            'lufs': stats['lufs'],
            'peak': stats['peak'],
            'sha256': sha256(destination),
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        records = [r for r in records if r['id'] != identifier] + [record]
        save_manifest(records, [a['id'] for a in assets])
        saved.append(identifier)
        print(f"  完成 {destination.name}：{stats['duration']} 秒，{stats['lufs']} LUFS，"
              f"request_id={request_id}")

    if not args.dry_run and not saved:
        print('没有生成新素材。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
