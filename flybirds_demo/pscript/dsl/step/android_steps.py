# -*- coding: utf-8 -*-
"""
Android 端自定义步骤

1) 雷电模拟器（Android 14 精简镜像）没有 monkey 命令，Flybirds 内置的
   「启动APP[包名]」会报 `monkey: inaccessible or not found`；
   airtest 的 start_app(package, activity) 又会重复拼包名，
   所以这里直接用 am start 指定包名/Activity。

2) App 是 Flutter 实现，文案落在无障碍 content-desc 上，且常带无障碍后缀
   （如「我的\\n第 5 个标签，共 5 个」）。poco 的 `name=` 是精确匹配用不了，
   而 `uiautomator dump` 会和 poco 的 UiAutomation 服务冲突（already registered），
   所以这里直接读 poco 的控件树 dump，按「包含」匹配文案后点击。
"""
import time

import flybirds.core.global_resource as gr
from behave import step
from airtest.core.helper import G


def _poco():
    poco = gr.get_value("pocoInstance")
    if poco is None:
        raise AssertionError("未获取到 poco 实例，请确认用例以 android 平台运行")
    return poco


def _walk(node):
    yield node
    for child in node.get("children") or ():
        yield from _walk(child)


def _find(keyword):
    """在控件树里按 name/desc/text 的包含匹配查找节点，返回命中节点中面积最小的 payload。

    Flutter 的语义树会给容器合并整页文案，包含匹配可能先命中一个覆盖全屏的父节点，
    点它的中心会点错位置，所以取面积最小的那个（即真正的行/按钮）。
    """
    best = None
    best_area = None
    for node in _walk(_poco().dump()):
        payload = node.get("payload") or {}
        if not any(keyword in (payload.get(key) or "") for key in ("name", "desc", "text")):
            continue
        size = payload.get("size") or [1, 1]
        area = float(size[0]) * float(size[1])
        if best_area is None or area < best_area:
            best, best_area = payload, area
    return best


def _find_edit():
    """当前页面的第一个输入框（Flutter 输入框在无障碍里是 EditText）。"""
    for node in _walk(_poco().dump()):
        payload = node.get("payload") or {}
        if payload.get("type") == "android.widget.EditText":
            return payload
    return None


@step("启动应用[{package}][{activity}]")
def start_app_with_activity(context, package, activity):
    G.DEVICE.shell("am start -n %s/%s" % (package, activity))


@step("清除应用数据[{package}]")
def clear_app_data(context, package):
    """登录态会缓存在 App 内，重复执行登录用例前先清空数据。"""
    G.DEVICE.shell("pm clear %s" % package)


@step("按文案点击[{keyword}]")
def tap_by_text(context, keyword):
    payload = _find(keyword)
    if payload is None:
        raise AssertionError("当前页面找不到包含「%s」的元素" % keyword)
    _poco().click(payload["pos"])
    time.sleep(1)


@step("清空输入框")
def clear_input(context):
    edit = _find_edit()
    if edit is None:
        raise AssertionError("当前页面没有可输入的文本框")
    _poco().click(edit["pos"])
    G.DEVICE.shell("input keyevent KEYCODE_MOVE_END")
    for _ in range(50):
        G.DEVICE.shell("input keyevent KEYCODE_DEL")


@step("在输入框输入[{value}]")
def input_in_edit(context, value):
    edit = _find_edit()
    if edit is None:
        raise AssertionError("当前页面没有可输入的文本框")
    _poco().click(edit["pos"])
    G.DEVICE.shell('input text "%s"' % value)
    time.sleep(1)


@step("页面应包含文案[{keyword}]")
def assert_page_contains(context, keyword):
    if _find(keyword) is None:
        raise AssertionError("当前页面未找到包含「%s」的文案" % keyword)


@step("页面不应包含文案[{keyword}]")
def assert_page_not_contains(context, keyword):
    if _find(keyword) is not None:
        raise AssertionError("当前页面仍存在包含「%s」的文案" % keyword)
