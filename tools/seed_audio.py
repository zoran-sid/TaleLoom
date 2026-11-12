"""Generate ledger voice and ambience with Seed Audio 1.0 (Volcengine or fal).

The bearer token is read from a local 0600 file, never from command arguments or
repository files. Run --list before --generate to inspect the planned calls.

``--provider fal`` calls the same model hosted on fal (``bytedance/seed-audio-1.0``).
fal returns audio only, so page timings come from a local Whisper transcription
aligned against the script text; clips whose transcript match is too low are kept
out of the web bundle, exactly like mismatched Volcengine clips.
"""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web/cinematic/audio/seed"
MANIFEST = OUT / "manifest.json"
RUNTIME = ROOT / "web/cinematic/seed-runtime.json"
API = "https://openspeech.bytedance.com/api/v3/tts/create"
MODEL = "seed-audio-1.0"
RATE_CNY_PER_MINUTE = 1.0
MIN_PAGE_SECONDS = 1.2
FAL_API = "https://fal.run/bytedance/seed-audio-1.0"
FAL_USD_PER_MINUTE = 0.1875
USD_TO_CNY = 7.2
# Whisper 转写会把人名、数字写成同音字，匹配门槛比模型自带字幕低；仍能拦住漏读整句。
WHISPER_MATCH = 0.80
# 阿芸的女声参考音（fal 托管）；只有她有台词的场景才带上。
AYUN_REFERENCE = "https://v3b.fal.media/files/b/0ab1ef30/SopQ9Xbe8FCMIV4LgtLD6_ayun-female.mp3"
AYUN_NOTE = "阿芸的台词使用 @Audio1 的年轻女声音色；其他人物都不要使用 @Audio1 的音色。"

AMBIENCE = {
    "harbor": "1931年中国雾港夜间码头。近处海水轻拍木桩、绳索轻响，远处偶有雾笛，潮湿海风。约40秒纯环境声，空间真实，动态平稳，可循环。无人声，无音乐，无突兀事件。",
    "lobby": "1931年中国海鸥旅馆大堂。旧式座钟轻轻走动，炉火微响，窗外细雨，木地板偶尔轻响。约40秒纯环境声，温暖但隐隐不安，可循环。无人声，无音乐。",
    "dinner": "1931年中国港口旅馆的饭厅夜晚。炉火、瓷碗与汤匙轻碰、远处雨声、老木屋细微作响。约40秒纯环境声，克制真实，可循环。无人声，无音乐。",
    "office": "1931年中国港口旅馆账房雨夜。雨点敲窗、灯芯轻响、旧木板偶尔吱响，纸张轻翻。约40秒纯环境声，近处细节清楚，可循环。无人声，无音乐。",
    "kitchen": "1931年中国旅馆后厨深夜。灶火余烬、锅盖轻触、滴水和远处风雨，室内空旷。约40秒纯环境声，可循环。无人声，无音乐。",
    "dutyroom": "1931年中国雾港值房深夜。挂钟走动、旧电话轻微电流、海风穿过窗缝、远处水声。约40秒纯环境声，可循环。无人声，无音乐。",
    "ledger": "1931年中国旅馆账桌旁。纸页、铅笔划过账簿、灯芯轻响，窗外细雨很远。约40秒纯环境声，安静适合阅读，可循环。无人声，无音乐。",
    "rain": "1931年中国港口旅馆客房。持续细雨敲打旧窗与屋檐，偶尔风掠过窗缝。约40秒纯环境声，平稳可循环。无人声，无音乐。",
    "attic": "1931年中国港口旅馆阁楼。屋顶雨声、木梁伸缩轻响、远处港风。约40秒纯环境声，压抑但自然，可循环。无人声，无音乐。",
    "tension": "1931年中国港口旅馆门外的深夜。远处海风、门轴轻响、脚下木板极轻的吱声，安静中带戒备。约40秒纯环境声，可循环。无人声，无音乐，无恐怖惊吓。",
}


# 场景配乐：与播放器的五种情绪对应，纯器乐循环；加载失败时播放器退回代码合成的配乐。
MUSIC = {
    "calm": "夜晚旅馆氛围的纯器乐背景音乐。钢琴与弦乐缓慢流动，温暖而略带忧伤，旋律简单，节奏很慢。约40秒，首尾自然衔接，可循环。纯音乐，没有人声和歌词。",
    "study": "深夜书房氛围的纯器乐背景音乐。钢琴与弦乐稀疏而平稳，冷静专注，节奏很慢。约40秒，首尾自然衔接，可循环。纯音乐，没有人声和歌词。",
    "tense": "一九三一年中国雾港旅馆命案之夜的背景音乐。低沉的大提琴与低音提琴持续音，间或轻轻的定音鼓和一两声高处的弦乐泛音，悬疑而压抑，但不惊吓，节奏很慢。约40秒纯器乐，首尾自然衔接，可循环。无人声，无歌词，无环境音效。",
    "dark": "雨夜氛围的纯器乐背景音乐。弦乐与钢琴缓慢低回，沉静而略带忧郁，节奏很慢。约40秒，首尾自然衔接，可循环。纯音乐，没有人声和歌词。",
    "dawn": "清晨氛围的纯器乐背景音乐。钢琴与弦乐缓慢上行，雾散天亮的释然感，克制而温暖，节奏很慢。约40秒，首尾自然衔接，可循环。纯音乐，没有人声和歌词。",
}


def jobs() -> list[dict]:
    result = json.loads(subprocess.check_output(["node", "tools/seed_audio_plan.mjs"], cwd=ROOT))
    for name, prompt in AMBIENCE.items():
        result.append({"id": "ambience_" + name, "kind": "ambience", "place": name, "prompt": prompt})
    for mood, prompt in MUSIC.items():
        result.append({"id": "music_" + mood, "kind": "music", "mood": mood, "prompt": prompt})
    return result


def clean(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum())


def cue_times(job: dict, subtitle: dict | None, duration: float) -> tuple[float, list[float]]:
    if not subtitle or not job.get("pages"):
        return 0.0, []
    words = [word for sentence in subtitle.get("sentences", []) for word in sentence.get("words", [])]
    observed = ""
    ends = []
    for word in words:
        token = clean(word.get("text", ""))
        observed += token
        ends.extend([word.get("end_time", 0) / 1000] * len(token))
    source = "".join(clean(page["text"]) for page in job["pages"])
    if not source or not observed:
        return 0.0, []
    match = SequenceMatcher(None, source, observed, autojunk=False)
    ratio = match.ratio()
    positions = [0] * (len(source) + 1)
    for tag, i1, i2, j1, j2 in match.get_opcodes():
        if i1 == i2:
            positions[i1] = j2
            continue
        for i in range(i1, i2 + 1):
            positions[i] = round(j1 + (i - i1) * (j2 - j1) / (i2 - i1))
    cues = []
    count = 0
    for page in job["pages"]:
        count += len(clean(page["text"]))
        index = min(len(ends), max(1, positions[count])) - 1
        cues.append(round(min(duration, ends[index]), 3))
    cues[-1] = duration
    return round(ratio, 4), cues


def clamp_cues(cues: list[float], duration: float) -> list[float]:
    """短页至少停留 MIN_PAGE_SECONDS，避免一句还没读完就跳到下一页。"""
    if not cues or duration <= 0:
        return cues
    out = []
    previous = 0.0
    for index, cue in enumerate(cues):
        value = max(float(cue), (previous + MIN_PAGE_SECONDS) if index else MIN_PAGE_SECONDS)
        if index == len(cues) - 1:
            value = duration
        value = min(duration, value)
        value = min(round(value, 3), int(duration * 1000) / 1000)  # 四舍五入不能超过音频时长
        out.append(value)
        previous = value
    return out


def runtime_manifest(saved: dict, planned: list[dict]) -> dict:
    plan = {j["id"]: j for j in planned}
    result = {"scenes": {}, "choices": {}, "ambience": {}, "music": {}}
    for asset in saved["assets"]:
        job = {**plan.get(asset["id"], {}), **asset}
        if not (OUT / asset["file"]).exists():
            continue
        if job["kind"] == "ambience":
            result["ambience"][job["place"]] = asset["file"]
            continue
        if job["kind"] == "music":
            result["music"][job["mood"]] = asset["file"]
            continue
        ratio, cues = cue_times(job, asset.get("subtitle"), asset.get("duration") or 0)
        threshold = WHISPER_MATCH if asset.get("subtitle_source", "").startswith("whisper") else 0.95
        if not asset.get("subtitle") and asset.get("cues"):
            # 早先用 fal 重做的场景没有字幕，页时间是对齐后直接记录的。
            ratio, cues = 1.0, list(asset["cues"])
        cues = clamp_cues(cues, float(asset.get("duration") or 0))
        if ratio < threshold or not cues:
            continue  # Human review or regeneration required before shipping inaccurate speech.
        compact = {"file": asset["file"], "cues": cues, "duration": asset["duration"]}
        if job["kind"] == "scene":
            result["scenes"][job["scene_id"]] = compact
        else:
            result["choices"][json.dumps([job["scene_id"], job["source_text"], ], ensure_ascii=False, separators=(",", ":"))] = compact
    return result


def request_audio(job: dict, token: str, app_id: str) -> dict:
    payload = {
        "model": MODEL,
        "text_prompt": job["prompt"],
        "audio_config": {"format": "mp3", "sample_rate": 48000, "pitch_rate": 0,
                         "speech_rate": 10 if len(clean(job.get("source_text", ""))) > 360 else 0,
                         "loudness_rate": 0,
                         "enable_subtitle": job["kind"] != "ambience"},
        "watermark": {},
    }
    req = Request(API, json.dumps(payload, ensure_ascii=False).encode(), {
        "Content-Type": "application/json", "X-Api-app-id": app_id,
        "Authorization": "Bearer " + token,
    })
    try:
        with urlopen(req, timeout=300) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Seed Audio HTTP {exc.code}: {exc.read(200).decode(errors='replace')}") from None
    if not data.get("audio"):
        raise RuntimeError(f"Seed Audio failed: {data.get('code')} {data.get('message')}")
    audio = base64.b64decode(data["audio"])
    path = OUT / (job["id"] + ".mp3")
    filter_spec = "loudnorm=I=-34:TP=-6:LRA=8" if job["kind"] == "ambience" else "loudnorm=I=-18:TP=-2:LRA=8"
    raw = path.with_suffix(".raw.mp3")
    raw.write_bytes(audio)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                    "-af", filter_spec, "-codec:a", "libmp3lame", "-b:a", "128k", str(path)], check=True)
    raw.unlink()
    post = {"filter": filter_spec, "codec": "mp3 128k",
            "source_sha256": hashlib.sha256(audio).hexdigest()}
    audio = path.read_bytes()
    ratio, _ = cue_times(job, data.get("subtitle"), data.get("duration") or 0)
    return {**job, "file": path.name, "model": MODEL, "api": API,
            "audio_config": payload["audio_config"],
            "duration": data.get("duration"), "original_duration": data.get("original_duration"),
            "cost_cny": round(float(data.get("original_duration") or 0) / 60 * RATE_CNY_PER_MINUTE, 3),
            "subtitle": data.get("subtitle"), "transcript_match": ratio,
            "sha256": hashlib.sha256(audio).hexdigest(), "post": post,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def whisper_subtitle(path: Path) -> dict:
    """用本机 Whisper 取逐词时间，整理成与 Seed Audio 字幕相同的结构。"""
    out = Path("/private/tmp/taleloom-whisper")
    out.mkdir(exist_ok=True)
    subprocess.run(["whisper", str(path), "--model", "small", "--language", "zh", "--word_timestamps", "True",
                    "--output_format", "json", "--output_dir", str(out), "--verbose", "False"],
                   check=True, capture_output=True)
    data = json.loads((out / (path.stem + ".json")).read_text(encoding="utf-8"))
    return {"sentences": [{"words": [{"text": w["word"], "end_time": round(w["end"] * 1000)}
                                     for w in segment.get("words", [])]} for segment in data["segments"]]}


def voice_pitch(path: Path, start: float, end: float) -> float:
    """估计一段语音的基频中位数（Hz），用来复核阿芸是不是女声；算不出时返回 0。"""
    import numpy as np
    rate = 16000
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(start), "-to", str(end), "-i", str(path),
                          "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"], check=True, capture_output=True).stdout
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    found = []
    for offset in range(0, len(samples) - 1024, 512):
        frame = samples[offset:offset + 1024]
        if np.sqrt(np.mean(frame ** 2)) < 600:
            continue
        frame = frame - frame.mean()
        corr = np.correlate(frame, frame, "full")[1023:]
        low, high = rate // 400, rate // 70
        lag = low + int(np.argmax(corr[low:high]))
        if corr[lag] > 0.45 * corr[0]:
            found.append(rate / lag)
    return round(float(np.median(found)), 1) if found else 0.0


def request_audio_fal(job: dict, key: str) -> dict:
    """fal 托管的 Seed Audio 1.0：生成、整理响度，再用 Whisper 对齐每页时间。"""
    has_ayun = "阿芸（" in job["prompt"]
    payload = {"prompt": (AYUN_NOTE + " " if has_ayun else "") + job["prompt"],
               "output_format": "mp3", "sample_rate": 44100, "multilingual": True}
    if has_ayun:
        payload["audio_urls"] = [AYUN_REFERENCE]
    req = Request(FAL_API, json.dumps(payload, ensure_ascii=False).encode(), {
        "Content-Type": "application/json", "Authorization": "Key " + key})
    try:
        with urlopen(req, timeout=900) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"fal HTTP {exc.code}: {exc.read(300).decode(errors='replace')}") from None
    url = (data.get("audio") or {}).get("url")
    if not url:
        raise RuntimeError(f"fal returned no audio: {json.dumps(data, ensure_ascii=False)[:200]}")
    with urlopen(url, timeout=300) as response:
        audio = response.read()
    path = OUT / (job["id"] + ".mp3")
    filter_spec = {"ambience": "loudnorm=I=-34:TP=-6:LRA=8", "music": "loudnorm=I=-28:TP=-4:LRA=9"}.get(
        job["kind"], "loudnorm=I=-18:TP=-2:LRA=8")
    raw = path.with_suffix(".raw.mp3")
    raw.write_bytes(audio)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                    "-af", filter_spec, "-codec:a", "libmp3lame", "-b:a", "128k", str(path)], check=True)
    raw.unlink()
    duration = round(float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])), 2)
    result = {**job, "file": path.name, "model": MODEL, "api": FAL_API,
              "audio_config": {k: v for k, v in payload.items() if k not in ("prompt", "audio_urls")},
              "duration": duration, "original_duration": duration,
              "cost_usd": round(duration / 60 * FAL_USD_PER_MINUTE, 4),
              "cost_cny": round(duration / 60 * FAL_USD_PER_MINUTE * USD_TO_CNY, 3),
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "post": {"filter": filter_spec, "codec": "mp3 128k", "source_sha256": hashlib.sha256(audio).hexdigest()},
              "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if has_ayun:
        result["reference"] = "A Yun female reference audio (fal upload)"
        result["reference_url"] = AYUN_REFERENCE
    if job["kind"] in ("ambience", "music"):
        result["transcript_match"] = 1.0
        return result
    subtitle = whisper_subtitle(path)
    ratio, cues = cue_times(job, subtitle, duration)
    result.update({"subtitle": subtitle, "subtitle_source": "whisper-small word timestamps", "transcript_match": ratio})
    if has_ayun and cues:
        starts = [0.0] + cues[:-1]
        result["ayun_pitch_hz"] = [voice_pitch(path, a, b) for page, a, b in zip(job["pages"], starts, cues)
                                   if page.get("speaker") == "阿芸" and b - a > 0.4]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Show planned requests without calling the API")
    parser.add_argument("--generate", action="store_true", help="Generate missing assets")
    parser.add_argument("--refresh", action="store_true", help="Rebuild runtime mapping from the saved manifest")
    parser.add_argument("--force", action="store_true", help="Archive selected assets and regenerate them")
    parser.add_argument("--prune-review", action="store_true", help="Move mismatched clips out of the web bundle")
    parser.add_argument("--retry-review", action="store_true", help="Regenerate mismatched clips from the literal text")
    parser.add_argument("--kind", choices=("scene", "choice", "ambience", "music"))
    parser.add_argument("--limit", type=int, default=0, help="Maximum new requests (0 = all)")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent requests, at most 5")
    parser.add_argument("--max-cost-cny", type=float, default=0,
                        help="Hard ceiling for this run; reserves ¥2 for each in-flight request")
    parser.add_argument("--only", help="Generate one job ID")
    parser.add_argument("--key-file", type=Path, default=Path("/private/tmp/taleloom-volcengine.key"))
    parser.add_argument("--app-id", default="9079187114")
    parser.add_argument("--provider", choices=("volcengine", "fal"), default="volcengine")
    parser.add_argument("--fal-key-file", type=Path, default=Path("/private/tmp/taleloom-fal.key"))
    args = parser.parse_args()
    if args.provider == "fal":
        args.key_file = args.fal_key_file
    all_jobs = jobs()
    job_by_id = {j["id"]: j for j in all_jobs}
    planned = [j for j in all_jobs if (not args.kind or j["kind"] == args.kind)
               and (not args.only or j["id"] == args.only)]
    saved = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"assets": []}
    if args.prune_review or args.retry_review:
        reviewed = []
        for asset in list(saved["assets"]):
            job = {**job_by_id.get(asset["id"], {}), **asset}
            if job["kind"] in ("ambience", "music") or asset.get("cues"):
                continue
            ratio, _ = cue_times(job, asset.get("subtitle"), asset.get("duration") or 0)
            if ratio >= (WHISPER_MATCH if asset.get("subtitle_source", "").startswith("whisper") else 0.95):
                continue
            saved["assets"].remove(asset)
            asset["rejection_reason"] = f"transcript mismatch ({ratio:.3f})"
            saved.setdefault("rejected", []).append(asset)
            source = OUT / asset["file"]
            if source.exists():
                rejected = Path("/private/tmp/taleloom-seed-rejected") / f"{asset['id']}-{len(saved['rejected'])}.mp3"
                rejected.parent.mkdir(exist_ok=True)
                shutil.move(source, rejected)
            reviewed.append(asset["id"])
        MANIFEST.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        RUNTIME.write_text(json.dumps(runtime_manifest(saved, all_jobs), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Moved {len(reviewed)} mismatched clips out of the web bundle")
        if args.prune_review:
            return
        planned = [{**job, "prompt": job["prompt"].replace("「", "").replace("」", ""),
                    "prompt_mode": "quoted_terms_as_narration"}
                   for job in planned if job["id"] in reviewed]
        args.generate = True
    if args.refresh:
        RUNTIME.write_text(json.dumps(runtime_manifest(saved, all_jobs), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: len(v) for k, v in runtime_manifest(saved, all_jobs).items()}))
        return
    if args.force:
        force_ids = {j["id"] for j in planned}
        for asset in list(saved["assets"]):
            if asset["id"] not in force_ids:
                continue
            saved["assets"].remove(asset)
            asset["rejection_reason"] = "forced regeneration"
            saved.setdefault("rejected", []).append(asset)
            source = OUT / asset["file"]
            if source.exists():
                rejected = Path("/private/tmp/taleloom-seed-rejected") / f"{asset['id']}-forced-{len(saved['rejected'])}.mp3"
                rejected.parent.mkdir(exist_ok=True)
                shutil.move(source, rejected)
        MANIFEST.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        RUNTIME.write_text(json.dumps(runtime_manifest(saved, all_jobs), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    done = {j["id"] for j in saved["assets"]}
    pending = [j for j in planned if j["id"] not in done]
    if args.list or not args.generate:
        counts = {k: sum(j["kind"] == k for j in pending) for k in ("scene", "choice", "ambience", "music")}
        seconds = sum(40 if j["kind"] in ("ambience", "music") else len(clean(j["source_text"])) / 3.5 for j in pending)
        print(json.dumps({"pending": counts, "total": len(pending),
                          "estimated_cost_cny": round(seconds / 60, 2),
                          "ids": [j["id"] for j in pending]}, ensure_ascii=False))
        return
    if not args.key_file.exists() or (args.key_file.stat().st_mode & 0o077):
        parser.error("key file missing or not private (required mode 0600)")
    token = args.key_file.read_text(encoding="utf-8").strip()
    if not token:
        parser.error("key file is empty")
    OUT.mkdir(parents=True, exist_ok=True)
    selected = pending[:args.limit or None]
    if len(selected) > 3 and args.max_cost_cny <= 0:
        parser.error("batch generation requires --max-cost-cny")
    failed = []
    spent = 0.0
    queue = iter(selected)
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 5))) as pool:
        futures = {}
        exhausted = False
        while futures or not exhausted:
            while not exhausted and len(futures) < max(1, min(args.workers, 5)):
                if args.max_cost_cny and spent + 2 * (len(futures) + 1) > args.max_cost_cny:
                    exhausted = True
                    break
                try:
                    job = next(queue)
                except StopIteration:
                    exhausted = True
                    break
                if args.provider == "fal":
                    futures[pool.submit(request_audio_fal, job, token)] = job
                else:
                    futures[pool.submit(request_audio, job, token, args.app_id)] = job
            if not futures:
                break
            completed, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in completed:
                job = futures.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    failed.append(job["id"])
                    print(f"{job['id']}: FAILED {exc}", file=sys.stderr, flush=True)
                    continue
                spent += result["cost_cny"]
                saved["assets"].append(result)
                tmp = MANIFEST.with_suffix(".tmp")
                tmp.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                os.replace(tmp, MANIFEST)
                RUNTIME.write_text(json.dumps(runtime_manifest(saved, all_jobs), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"{job['id']}: {result['duration']}s, ¥{result['cost_cny']:.3f}, match={result['transcript_match']:.3f}", flush=True)
    remaining = len([j for j in selected if j["id"] not in {a["id"] for a in saved["assets"]}])
    print(f"New generation cost: ¥{spent:.3f}; remaining from this run: {remaining}")
    if failed:
        print(f"Failed jobs: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
