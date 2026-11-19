# -*- coding: utf-8 -*-
"""守护进程包装：启动/停止/暂停 huayi_course_guard.py，并解析它的输出写入事件流。"""
import ctypes
import os
import re
import subprocess
import sys
import threading
import time

from db import add_event, create_task, update_task

PROGRESS_RE = re.compile(r"已播 (\d+)/(\d+) 秒，分片=(-?\d+)，停滞=(\d+)")
START_RE = re.compile(r"启动：课件=(.*?)，时长=(\d+) 秒")
SWITCH_RE = re.compile(r"切换到下一课件：(.*?)，时长=(\d+) 秒")


def classify(line):
    """按输出内容归类事件，供页面筛选与着色。"""
    if "截图" in line:
        return "截图"
    if "进度：" in line:
        return "进度"
    if "警告" in line or "错误" in line or "失败" in line:
        return "错误"
    if "弹窗" in line:
        return "弹窗"
    if "恢复" in line or "校正" in line:
        return "恢复"
    if "测验" in line or "考试" in line or "试题" in line:
        return "考试"
    if "启动" in line or "停止" in line or "切换" in line:
        return "系统"
    return "日志"


def _nt_call(name, pid):
    """用 NtSuspendProcess/NtResumeProcess 冻结守护进程，暂停期间它不会误点屏幕。"""
    process_suspend_resume = 0x0800
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    handle = kernel32.OpenProcess(process_suspend_resume, False, pid)
    if not handle:
        return False
    try:
        return getattr(ntdll, name)(handle) == 0
    finally:
        kernel32.CloseHandle(handle)


class GuardWorker:
    def __init__(self, config):
        self.config = config
        self._lock = threading.Lock()
        self._process = None
        self._reader = None
        self._paused = False
        self._task_id = None
        self._started_at = None
        self._lesson = {"index": 0, "name": "", "duration": 0}
        self._progress = {"played": 0, "duration": 0, "segment": -1, "stalled": 0}
        self._last_output = 0.0
        self._last_line = ""
        self._exit_code = None
        self._stopping = False

    # ---------- 对外接口 ----------
    def start(self, params):
        with self._lock:
            if self._process and self._process.poll() is None:
                return False, "守护已在运行"
            args = self._build_command(params)
            self._task_id = create_task(
                params.get("project_name", ""),
                int(params.get("lesson_index") or 0),
                params.get("lesson_name", ""),
                int(params.get("duration") or 0),
            )
            log_path = self.config["guard_log"]
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            self._process = subprocess.Popen(
                args,
                cwd=str(self.config["repo_root"]),
                env={**os.environ, "HUAYI_DEVICE": self.config["device"]},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
            )
            self._paused = False
            self._exit_code = None
            self._stopping = False
            self._started_at = time.time()
            self._last_output = time.time()
            self._last_line = ""
            self._lesson = {
                "index": int(params.get("lesson_index") or 0),
                "name": params.get("lesson_name", ""),
                "duration": int(params.get("duration") or 0),
            }
            self._progress = {
                "played": 0,
                "duration": int(params.get("duration") or 0),
                "segment": -1,
                "stalled": 0,
            }
            self._reader = threading.Thread(target=self._read_output, args=(self._process, self._task_id),
                                            daemon=True)
            self._reader.start()
            add_event("启动守护：%s" % " ".join(args[1:]), "系统", "info", self._task_id)
            return True, "已启动"

    def stop(self):
        with self._lock:
            process = self._process
            if not process or process.poll() is not None:
                return False, "守护未在运行"
            if self._paused:
                _nt_call("NtResumeProcess", process.pid)
                self._paused = False
            self._stopping = True
            process.terminate()
            return True, "正在停止"

    def pause(self):
        with self._lock:
            if not self._process or self._process.poll() is not None:
                return False, "守护未在运行"
            if self._paused:
                return False, "已经是暂停状态"
            # 先让播放器暂停，再冻结守护，避免它把暂停当卡顿去恢复。
            self._adb("shell", "input", "keyevent", "85")
            ok = _nt_call("NtSuspendProcess", self._process.pid)
            if not ok:
                return False, "暂停失败（无法挂起守护进程）"
            self._paused = True
            add_event("已暂停：播放器暂停，守护进程挂起", "系统", "warning", self._task_id)
            return True, "已暂停"

    def resume(self):
        with self._lock:
            if not self._process or self._process.poll() is not None:
                return False, "守护未在运行"
            if not self._paused:
                return False, "当前不是暂停状态"
            ok = _nt_call("NtResumeProcess", self._process.pid)
            if not ok:
                return False, "继续失败（无法恢复守护进程）"
            self._paused = False
            self._adb("shell", "input", "keyevent", "126")
            add_event("已继续：恢复守护进程并发送播放键", "系统", "info", self._task_id)
            return True, "已继续"

    def recover(self):
        result = self._adb("shell", "input", "keyevent", "126")
        add_event("强制恢复播放：keyevent 126（%s）" % ("成功" if result else "adb 调用失败"),
                  "恢复", "warning" if not result else "info", self._task_id)
        return result

    def status(self):
        process = self._process
        running = bool(process and process.poll() is None)
        now = time.time()
        progress = dict(self._progress)
        percent = 0
        if progress["duration"] > 0:
            percent = round(min(progress["played"] / progress["duration"], 1.0) * 100, 1)
        return {
            "running": running,
            "paused": self._paused,
            "pid": process.pid if running else None,
            "exit_code": self._exit_code,
            "stopped_manually": self._stopping,
            "task_id": self._task_id,
            "started_at": self._started_at,
            "uptime": int(now - self._started_at) if self._started_at else 0,
            "lesson": dict(self._lesson),
            "progress": dict(progress, percent=percent),
            "last_output_seconds": int(now - self._last_output) if self._last_output else None,
            "last_line": self._last_line,
        }

    # ---------- 内部 ----------
    def _build_command(self, params):
        args = [
            sys.executable, "-u", str(self.config["guard_script"]),
            "--interval", str(int(params.get("interval") or 60)),
            "--max-hours", str(float(params.get("max_hours") or 4.0)),
            "--out-root", params.get("out_root") or self.config["tasks_root"],
            "--log", self.config["guard_log"],
        ]
        if int(params.get("lesson_index") or 0):
            args += ["--lesson-index", str(int(params["lesson_index"]))]
        if params.get("lesson_name"):
            args += ["--lesson-name", params["lesson_name"]]
        if int(params.get("duration") or 0) >= 60:
            args += ["--duration", str(int(params["duration"]))]
        if params.get("next_name"):
            args += ["--next-name", params["next_name"],
                     "--next-index", str(int(params.get("next_index") or 0))]
        # 不传 --played：守护会用 logcat 分片序号自校正，传值反而会误导。
        return args

    def _read_output(self, process, task_id):
        try:
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                self._last_output = time.time()
                self._last_line = line
                self._parse(line)
                add_event(line, classify(line), "error" if classify(line) == "错误" else "info", task_id)
        finally:
            code = process.wait()
            self._exit_code = code
            if self._stopping:
                level, message, task_status = "info", "守护已停止", "stopped"
            elif code == 0:
                level, message, task_status = "info", "守护进程正常退出（code=0）", "stopped"
            else:
                level, message, task_status = "error", "守护进程异常退出（code=%s）" % code, "failed"
            add_event(message, "系统", level, task_id)
            if task_id:
                update_task(task_id, status=task_status,
                            played=self._progress["played"], segment=self._progress["segment"],
                            ended_at=time.strftime("%Y-%m-%d %H:%M:%S"))

    def _parse(self, line):
        match = PROGRESS_RE.search(line)
        if match:
            played, duration, segment, stalled = (int(value) for value in match.groups())
            self._progress = {"played": played, "duration": duration, "segment": segment, "stalled": stalled}
        match = START_RE.search(line)
        if match:
            self._lesson["name"] = match.group(1)
            self._lesson["duration"] = int(match.group(2))
        match = SWITCH_RE.search(line)
        if match:
            self._lesson["name"] = match.group(1)
            self._lesson["duration"] = int(match.group(2))
            self._progress = {"played": 0, "duration": int(match.group(2)), "segment": -1, "stalled": 0}

    def _adb(self, *args):
        try:
            subprocess.run(
                [self.config["adb_path"], "-s", self.config["device"], *args],
                capture_output=True, timeout=20,
            )
            return True
        except Exception as error:
            add_event("adb 调用失败：%s" % error, "错误", "error", self._task_id)
            return False
