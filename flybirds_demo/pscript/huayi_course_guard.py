# -*- coding: utf-8 -*-
"""掌上华医继续教育课件播放守护：自动连播、处理弹窗、记录进度。

只做“播放课件”这一件事：不答题、不申请证书、不提交任何表单。
播放状态以 IJK 播放器日志中的 ts 分片序号为依据，避免静态幻灯片被误判为暂停。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ADB = r"E:\leidian\LDPlayer14\adb.exe"
DEVICE = os.environ.get("HUAYI_DEVICE", "127.0.0.1:5555")
PACKAGE = "com.huayi.cme"
POPUP_WORDS = ("继续学习", "继续观看", "我知道了", "知道了", "重试", "刷新", "继续播放")
# 注意：不要点「确定」。播放结束时的「提示」弹窗点确定会直接退回项目页，把播放器关掉。
# 测验页特征：出现「交卷/答题状态/提交」说明已经离开播放器，不能再点屏幕任何位置。
QUIZ_MARKS = ("交卷", "答题状态", "提交")
# 播放器正常结束时会显示「谢谢观看」，此时分片序号不再增长，不能当成卡顿去恢复。
END_MARKS = ("谢谢观看",)
# 更可靠的结束信号：视频播完会弹「请点击左下角"考试"按钮参加课后测试…」。
END_HINT = "请点击左下角"
# 实测约 7 个 ts 分片/分钟（约 8.57 秒一片），用分片序号估算播放位置。
# 只按 --played 累加会因传值偏低而永远达不到结束门槛，必须用分片位置校正。
SECONDS_PER_SEGMENT = 8.57
# 交卷后的成绩页，出现这些字样说明该课件的学习与考试已闭环。
RESULT_MARKS = ("考试结果", "考试通过", "考试未通过")
LESSON_TITLES = (
    "阻塞性睡眠呼吸暂停的筛查及诊断",
    "阻塞性睡眠呼吸暂停疾病评估新指标",
    "阻塞性睡眠呼吸暂停药物治疗新进展",
)


def log(message, handle=None):
    line = "%s %s" % (datetime.now().strftime("%H:%M:%S"), message)
    print(line, flush=True)
    if handle:
        handle.write(line + "\n")
        handle.flush()


def adb(*args, timeout=60):
    return subprocess.run([ADB, "-s", DEVICE, *args], capture_output=True, timeout=timeout)


def logcat():
    return adb("logcat", "-d", "-t", "2000").stdout.decode("utf-8", "ignore")


def segment_index(playlist_id=""):
    """取最近一次 ts 分片序号；序号增长说明播放器仍在拉流。"""
    text = logcat()
    pattern = re.compile(r"_(\d+)\.ts", re.I)
    indexes = [int(item) for item in pattern.findall(text)]
    # 必须取最后一条而不是最大值：logcat 窗口里还留着上一个课件的分片号，
    # 取最大值会把「新课刚开始」误判成「已经快播完」。
    return indexes[-1] if indexes else -1


def duration_seconds():
    """读取当前课件总时长，只接受合理区间。

    优先用保利威播放器接口日志里的 duration=秒数，比 IJK 的 Duration 稳定。
    """
    text = logcat()
    polyv = [int(value) for value in re.findall(r"[?&]duration=(\d+)&", text)]
    polyv = [value for value in polyv if 60 <= value <= 4 * 3600]
    if polyv:
        return polyv[-1]
    # ffmpeg 把时长单独打在 Duration 的下一行，中间隔着 logcat 时间戳前缀。
    values = re.findall(r"Duration:[^\n]*\n[^\n]*?(\d{2}:\d{2}:\d{2})", text)
    if not values:
        values = re.findall(r"Duration: +(\d{2}:\d{2}:\d{2})", text)
    seconds = []
    for value in values:
        hours, minutes, secs = (int(part) for part in value.split(":"))
        total = hours * 3600 + minutes * 60 + secs
        # 单节课件 1 分钟～4 小时；排除整段播放列表或残留日志里的异常值。
        if 60 <= total <= 4 * 3600:
            seconds.append(total)
    return seconds[-1] if seconds else 0


def ui_xml():
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", timeout=90)
    return adb("shell", "cat", "/sdcard/ui.xml", timeout=90).stdout.decode("utf-8", "ignore")


def current_activity():
    text = adb("shell", "dumpsys window | grep mCurrentFocus").stdout.decode("utf-8", "ignore")
    match = re.search(r"com\.huayi\.cme/([\w.]+)", text)
    return match.group(1) if match else ""


def safe_name(text):
    """课程名里如果有 Windows 不允许的字符，替换成下划线。"""
    return re.sub(r'[\\/:*?"<>|]', "_", text).strip()


def screenshot(task_dir, title, stage, log_file):
    """截图存到任务目录，文件名固定为「课程名_阶段.png」。"""
    adb("shell", "screencap", "-p", "/sdcard/_shot.png", timeout=90)
    # adb pull 对中文目标路径会静默失败，先拉到系统临时目录（纯英文）再改名。
    temp = Path(tempfile.gettempdir()) / "_huayi_shot.png"
    adb("pull", "/sdcard/_shot.png", str(temp), timeout=90)
    target = task_dir / ("%s_%s.png" % (title, stage))
    shutil.move(str(temp), str(target))
    log("截图：%s" % target, log_file)
    return target


def node_bounds(xml, text):
    match = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(text), xml)
    if not match:
        return None
    left, top, right, bottom = (int(value) for value in match.groups())
    return (left + right) // 2, (top + bottom) // 2


def node_bounds_contains(xml, keyword):
    """按关键词找按钮，兼容“好的，知道了”这类带前缀的文案。"""
    match = re.search(r'text="([^"]*%s[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                      % re.escape(keyword), xml)
    if not match:
        return None
    left, top, right, bottom = (int(value) for value in match.groups()[1:])
    return (left + right) // 2, (top + bottom) // 2


def visible_texts(xml):
    return set(re.findall(r'text="([^"]+)"', xml))


def tap(x, y):
    adb("shell", "input", "tap", str(x), str(y))


def toggle_play():
    adb("shell", "input", "keyevent", "85")


def lesson_titles_in(xml):
    return [title for title in LESSON_TITLES if title in xml]


def try_exam(xml, log_file):
    """播放结束后自动点底部「考试」按钮，返回是否点到了。"""
    point = node_bounds(xml, "考试")
    if not point and "请点击左下角" in xml:
        # 结束时会弹「请点击左下角考试按钮」的提示框，它会盖住底部按钮，先关掉提示。
        hint = node_bounds(xml, "确定")
        if hint:
            tap(*hint)
            time.sleep(3)
            xml = ui_xml()
            point = node_bounds(xml, "考试")
    if not point:
        log("未找到「考试」按钮，稍后重试", log_file)
        return False
    tap(*point)
    log("自动打开课后测验", log_file)
    return True


def main():
    parser = argparse.ArgumentParser(description="掌上华医课件播放守护")
    parser.add_argument("--interval", type=int, default=60, help="检查间隔秒数")
    parser.add_argument("--max-hours", type=float, default=4.0, help="最长运行小时数")
    parser.add_argument("--duration", type=int, default=0, help="首个课件时长（秒），日志已滚出时使用")
    parser.add_argument("--played", type=int, default=0, help="首个课件已播（秒）")
    parser.add_argument("--lesson-index", type=int, default=0, help="课件序号，用于任务目录前缀")
    parser.add_argument("--lesson-name", default="", help="课程名，用于任务目录与截图文件名")
    parser.add_argument("--out-root", default=r"d:\trae_flybirds\app_page_captures\huayi_course\tasks",
                        help="任务目录根路径，每个课件建一个子目录")
    parser.add_argument("--next-name", default="", help="考完自动打开的下一课件标题，留空则考完即停")
    parser.add_argument("--next-index", type=int, default=0, help="下一课件序号")
    parser.add_argument("--log", default=r"d:\trae_flybirds\app_page_captures\huayi_course\guard.log")
    args = parser.parse_args()

    title = safe_name(args.lesson_name) or (
        LESSON_TITLES[args.lesson_index - 1] if 0 < args.lesson_index <= len(LESSON_TITLES) else "课件")
    dir_name = ("%02d_%s" % (args.lesson_index, title)) if args.lesson_index else title
    task_dir = Path(args.out_root) / dir_name
    task_dir.mkdir(parents=True, exist_ok=True)

    handle = Path(args.log)
    handle.parent.mkdir(parents=True, exist_ok=True)
    log_file = handle.open("a", encoding="utf-8")

    deadline = time.time() + args.max_hours * 3600
    detected = duration_seconds()
    duration = args.duration if args.duration >= 60 else detected
    if not 60 <= duration <= 4 * 3600:
        duration = 0
    played = args.played
    last_index = segment_index()
    estimate = int(max(last_index, 0) * SECONDS_PER_SEGMENT)
    if duration:
        estimate = min(estimate, duration)
    if estimate > played + 120:
        log("进度校正：--played=%d 秒低于分片位置 %d 秒，按分片估算" % (played, estimate), log_file)
        played = estimate
    stalled = 0
    mid_taken = (task_dir / ("%s_中间.png" % title)).exists()
    quiz_waiting = False
    quiz_since = 0
    exam_attempt = 0
    exam_taps = 0
    ended = False
    log("启动：课件=%s，时长=%d 秒，初始分片序号=%d，任务目录=%s"
        % (title, duration, last_index, task_dir), log_file)
    if not (task_dir / ("%s_开始.png" % title)).exists():
        screenshot(task_dir, title, "开始", log_file)
    if not duration:
        log("未取到课件时长，中间截图无法定位（可加 --duration 指定）", log_file)

    while time.time() < deadline:
        time.sleep(args.interval)
        xml = ui_xml()
        texts = visible_texts(xml)
        joined = "\n".join(texts)
        activity = current_activity()

        if any(mark in joined for mark in RESULT_MARKS):
            screenshot(task_dir, title, "考试结果", log_file)
            if not args.next_name:
                log("检测到考试成绩页，停止守护", log_file)
                break
            log("检测到考试成绩页，返回列表并打开下一课件：%s" % args.next_name, log_file)
            point = None
            for _ in range(3):
                adb("shell", "input", "keyevent", "4")
                time.sleep(4)
                list_xml = ui_xml()
                point = node_bounds(list_xml, args.next_name) or node_bounds_contains(list_xml, args.next_name)
                if point:
                    break
            if not point:
                log("未在列表中定位到下一课件，停止守护", log_file)
                break
            tap(*point)
            time.sleep(12)
            title = safe_name(args.next_name)
            dir_name = ("%02d_%s" % (args.next_index, title)) if args.next_index else title
            task_dir = Path(args.out_root) / dir_name
            task_dir.mkdir(parents=True, exist_ok=True)
            duration = duration_seconds()
            played, stalled, ended, quiz_waiting = 0, 0, False, False
            last_index = segment_index()
            mid_taken = (task_dir / ("%s_中间.png" % title)).exists()
            log("切换到下一课件：%s，时长=%d 秒，分片=%d" % (title, duration, last_index), log_file)
            if not (task_dir / ("%s_开始.png" % title)).exists():
                screenshot(task_dir, title, "开始", log_file)
            continue

        if quiz_waiting:
            # 测验期间只观察：不点选项、不点交卷，等回到播放器或出现成绩。
            if "MediaPlayNewActivity" in activity:
                log("已回到播放器，继续守护", log_file)
                quiz_waiting = False
                last_index = segment_index()
                continue
            if quiz_since and time.time() - quiz_since > 1800:
                log("测验页停留超过 30 分钟，停止守护", log_file)
                break
            continue

        # 被弹窗带回项目页时，自动重新进入当前课件，避免在项目页上空转。
        if not ended and "CourseDetailsActivity" in activity:
            point = node_bounds(xml, title) or node_bounds_contains(xml, title)
            if point:
                tap(*point)
                log("已离开播放器（项目页），重新进入课件：%s" % title, log_file)
                time.sleep(10)
                last_index = segment_index()
                continue

        if ("WebActivity" in activity or "TestQuestionsActivity" in activity
                or any(mark in joined for mark in QUIZ_MARKS)):
            screenshot(task_dir, title, "考试开始", log_file)
            log("检测到测验页（%s），停止点击并等待考试成绩" % (activity or "未知页面"), log_file)
            for line in texts:
                if len(line) > 12:
                    log("  试题内容：%s" % line[:120], log_file)
            quiz_waiting = True
            quiz_since = time.time()
            continue

        popup = next((word for word in POPUP_WORDS if word in joined), "")
        if popup:
            point = node_bounds_contains(xml, popup)
            if point:
                tap(*point)
                log("处理弹窗：%s" % popup, log_file)
                time.sleep(3)
                continue

        if not ended and any(mark in joined for mark in END_MARKS):
            screenshot(task_dir, title, "结束", log_file)
            log("检测到播放结束（谢谢观看），等待课后测验", log_file)
            ended = True

        # 「请点击左下角考试」只在当前视频播完时出现，比等分片停滞可靠。
        if not ended and END_HINT in joined and "MediaPlayNewActivity" in activity:
            screenshot(task_dir, title, "结束", log_file)
            log("检测到结束提示（请点击左下角考试），按播放完成处理", log_file)
            played = duration or played
            ended = True

        current = segment_index()
        if current < last_index - 10:
            # 换课件后分片序号会从头开始，重置基线，避免被误判成停滞。
            log("分片序号回落（%d → %d），按新课重置基线" % (last_index, current), log_file)
            last_index = current
            played = int(max(current, 0) * SECONDS_PER_SEGMENT)
            stalled = 0
        elif current > last_index:
            # 用分片序号反推播放位置，避免 --played 传错后一直停在低进度。
            estimate = int(current * SECONDS_PER_SEGMENT)
            played = min(duration, estimate) if duration else estimate
            last_index = current
            stalled = 0
        else:
            stalled += 1

        if not ended and duration and not mid_taken and played >= duration // 2:
            screenshot(task_dir, title, "中间", log_file)
            mid_taken = True

        if stalled >= 2 and not ended:
            log("连续 %d 次无新分片，尝试恢复播放" % stalled, log_file)
            # 126 = MEDIA_PLAY：只会恢复播放，不会把正在播的课件按暂停。
            adb("shell", "input", "keyevent", "126")
            time.sleep(2)
            if segment_index() <= last_index:
                # 播放键无效时再点一次播放器画面，触发缓冲重连。
                tap(450, 350)
            time.sleep(3)
            last_index = segment_index()
            if stalled >= 10:
                log("警告：已卡顿约 %d 分钟，需要人工查看" % stalled, log_file)

        # 片尾经常没有「谢谢观看」，分片连续 5 分钟不动就按播放结束处理。
        # 但只有进度过了 85% 才认作结束，否则先判为卡顿，继续尝试恢复播放。
        if stalled >= 5 and not ended:
            if duration and played < duration * 0.85:
                log("分片停滞但进度仅 %d/%d 秒，按卡顿处理，继续恢复播放" % (played, duration), log_file)
                stalled = 0
                adb("shell", "input", "keyevent", "126")
                time.sleep(5)
                last_index = segment_index()
                continue
            screenshot(task_dir, title, "结束", log_file)
            log("分片 5 分钟无变化，按播放结束处理", log_file)
            ended = True

        # 播放结束后自动点「考试」进入课后测验；最多尝试 5 次，间隔 90 秒。
        if (ended and not quiz_waiting and "MediaPlayNewActivity" in activity
                and exam_taps < 5 and time.time() - exam_attempt > 90):
            exam_attempt = time.time()
            if try_exam(xml, log_file):
                exam_taps += 1
                time.sleep(5)
                continue

        log("进度：已播 %d/%d 秒，分片=%d，停滞=%d，已结束=%s"
            % (played, duration, current, stalled, ended), log_file)

    log_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
