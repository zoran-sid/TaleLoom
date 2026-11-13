"""用 MiniMax H3 生成影像模式的场景背景镜头。负责人：ZC。

只在制作阶段运行；游戏运行时不调用生成服务。镜头清单与提示词在
``tools/minimax_shots.json``，成品写入 ``web/cinematic/media/``：

- ``<id>.mp4``：去掉音轨、首尾交叉淡化成无缝循环的背景镜头；
- ``<id>.jpg``：循环第一帧，视频未加载或关闭动态效果时显示；
- ``manifest.json``：每段的任务号、模型、提示词、参考图、费用与文件哈希。

密钥只从本机权限为 0600 的文件读取（默认 ``/private/tmp/taleloom-minimax.key``），
不接受命令行参数，也不写入仓库。先运行 ``--list`` 查看待生成数量与预计费用::

    python3 tools/minimax_video.py --list
    python3 tools/minimax_video.py --generate --max-cost-cny 100
    python3 tools/minimax_video.py --generate --only zhou-portrait --force
    python3 tools/minimax_video.py --posters      # 给已有转场生成末帧静帧，不调用接口
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "tools" / "minimax_shots.json"
MEDIA = ROOT / "web" / "cinematic" / "media"
MANIFEST = MEDIA / "manifest.json"
RAW = Path("/private/tmp/taleloom-minimax-raw")
API = "https://api.minimax.cn"
FADE = 0.7          # 循环首尾交叉淡化的秒数
POLL_SECONDS = 15
TIMEOUT_SECONDS = 30 * 60


def load_plan() -> dict:
    """读取镜头清单；每个镜头的完整提示词 = 画风说明 + 画面描述。"""
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    for shot in plan["shots"]:
        shot["full_prompt"] = plan["styles"][shot["style"]] + shot["prompt"]
    return plan


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"shots": {}, "rejected": [], "spent_cny": 0.0}


def save_manifest(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_key(path: Path) -> str:
    """读取密钥文件；权限过宽时拒绝使用。"""
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"{path} 的权限应为 0600，当前为 {mode:o}")
    return path.read_text(encoding="utf-8").strip()


def call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"HTTP {error.code}: {detail}") from None


def data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def submit(plan: dict, shot: dict, token: str) -> str:
    """创建生成任务，返回任务号。参考图以 reference_image 传入，只约束画风或人物长相。"""
    content = [{"type": "text", "text": shot["full_prompt"]}]
    for name in shot.get("refs", []):
        ref = ROOT / plan["refs"][name]
        if not ref.exists():
            raise RuntimeError(f"缺少参考图 {ref}（先生成对应的基准镜头）")
        content.append({"type": "image_url", "image_url": {"url": data_url(ref)}, "role": "reference_image"})
    reply = call("POST", "/v2/video_generation", token, {
        "model": plan["model"], "content": content, "resolution": plan["resolution"],
        "duration": plan["duration"], "ratio": plan["ratio"]})
    task_id = reply.get("task_id") or (reply.get("task") or {}).get("id")
    if not task_id:
        raise RuntimeError(f"没有返回任务号：{json.dumps(reply, ensure_ascii=False)[:300]}")
    return str(task_id)


def wait(task_id: str, token: str) -> dict:
    """轮询任务直到结束；成功时返回任务对象。"""
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        reply = call("GET", f"/v2/query/video_generation/{task_id}", token)
        task = reply.get("task", reply)
        if task.get("status") == "succeeded":
            return task
        if task.get("status") in ("failed", "cancelled"):
            raise RuntimeError(f"任务 {task_id} {task.get('status')}：{json.dumps(task, ensure_ascii=False)[:300]}")
        time.sleep(POLL_SECONDS)
    raise RuntimeError(f"任务 {task_id} 超过 {TIMEOUT_SECONDS // 60} 分钟仍未完成")


def run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_loop(raw: Path, shot_id: str) -> dict:
    """去音轨，把最后 FADE 秒淡入开头，得到可以无缝循环的镜头，并导出第一帧静帧。"""
    duration = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)))
    video, poster = MEDIA / f"{shot_id}.mp4", MEDIA / f"{shot_id}.jpg"
    graph = (
        f"[0:v]trim=start={FADE}:end={duration - FADE},setpts=PTS-STARTPTS[body];"
        f"[0:v]trim=start={duration - FADE}:end={duration},setpts=PTS-STARTPTS[tail];"
        f"[0:v]trim=start=0:end={FADE},setpts=PTS-STARTPTS[head];"
        f"[tail][head]xfade=transition=fade:duration={FADE}:offset=0[cross];"
        "[body][cross]concat=n=2:v=1,format=yuv420p[out]")
    run("ffmpeg", "-loglevel", "error", "-y", "-i", str(raw), "-filter_complex", graph, "-map", "[out]", "-an",
        "-c:v", "libx264", "-preset", "slow", "-crf", "25", "-r", "24", "-movflags", "+faststart", str(video))
    run("ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-frames:v", "1", "-vf", "scale=1024:-2",
        "-q:v", "5", str(poster))
    return {"file": video.name, "poster": poster.name, "raw_duration": round(duration, 2),
            "loop_duration": round(duration - FADE, 2), "sha256": sha256(video), "raw_sha256": sha256(raw),
            "post": {"loop": f"xfade {FADE}s tail into head", "codec": "h264 crf 25, no audio"}}


def produce(plan: dict, shot: dict, token: str) -> dict:
    task_id = submit(plan, shot, token)
    print(f"  已提交 {shot['id']} → {task_id}", flush=True)
    task = wait(task_id, token)
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{shot['id']}-{task_id}.mp4"
    urllib.request.urlretrieve(task["content"]["url"], raw)
    usage = task.get("usage") or {}
    seconds = usage.get("output_seconds", plan["duration"])
    return {"id": shot["id"], "task_id": task_id, "model": plan["model"], "resolution": plan["resolution"],
            "duration": seconds, "ratio": plan["ratio"], "prompt": shot["full_prompt"],
            "references": [plan["refs"][name] for name in shot.get("refs", [])],
            "cost_cny": round(seconds * plan["price_cny_per_second"], 2),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **make_loop(raw, shot["id"])}


def posters_for_transitions() -> None:
    """已有转场（成员此前生成）取最后一帧作静帧：转场播完后停在这一帧上。"""
    for clip in sorted(MEDIA.glob("*.mp4")):
        poster = clip.with_suffix(".jpg")
        if poster.exists():
            continue
        run("ffmpeg", "-loglevel", "error", "-y", "-sseof", "-0.2", "-i", str(clip), "-frames:v", "1",
            "-vf", "scale=1024:-2", "-q:v", "5", str(poster))
        print(f"  静帧 {poster.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--list", action="store_true", help="列出待生成的镜头与预计费用，不调用接口")
    parser.add_argument("--generate", action="store_true", help="生成缺少的镜头")
    parser.add_argument("--posters", action="store_true", help="为已有转场导出末帧静帧，不调用接口")
    parser.add_argument("--only", action="append", help="只处理指定镜头 id，可重复")
    parser.add_argument("--force", action="store_true", help="重做已有镜头，旧记录移入 rejected")
    parser.add_argument("--limit", type=int, default=0, help="本次最多生成几段（0 为全部）")
    parser.add_argument("--workers", type=int, default=4, help="并发任务数，最多 6")
    parser.add_argument("--max-cost-cny", type=float, default=0, help="累计费用上限；超过则不再提交")
    parser.add_argument("--key-file", type=Path, default=Path("/private/tmp/taleloom-minimax.key"))
    args = parser.parse_args()

    if args.posters:
        posters_for_transitions()
        return
    plan, manifest = load_plan(), load_manifest()
    price = plan["duration"] * plan["price_cny_per_second"]
    shots = [s for s in plan["shots"] if not args.only or s["id"] in args.only]
    pending = [s for s in shots if args.force or s["id"] not in manifest["shots"]]
    if args.limit:
        pending = pending[:args.limit]
    summary = {"pending": len(pending), "estimated_cost_cny": round(len(pending) * price, 2),
               "spent_cny": manifest["spent_cny"], "ids": [s["id"] for s in pending]}
    if not args.generate:
        print(json.dumps(summary, ensure_ascii=False))
        return
    if args.max_cost_cny and manifest["spent_cny"] + len(pending) * price > args.max_cost_cny:
        affordable = int((args.max_cost_cny - manifest["spent_cny"]) // price)
        print(f"预算只够再生成 {max(0, affordable)} 段，其余留待确认。", file=sys.stderr)
        pending = pending[:max(0, affordable)]
    if not pending:
        print("没有需要生成的镜头。")
        return
    token = read_key(args.key_file)

    def job(shot: dict) -> tuple[dict, dict | None, str]:
        try:
            return shot, produce(plan, shot, token), ""
        except Exception as error:  # 单个镜头失败不影响其他镜头
            return shot, None, str(error)

    with ThreadPoolExecutor(max_workers=min(6, max(1, args.workers))) as pool:
        for shot, record, error in pool.map(job, pending):
            if record is None:
                print(f"  失败 {shot['id']}：{error}", file=sys.stderr)
                continue
            old = manifest["shots"].get(shot["id"])
            if old:
                manifest["rejected"].append(old)
            manifest["shots"][shot["id"]] = record
            manifest["spent_cny"] = round(manifest["spent_cny"] + record["cost_cny"], 2)
            save_manifest(manifest)
            print(f"  完成 {shot['id']}  ¥{record['cost_cny']}  累计 ¥{manifest['spent_cny']}", flush=True)


if __name__ == "__main__":
    main()
