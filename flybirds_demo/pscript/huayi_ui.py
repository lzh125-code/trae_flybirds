# -*- coding: utf-8 -*-
"""导出掌上华医当前界面的文本与坐标，便于定位点击位置。"""
import os
import re
import subprocess
import sys

ADB = r"E:\leidian\LDPlayer14\adb.exe"
DEVICE = os.environ.get("HUAYI_DEVICE", "127.0.0.1:5555")


def main():
    subprocess.run([ADB, "-s", DEVICE, "shell", "uiautomator", "dump", "/sdcard/ui.xml"],
                   capture_output=True, timeout=90)
    text = subprocess.run([ADB, "-s", DEVICE, "shell", "cat", "/sdcard/ui.xml"],
                          capture_output=True, timeout=90).stdout.decode("utf-8", "ignore")
    pattern = re.compile(r'text="([^"]+)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    for match in pattern.finditer(text):
        label = match.group(1)
        left, top, right, bottom = (int(value) for value in match.groups()[1:])
        print("%4d,%4d  %s" % ((left + right) // 2, (top + bottom) // 2, label))
    if "--state" in sys.argv:
        for node in re.findall(r"<node [^>]*>", text):
            if 'checked="true"' in node or 'selected="true"' in node:
                print("选中：%s" % node[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
