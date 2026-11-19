# -*- coding: utf-8 -*-
"""掌上华医刷课控制台：本地 Web 服务（FastAPI + SQLite + SSE）。

启动：python huayi_console/app.py    然后在浏览器打开 http://127.0.0.1:8765
"""
import asyncio
import json
import os
import re
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import db
from worker import GuardWorker

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
STATIC = ROOT / "static"


def load_env():
    """读取 huayi_console/.env；已在系统环境里的变量优先。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def build_config():
    return {
        "adb_path": os.environ.get("ADB_PATH", r"E:\leidian\LDPlayer14\adb.exe"),
        "device": os.environ.get("HUAYI_DEVICE", "127.0.0.1:5555"),
        "port": int(os.environ.get("CONSOLE_PORT", "8765")),
        "repo_root": REPO,
        "guard_script": REPO / "flybirds_demo" / "pscript" / "huayi_course_guard.py",
        "tasks_root": os.environ.get(
            "HUAYI_TASKS_ROOT", str(REPO / "app_page_captures" / "huayi_course" / "tasks")),
        "guard_log": os.environ.get(
            "HUAYI_GUARD_LOG", str(REPO / "app_page_captures" / "huayi_course" / "guard.log")),
    }


load_env()
CONFIG = build_config()
worker = GuardWorker(CONFIG)
DEVICE = {"connected": None, "activity": "", "checked_at": 0, "error": ""}
DEVICE_LOCK = threading.Lock()


def adb(*args, timeout=20):
    try:
        return subprocess.run([CONFIG["adb_path"], "-s", CONFIG["device"], *args],
                              capture_output=True, timeout=timeout)
    except Exception:
        return None


def resolve_device():
    """配置的设备号不在线时，若只有一个 adb 设备则自动改用（例如模拟器重启后端口变化）。"""
    try:
        result = subprocess.run([CONFIG["adb_path"], "devices"], capture_output=True, timeout=15)
        lines = result.stdout.decode("utf-8", "ignore").splitlines()[1:]
        online = [line.split()[0] for line in lines if line.strip().endswith("device")]
    except Exception:
        return
    if CONFIG["device"] in online or len(online) != 1:
        return
    original = CONFIG["device"]
    CONFIG["device"] = online[0]
    db.add_event("配置的设备 %s 未连接，自动改用 %s" % (original, online[0]), "系统", "warning")


def probe_device():
    """每 10 秒体检一次：adb 是否在线、掌上华医当前 Activity。状态变化才写事件。"""
    previous = DEVICE["connected"]
    listing = adb("devices", timeout=15)
    connected = False
    error = ""
    activity = ""
    if listing is None or listing.returncode != 0:
        error = "adb 调用失败"
    else:
        text = listing.stdout.decode("utf-8", "ignore")
        connected = any(line.strip().endswith("device") for line in text.splitlines()[1:])
        if not connected:
            error = "adb devices 中无在线设备"
    if connected:
        focus = adb("shell", "dumpsys window | grep mCurrentFocus", timeout=15)
        if focus is not None and focus.returncode == 0:
            match = re.search(r"com\.huayi\.cme/([\w.]+)", focus.stdout.decode("utf-8", "ignore"))
            activity = match.group(1) if match else ""
            if not activity:
                error = "前台不是掌上华医"
    with DEVICE_LOCK:
        DEVICE.update(connected=connected, activity=activity,
                      checked_at=time.time(), error=error)
    if previous is not None and previous != connected:
        if connected:
            db.add_event("设备已连接：%s（当前页面 %s）" % (CONFIG["device"], activity or "非掌上华医"),
                         "系统", "info")
        else:
            db.add_event("设备断开：%s（%s）" % (CONFIG["device"], error), "错误", "error")


def device_monitor():
    while True:
        probe_device()
        time.sleep(10)


@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    resolve_device()
    db.add_event("控制台服务启动（设备 %s）" % CONFIG["device"], "系统", "info")
    threading.Thread(target=device_monitor, daemon=True).start()
    yield


app = FastAPI(title="掌上华医刷课控制台", lifespan=lifespan)


class StartRequest(BaseModel):
    lesson_index: int = 0
    lesson_name: str = ""
    duration: int = 0
    next_index: int = 0
    next_name: str = ""
    project_name: str = ""
    interval: int = 60
    max_hours: float = 4.0
    out_root: str = ""


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    now = time.time()
    with DEVICE_LOCK:
        device = dict(DEVICE)
        device["age"] = int(now - device["checked_at"]) if device["checked_at"] else None
    device["serial"] = CONFIG["device"]
    guard = worker.status()
    warnings = []
    if device["connected"] is False:
        warnings.append({"level": "error", "text": "设备未连接：请检查模拟器与 adb（%s）" % CONFIG["device"]})
    if device["connected"] and guard["running"] and device["activity"] \
            and "MediaPlayNewActivity" not in device["activity"]:
        warnings.append({"level": "warning",
                         "text": "当前不在播放器页面（%s），守护可能无法工作" % device["activity"]})
    if guard["running"] and guard["last_output_seconds"] is not None and guard["last_output_seconds"] > 180:
        warnings.append({"level": "warning",
                         "text": "守护已 %d 秒无输出，可能已卡死" % guard["last_output_seconds"]})
    if guard["running"] and guard["progress"]["stalled"] >= 2:
        warnings.append({"level": "warning",
                         "text": "播放停滞 %d 轮，守护正在尝试恢复" % guard["progress"]["stalled"]})
    if guard["exit_code"] not in (None, 0) and not guard["stopped_manually"]:
        warnings.append({"level": "error", "text": "守护上次异常退出（code=%s）" % guard["exit_code"]})
    return {"guard": guard, "device": device,
            "console": {"port": CONFIG["port"], "tasks_root": CONFIG["tasks_root"]},
            "warnings": warnings}


@app.post("/api/guard/start")
def guard_start(payload: StartRequest):
    if not Path(CONFIG["guard_script"]).exists():
        raise HTTPException(500, "找不到守护脚本：%s" % CONFIG["guard_script"])
    ok, message = worker.start(payload.dict())
    if not ok:
        raise HTTPException(409, message)
    return {"ok": True, "message": message}


@app.post("/api/guard/stop")
def guard_stop():
    ok, message = worker.stop()
    if not ok:
        raise HTTPException(409, message)
    return {"ok": True, "message": message}


@app.post("/api/guard/pause")
def guard_pause():
    ok, message = worker.pause()
    if not ok:
        raise HTTPException(409, message)
    return {"ok": True, "message": message}


@app.post("/api/guard/resume")
def guard_resume():
    ok, message = worker.resume()
    if not ok:
        raise HTTPException(409, message)
    return {"ok": True, "message": message}


@app.post("/api/device/recover")
def device_recover():
    ok = worker.recover()
    return {"ok": ok, "message": "已发送播放键" if ok else "adb 调用失败"}


@app.get("/api/events")
def events(after: int = 0, limit: int = 200, tail: bool = False):
    rows = db.tail_events(limit) if tail else db.recent_events(after_id=after, limit=limit)
    return {"events": rows}


@app.get("/api/events/stream")
async def events_stream(request: Request, after: int = 0):
    async def generate():
        last = after
        idle = 0
        while True:
            if await request.is_disconnected():
                break
            rows = db.recent_events(after_id=last, limit=100)
            if rows:
                idle = 0
                for row in rows:
                    last = row["id"]
                    yield "data: %s\n\n" % json.dumps(row, ensure_ascii=False)
            else:
                idle += 1
                if idle >= 15:
                    idle = 0
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=CONFIG["port"], log_level="info")
