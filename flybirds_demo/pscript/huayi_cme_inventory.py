# -*- coding: utf-8 -*-
"""盘点掌上华医 CME 选课列表里的项目进度，输出 CSV。

只读：进入项目页读「学习进度 x/N」和每个课件状态，不播放、不答题、不选课。
起点必须是课程列表页（顶部有「请输入项目名称」）。
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time

ADB = r"E:\leidian\LDPlayer14\adb.exe"
DEVICE = os.environ.get("HUAYI_DEVICE", "127.0.0.1:5555")
STATUS_WORDS = ("未学习", "待考试", "已完成", "学习中")
SKIP_TITLES = ("国家级", "市级", "项目编号", "本项目", "课程学习与考试", "帮助")


def adb(*args, timeout=90):
    return subprocess.run([ADB, "-s", DEVICE, *args], capture_output=True, timeout=timeout)


def dump():
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    return adb("shell", "cat", "/sdcard/ui.xml").stdout.decode("utf-8", "ignore")


def nodes(xml):
    pattern = re.compile(r'text="([^"]+)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    result = []
    for match in pattern.finditer(xml):
        label = match.group(1)
        left, top, right, bottom = (int(value) for value in match.groups()[1:])
        result.append(((left + right) // 2, (top + bottom) // 2, label))
    return result


def tap(x, y):
    adb("shell", "input", "tap", str(x), str(y))


def swipe(y1, y2, duration=400):
    adb("shell", "input", "swipe", "450", str(y1), "450", str(y2), str(duration))


def back():
    adb("shell", "input", "keyevent", "4")


def credit_cards(xml):
    """列表页：每个项目卡片有一个「国家级 x 学分」节点，用它做锚点。"""
    cards = []
    for cx, cy, label in nodes(xml):
        if ("学分" in label and ("国家级" in label or "市级" in label)) and cx < 700:
            cards.append((cy, label))
    return sorted(cards)


def find_title(items, credit_y):
    """卡片标题在学分行上方约 40px。"""
    best = None
    for cx, cy, label in items:
        if not (credit_y - 70 <= cy <= credit_y - 15):
            continue
        if len(label) < 6 or any(word in label for word in SKIP_TITLES):
            continue
        if best is None or cy > best[1]:
            best = (cx, cy, label)
    return best


def read_detail():
    """读项目详情：进度 + 每个课件状态，最多滚 3 屏。"""
    progress = "0/0"
    number = ""
    status_by_title = {}
    for _ in range(3):
        xml = dump()
        items = nodes(xml)
        match = re.search(r"学习进度：(\d+)/(\d+)", xml)
        if match:
            progress = "%s/%s" % match.groups()
        match = re.search(r"项目编号：([\w\-()（）]+)", xml)
        if match:
            number = match.group(1)
        titles = [(cx, cy, label) for cx, cy, label in items
                  if 250 < cx < 700 and len(label) > 6 and not label.startswith(SKIP_TITLES)
                  and not re.match(r"^\d+\.$", label)]
        for cx, cy, label in items:
            if not (label in STATUS_WORDS or label.startswith("播放至")):
                continue
            best = None
            for tcx, tcy, tlabel in titles:
                if abs(tcy - (cy - 39)) <= 25 or abs(tcy - cy) <= 12:
                    if best is None or abs(tcy - cy) < abs(best[1] - cy):
                        best = (tcx, tcy, tlabel)
            if best:
                status_by_title[best[2]] = label
        swipe(1400, 700)
        time.sleep(1)
    return progress, number, status_by_title


def main():
    parser = argparse.ArgumentParser(description="盘点 CME 选课项目进度")
    parser.add_argument("--out", default=r"d:\trae_flybirds\app_page_captures\huayi_course\inventory.csv")
    parser.add_argument("--screens", type=int, default=12, help="列表最多滚多少屏")
    args = parser.parse_args()

    xml = dump()
    if "请输入项目名称" not in xml:
        print("当前不在课程列表页，先手动回到列表页再跑")
        return 1

    seen = set()
    rows = []
    for screen in range(args.screens):
        xml = dump()
        cards = credit_cards(xml)
        items = nodes(xml)
        new_count = 0
        for credit_y, credit_label in cards:
            title = find_title(items, credit_y)
            if not title:
                continue
            tx, ty, name = title
            if name in seen:
                continue
            seen.add(name)
            tap(tx, ty)
            time.sleep(3)
            progress, number, statuses = read_detail()
            back()
            time.sleep(2)
            counts = {}
            for value in statuses.values():
                key = "播放中" if value.startswith("播放至") else value
                counts[key] = counts.get(key, 0) + 1
            done, total = (progress.split("/") + ["0"])[:2]
            rows.append({
                "项目名": name,
                "项目编号": number,
                "学分": credit_label,
                "学习进度": progress,
                "课件总数": total,
                "已完成": counts.get("已完成", 0),
                "待考试": counts.get("待考试", 0),
                "播放中": counts.get("播放中", 0),
                "未学习": counts.get("未学习", 0),
            })
            print("%s  %s  已完成%s 待考试%s 未学习%s" % (name, progress, rows[-1]["已完成"],
                                                    rows[-1]["待考试"], rows[-1]["未学习"]), flush=True)
            new_count += 1
        swipe(1500, 600)
        time.sleep(2)
        if new_count == 0 and screen > 0:
            break

    handle = open(args.out, "w", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["项目名"])
    writer.writeheader()
    writer.writerows(rows)
    handle.close()
    print("共 %d 个项目，已写入 %s" % (len(rows), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
