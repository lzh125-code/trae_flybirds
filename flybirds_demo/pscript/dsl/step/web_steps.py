# -*- coding: utf-8 -*-
"""Web 端自定义步骤：整页文本级断言。

后台客户详情页的字段 DOM 结构尚未确认（demo 环境当前不可用），
先用整页文本断言，避免依赖具体层级；环境恢复后可再收紧为字段级选择器。
"""
import flybirds.core.global_resource as gr
from behave import step


def _page():
    page_obj = gr.get_value("plugin_page")
    if page_obj is None or not hasattr(page_obj, "page"):
        raise AssertionError("未获取到 Web 页面对象 plugin_page")
    return page_obj.page


def _body_text():
    return _page().locator("body").inner_text()


@step("后台打开页面[{url}]")
def navigate_backend_page(context, url):
    """用 DOMContentLoaded 导航，避免静态资源加载缓慢导致整页 load 超时。"""
    for attempt in range(2):
        try:
            _page().goto(url, wait_until="domcontentloaded", timeout=60000)
            return
        except Exception:
            if attempt:
                raise
            _page().wait_for_timeout(3000)


@step("后台搜索手机号[{phone}]并打开详情")
def open_customer_by_phone(context, phone):
    page = _page()
    selectors = "input[placeholder*='手机'], input[placeholder*='搜索'], input[placeholder*='UID']"
    field = page.locator(selectors).locator("visible=true").first
    field.fill(phone, timeout=30000)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    row = page.locator(".ivu-table-body tr.ivu-table-row").filter(has_text=phone).first
    row.click(timeout=30000)
    page.wait_for_timeout(4000)


@step("页面文本应包含[{keyword}]")
def assert_text_contains(context, keyword):
    if keyword not in _body_text():
        raise AssertionError("页面文本中未找到「%s」" % keyword)


@step("页面文本不应包含[{keyword}]")
def assert_text_not_contains(context, keyword):
    if keyword in _body_text():
        raise AssertionError("页面文本中仍存在「%s」" % keyword)


@step("详情字段[{label}]应显示[{value}]")
def assert_field_value(context, label, value):
    """在整页文本里定位字段标签，检查其后一段文本中是否出现期望值。

    后台详情页常见结构是「标签 值」平铺或标签后紧跟兄弟节点，
    取标签之后 300 个字符做包含判断，不绑定具体 DOM。
    """
    text = _body_text()
    index = text.find(label)
    if index < 0:
        raise AssertionError("页面中未找到字段「%s」" % label)
    segment = text[index:index + 300]
    if value not in segment:
        raise AssertionError(
            "字段「%s」附近未显示期望值「%s」，实际片段：%r" % (label, value, segment[:80]))
