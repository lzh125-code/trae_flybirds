# -*- coding: utf-8 -*-
"""策略列表（推广费用排序）自定义步骤。

注：Flybirds 内置步骤先注册，为避免被 `点击[{selector}]` 等通配步骤抢先匹配，
此处自定义步骤均不以 `点击`、`存在`、`元素` 等内置前缀开头。
"""
import copy
import json
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlsplit

import flybirds.core.global_resource as gr
from behave import step

PROMOTION_COLUMN = "推广费用/利润分配($)"
PROMOTION_FIELD_CANDIDATES = (
    "netPromotionFeeYield", "promotionFeeYield", "promotion_fee_yield",
    "promotionFee", "promotionFeeAmount",
)
CRM_ID_CANDIDATES = ("crmId", "crm_id", "crmID", "crm_id_")


def _page():
    page_obj = gr.get_value("plugin_page")
    if page_obj is None or not hasattr(page_obj, "page"):
        raise AssertionError("未获取到 Web 页面对象 plugin_page")
    return page_obj.page


def _rows(page):
    return page.locator(".ivu-table-body tr.ivu-table-row")


def _header(page, column):
    return page.locator(".ivu-table-header th").filter(has_text=column).first


def _wait_table(page):
    page.locator(".ivu-table").first.wait_for(state="visible")
    loading = page.locator(".ivu-table-loading")
    if loading.count() > 0:
        loading.wait_for(state="hidden")
    page.wait_for_timeout(500)


def _row_keys(page):
    return [row.locator("td").first.inner_text().strip() for row in _rows(page).all()]


def _column_texts(page, column):
    header = _header(page, column)
    header.wait_for(state="attached")
    index = header.evaluate("th => Array.from(th.parentElement.children).indexOf(th)")
    return [row.locator("td").nth(index).inner_text().strip() for row in _rows(page).all()]


def _decimal(value):
    text = str(value).strip().replace(",", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    text = re.sub(r"[^0-9eE+\-.]", "", text)
    if not text:
        raise InvalidOperation("空数值")
    return Decimal(text)


def _numbers(page, column):
    values = []
    for value in _column_texts(page, column):
        if value in ("-", "--", ""):
            continue
        values.append(_decimal(value))
    assert values, "策略列表没有可解析的数值，无法校验排序"
    return values


def _datetimes(page, column):
    values = []
    for value in _column_texts(page, column):
        if value in ("-", "--", ""):
            continue
        text = value.replace("/", "-")
        try:
            values.append(datetime.fromisoformat(text))
        except ValueError:
            values.append(datetime.strptime(value, "%d/%m/%Y %H:%M:%S"))
    assert values, "策略列表没有可解析的时间，无法校验顺序"
    return values


def _find_records(node):
    """在响应 JSON 中定位策略记录列表，返回 (父节点, 列表字段名, 列表)。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                if any(_has_record_fields(item) for item in value):
                    return node, key, value
            found = _find_records(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_records(item)
            if found:
                return found
    return None


def _has_record_fields(item):
    if not isinstance(item, dict):
        return False
    return any(key in item for key in CRM_ID_CANDIDATES) or any(
        key in item
        for key in (
            "strategyName", "strategy_name",
            "providerId", "providerName", "provideId", "provideName",
            "netPromotionFeeYield",
        )
    )


def _record_id(record):
    for key in CRM_ID_CANDIDATES:
        if key in record and record[key] is not None:
            return str(record[key]).lstrip("0")
    return None


def _record_fee(record):
    for key in PROMOTION_FIELD_CANDIDATES:
        if key in record and record[key] is not None:
            return _decimal(record[key])
    return None


def _latest_response(context):
    payload = getattr(context, "_strategy_latest_payload", None)
    url = getattr(context, "_strategy_latest_url", None)
    assert payload is not None and url is not None, "未捕获策略列表接口，请先确认接口响应包含 CRM-ID 或策略名称字段"
    return payload, url


_MOCK_HANDLERS = []


def _is_list_request(route_url):
    # 只拦截数据列表接口，放行 /page/count，避免分页总数被一并篡改
    return "provideList/page?" in route_url


def _register_mock(page, handler):
    page.route(_is_list_request, handler)
    _MOCK_HANDLERS.append((page, handler))


def _clear_mocks(page):
    """清理历史场景遗留的路由 Mock，避免 context 复用时接口被一直拦截。"""
    for item_page, handler in list(_MOCK_HANDLERS):
        if item_page is page:
            try:
                page.unroute(_is_list_request, handler)
            except Exception:
                pass
            _MOCK_HANDLERS.remove((item_page, handler))


def _mock_list_once(context, mode):
    payload, url = _latest_response(context)
    body = copy.deepcopy(payload)
    page = _page()
    _clear_mocks(page)

    if mode == "timeout":
        _register_mock(page, lambda route: route.abort("timedout"))
        return
    if mode == "500":
        _register_mock(
            page,
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"success": False, "message": "Mock 500"}),
            ),
        )
        return

    parent, _, records = _find_records(body)
    records[:] = records[:1] if mode == "single" else []
    for key in ("total", "totalCount", "total_count"):
        if key in parent:
            parent[key] = len(records)
    _register_mock(
        page,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body, ensure_ascii=False),
        ),
    )


def _request_params(request):
    params = {key: values[-1] for key, values in parse_qs(urlsplit(request.url).query).items()}
    post_data = request.post_data
    if post_data:
        try:
            data = json.loads(post_data)
            if isinstance(data, dict):
                params.update(data)
        except (json.JSONDecodeError, TypeError):
            params.update({key: values[-1] for key, values in parse_qs(post_data).items()})
    return params


STRATEGY_URL = "https://demo-console.crmtest.org/social/strategy/"
LOGIN_URL = "https://demo-console.crmtest.org/login"
CRM_EMAIL = os.environ.get("CRM_EMAIL", "forestlin@pmonic.xyz")
CRM_PASSWORD = os.environ.get("CRM_PASSWORD", "Aa@135246")
_REGISTERED_PAGES = []


def _register_listeners(context, page):
    """同一页面只注册一次事件监听，避免跨场景重复叠加。"""
    if any(item is page for item in _REGISTERED_PAGES):
        return
    _REGISTERED_PAGES.append(page)

    def on_request(request):
        if request.resource_type in ("xhr", "fetch"):
            context._strategy_requests.append(request)

    def on_response(response):
        if response.request.resource_type not in ("xhr", "fetch"):
            return
        try:
            payload = response.json()
        except Exception:
            return
        if _find_records(payload):
            context._strategy_latest_payload = payload
            context._strategy_latest_url = response.url

    page.on("request", on_request)
    page.on("response", on_response)


def _is_login_page(page):
    return "/login" in page.url or page.locator("input[type='password']").count() > 0


def _login(page):
    if "/login" not in page.url:
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.locator("input[placeholder*='邮箱']").fill(CRM_EMAIL)
    page.locator("input[type='password']").fill(CRM_PASSWORD)
    page.locator("text=登录").first.click()
    page.wait_for_timeout(3000)


def _open_strategy_list(page):
    page.goto(STRATEGY_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    if _is_login_page(page):
        _login(page)
        page.goto(STRATEGY_URL, wait_until="domcontentloaded")
    page.locator(".ivu-table").first.wait_for(state="visible", timeout=30000)
    _wait_table(page)


@step("确保已登录并进入策略列表")
def ensure_logged_in_strategy_list(context):
    """登录一次后复用会话：已在策略列表页则直接复用，否则按需登录并跳转。"""
    page = _page()
    context._strategy_requests = []
    context._strategy_latest_payload = None
    context._strategy_latest_url = None
    _register_listeners(context, page)
    _clear_mocks(page)

    if "/social/strategy" in page.url:
        rows = _rows(page)
        if rows.count() > 0 or page.locator(".ivu-table-tip").count() > 0:
            _wait_table(page)
            return
    _open_strategy_list(page)


@step("开始监听策略列表请求")
def start_strategy_list_listener(context):
    page = _page()
    context._strategy_requests = []
    context._strategy_latest_payload = None
    context._strategy_latest_url = None
    _register_listeners(context, page)


@step("等待策略列表加载完成")
def wait_strategy_list(context):
    _wait_table(_page())


def _click_arrow(page, column, arrow):
    """点击排序列箭头，并等待列表接口响应，避免读到上一次的旧数据。"""
    try:
        with page.expect_response(
            lambda response: _is_list_request(response.url)
            and response.request.resource_type in ("xhr", "fetch"),
            timeout=10000,
        ):
            _header(page, column).locator(".ivu-table-sort .%s" % arrow).first.click()
    except Exception:
        pass
    _wait_table(page)


@step("对[{column}]列头进行排序")
def click_sort_column(context, column):
    page = _page()
    context._strategy_requests = []
    try:
        states = dict(context._strategy_sort_state)
    except KeyError:
        states = {}
    state = states.get(column, "default")
    # 该页面通过点击上/下箭头触发排序，且无“取消排序”入口：
    # 默认 -> 升序(上箭头)，升序 -> 降序(下箭头)，降序 -> 再次升序(上箭头)
    arrow, next_state = {
        "default": ("ivu-icon-md-arrow-dropup", "升序"),
        "升序": ("ivu-icon-md-arrow-dropdown", "降序"),
        "降序": ("ivu-icon-md-arrow-dropup", "升序"),
    }[state]
    states[column] = next_state
    context._strategy_sort_state = states
    _click_arrow(page, column, arrow)


@step("确保[{column}]列处于[{direction}]排序状态")
def ensure_column_sort_state(context, column, direction):
    """显式构造前置排序状态：先重置到默认，再按方向点击对应箭头。"""
    assert direction in ("默认", "升序", "降序"), "不支持的排序状态：%s" % direction
    page = _page()
    click_strategy_reset(context)
    context._strategy_sort_state = {}
    if direction == "默认":
        return
    _click_arrow(page, column, "ivu-icon-md-arrow-dropup")
    if direction == "降序":
        _click_arrow(page, column, "ivu-icon-md-arrow-dropdown")
    context._strategy_sort_state = {column: direction}


@step("快速对[{column}]列头排序[{times}]次")
def rapid_click_sort_column(context, column, times):
    page = _page()
    context._strategy_requests = []
    _header(page, column).locator(".ivu-table-cell").evaluate(
        "(cell, count) => { for (let i = 0; i < count; i++) cell.click(); }", int(times)
    )
    page.wait_for_timeout(2500)
    _wait_table(page)


@step("策略列表应按[{column}]列[{direction}]排列")
def verify_column_sort(context, column, direction):
    assert direction in ("升序", "降序"), "不支持的排序方向：%s" % direction
    values = _numbers(_page(), column)
    expected = sorted(values, reverse=direction == "降序")
    assert values == expected, "%s列不是%s排列：%s" % (column, direction, values)


@step("排序列[{column}]排序图标应为[{direction}]")
def verify_sort_icon(context, column, direction):
    header = _header(_page(), column)
    if direction == "默认":
        assert header.locator(".ivu-table-sort i.on").count() == 0, "%s列仍存在高亮排序图标" % column
        return
    icon = "dropup" if direction == "升序" else "dropdown"
    assert header.locator(".ivu-icon-md-arrow-%s.on" % icon).count() == 1, (
        "%s列排序图标不是%s" % (column, direction)
    )


@step("所有列头均无排序图标高亮")
def verify_no_sort_icons(context):
    active = _page().locator(".ivu-table-header .ivu-table-sort i.on")
    assert active.count() == 0, "仍有%s个排序图标处于高亮状态" % active.count()


@step("策略列表应按创建时间逆序排列")
def verify_default_time_sort(context):
    values = _datetimes(_page(), "创建时间")
    assert values == sorted(values, reverse=True), "策略列表未按创建时间逆序排列：%s" % values


@step("记录策略列表当前顺序")
def remember_strategy_order(context):
    context._strategy_initial_order = _row_keys(_page())
    assert context._strategy_initial_order, "策略列表没有可记录的数据"


@step("策略列表顺序应与已记录顺序一致")
def verify_remembered_strategy_order(context):
    expected = getattr(context, "_strategy_initial_order", None)
    assert expected is not None, "尚未记录策略列表初始顺序"
    actual = _row_keys(_page())
    assert actual == expected, "恢复默认后的顺序不一致，预期%s，实际%s" % (expected, actual)


@step("策略列表中推广费用相同的记录应按创建时间逆序排列")
def verify_equal_promotion_time_sort(context):
    page = _page()
    fees = _numbers(page, PROMOTION_COLUMN)
    times = _datetimes(page, "创建时间")
    assert len(fees) == len(times), "推广费用与创建时间列数据行数不一致"
    equal_groups = 0
    for index in range(len(fees) - 1):
        if fees[index] == fees[index + 1]:
            equal_groups += 1
            assert times[index] >= times[index + 1], "相同推广费用的记录未按创建时间逆序排列"
    if equal_groups == 0:
        print("提示：当前页没有相同推广费用的记录，未实际校验次级时间排序（需准备对应数据）")


@step("重置策略列表排序")
def click_strategy_reset(context):
    page = _page()
    context._strategy_requests = []
    page.get_by_role("button", name="重置", exact=True).click()
    _wait_table(page)


@step("翻到策略列表下一页")
def click_strategy_next_page(context):
    page = _page()
    context._strategy_requests = []
    page.locator(".ivu-page-next").click()
    _wait_table(page)


@step("策略列表当前页码应为[{page_number}]")
def verify_strategy_page_number(context, page_number):
    active = _page().locator(".ivu-page-item-active")
    assert active.get_attribute("title") == str(page_number), "当前页码不是%s" % page_number


@step("刷新策略列表页面")
def refresh_strategy_list(context):
    page = _page()
    context._strategy_requests = []
    page.reload()
    _wait_table(page)


@step("策略列表排序请求参数应为[{expected}]")
def verify_sort_request_params(context, expected):
    expected_params = dict(item.split("=", 1) for item in expected.split("&"))
    requests = getattr(context, "_strategy_requests", [])
    for request in reversed(requests):
        params = _request_params(request)
        if all(str(params.get(key)) == value for key, value in expected_params.items()):
            return
    raise AssertionError("未找到排序参数%s，请确认列表接口请求参数格式" % expected)


@step("策略列表请求不应包含排序参数")
def verify_no_sort_request_params(context):
    for request in getattr(context, "_strategy_requests", []):
        params = _request_params(request)
        assert "orderField" not in params and "orderType" not in params, (
            "请求仍包含排序参数：%s" % request.url
        )


@step("策略列表推广费用数据应包含负数、零值和正数")
def verify_negative_zero_positive_data(context):
    values = _numbers(_page(), PROMOTION_COLUMN)
    assert any(value < 0 for value in values), "当前页缺少负数推广费用"
    assert any(value == 0 for value in values), "当前页缺少零值推广费用"
    assert any(value > 0 for value in values), "当前页缺少正数推广费用"


@step("策略列表推广费用数据应包含千万或亿级数值")
def verify_large_promotion_data(context):
    values = _numbers(_page(), PROMOTION_COLUMN)
    assert any(abs(value) >= Decimal("10000000") for value in values), "当前页缺少千万或亿级推广费用"


@step("策略列表推广费用应与最新接口返回一致")
def verify_promotion_matches_latest_response(context):
    payload, _ = _latest_response(context)
    _, _, records = _find_records(payload)
    by_id = {}
    for record in records:
        record_id = _record_id(record)
        fee = _record_fee(record)
        if record_id is not None and fee is not None:
            by_id[record_id] = fee
    assert by_id, "最新接口返回中未找到 CRM-ID 与推广费用字段，请确认接口字段名"
    page = _page()
    ids = [_record_id({"crmId": value}) for value in _row_keys(page)]
    fees = _numbers(page, PROMOTION_COLUMN)
    assert len(ids) == len(fees), "CRM-ID 与推广费用列数据行数不一致"
    for record_id, fee in zip(ids, fees):
        assert record_id in by_id, "最新接口返回中找不到 CRM-ID：%s" % record_id
        assert fee == by_id[record_id], "CRM-ID %s 的推广费用不是最新接口值" % record_id


@step("准备仅有一条策略列表数据")
def mock_single_strategy(context):
    _mock_list_once(context, "single")


@step("准备空策略列表数据")
def mock_empty_strategy(context):
    _mock_list_once(context, "empty")


@step("模拟策略列表请求超时")
def mock_strategy_timeout(context):
    _mock_list_once(context, "timeout")


@step("模拟策略列表请求返回500")
def mock_strategy_server_error(context):
    _mock_list_once(context, "500")


@step("策略列表应只有[{count}]条数据")
def verify_strategy_row_count(context, count):
    actual = _rows(_page()).count()
    assert actual == int(count), "策略列表预期%s条数据，实际%s条" % (count, actual)


@step("策略列表应显示空数据")
def verify_empty_strategy_list(context):
    page = _page()
    assert _rows(page).count() == 0, "策略列表仍存在数据行"
    if page.locator(".ivu-table-tip").count() == 0:
        body = page.locator("body").inner_text()
        assert "暂无" in body or "无数据" in body or "No Data" in body, "策略列表未显示空状态"


@step("策略列表正常展示无异常")
def verify_strategy_normal(context):
    page = _page()
    page.locator(".ivu-table").first.wait_for(state="visible")
    assert _rows(page).count() > 0, "策略列表没有数据"
    assert page.locator(".ivu-table-loading").count() == 0, "策略列表仍处于加载中"


@step("使用无权限账号重新登录")
def login_without_strategy_permission(context):
    email = os.environ.get("CRM_NO_PERMISSION_EMAIL")
    password = os.environ.get("CRM_NO_PERMISSION_PASSWORD")
    assert email and password, "请配置 CRM_NO_PERMISSION_EMAIL 和 CRM_NO_PERMISSION_PASSWORD 环境变量"
    page = _page()
    page.context.clear_cookies()
    page.goto("https://demo-console.crmtest.org/login")
    page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    page.reload()
    page.locator("input[placeholder*='邮箱']").fill(email)
    page.locator("input[type='password']").fill(password)
    page.get_by_text("登录", exact=True).click()
    page.wait_for_timeout(3000)


@step("页面应提示无权限且看不到策略列表")
def verify_strategy_permission_denied(context):
    page = _page()
    page.wait_for_timeout(1000)
    assert page.locator(".ivu-table").count() == 0, "无权限账号仍能看到策略列表"
    body_text = page.locator("body").inner_text()
    denied = any(text in body_text for text in ("无权限", "403", "Forbidden", "无权访问")) or any(
        text in page.url.lower() for text in ("no-auth", "no_permission", "noauth", "403")
    ) or "/login" in page.url
    assert denied, "页面未提示无权限，当前地址：%s" % page.url
