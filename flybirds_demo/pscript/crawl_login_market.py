# -*- coding: utf-8 -*-
"""限定范围采集：登录、账号设置、行情入口及 MT4/MT5 各一个代表品种详情。"""
import csv
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

from airtest.core.api import connect_device, snapshot
from poco.drivers.android.uiautomation import AndroidUiautomationPoco

DEVICE_ID = "emulator-5554"
PACKAGE = "com.wetrade.crm.trial"
ACTIVITY = "com.wetrade.crm.MainActivity"
ACCOUNT = "potatolin@foxmail.com"
PASSWORD = "aa111111"

RUN_ROOT = Path("D:/trae_flybirds/app_page_captures/potatolin") / datetime.now().strftime("%Y%m%d_%H%M%S")
SCREENSHOTS = RUN_ROOT / "screenshots"
ERRORS = RUN_ROOT / "errors"
MANIFEST = RUN_ROOT / "manifest.csv"
FIELDS = ("screenshot", "navigation_path", "source", "action", "status", "fingerprint", "error")
SEARCH_POS = [0.943333, 0.039375]
EYE_POS = [0.053333, 0.07125]
LIST_POS = [0.109444, 0.07125]
EDIT_POS = [0.186667, 0.07125]
BACK_POS = [0.033333, 0.05]
SHEET_CLOSE_POS = [0.955, 0.215]
AGREEMENT_POS = [0.835, 0.642]
PRIVACY_POS = [0.22, 0.67]

coverage = {}
sequences = {}

device = connect_device("Android:///" + DEVICE_ID)
device.shell("settings put system accelerometer_rotation 0")
device.shell("wm user-rotation lock 0")
device.shell("wm size 900x1600")
time.sleep(1)
poco = AndroidUiautomationPoco(device=device, use_airtest_input=True)


def walk(node):
    if not isinstance(node, dict):
        return
    payload = node.get("payload") or {}
    if payload:
        yield payload
    for child in node.get("children") or []:
        yield from walk(child)


def tree():
    return poco.dump()


def nodes():
    return list(walk(tree()))


def texts(payload):
    return [(payload.get(key) or "").strip() for key in ("name", "desc", "text")]


def usable(payload):
    return payload.get("visible") is not False and payload.get("package") != "com.android.systemui"


def smallest(matches):
    best = None
    best_area = None
    for payload in matches:
        if not usable(payload):
            continue
        size = payload.get("size") or [1, 1]
        area = float(size[0]) * float(size[1])
        if best_area is None or area < best_area:
            best, best_area = payload, area
    return best


def find(keyword, current=None):
    return smallest(
        payload for payload in (current if current is not None else nodes())
        if any(keyword in value for value in texts(payload))
    )


def find_exact(value, current=None):
    return smallest(
        payload for payload in (current if current is not None else nodes())
        if value in texts(payload)
    )


def click_pos(pos, label):
    poco.click(pos)
    print("TAP:", label, "POS:", pos, flush=True)


def tap(keyword, exact=False):
    payload = find_exact(keyword) if exact else find(keyword)
    if payload is None:
        raise AssertionError("未找到元素：%s" % keyword)
    click_pos(payload.get("pos") or [0.5, 0.5], keyword)


def fingerprint(current=None):
    values = []
    for payload in current if current is not None else nodes():
        if not usable(payload):
            continue
        for value in texts(payload):
            if not value or len(value) > 80 or re.search(r"\d", value):
                continue
            if re.fullmatch(r"[A-Z]{3,12}", value):
                continue
            values.append(value)
    raw = json.dumps(sorted(set(values)), ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def safe_name(value):
    result = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")
    return result or "未命名"


def numbered(folder, label):
    key = str(folder)
    sequences[key] = sequences.get(key, 0) + 1
    return folder / ("%03d_%s.png" % (sequences[key], safe_name(label)))


def expect(navigation):
    coverage.setdefault(navigation, "pending")


def write_row(row):
    exists = MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in FIELDS})


def save_capture(relative, navigation, source, action):
    target = SCREENSHOTS / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(1.2)
    mark = fingerprint()
    snapshot(filename=str(target), quality=99)
    if not target.exists() or target.stat().st_size == 0:
        raise AssertionError("截图文件未生成：%s" % target)
    write_row({
        "screenshot": str(target.relative_to(RUN_ROOT)),
        "navigation_path": navigation,
        "source": source,
        "action": action,
        "status": "ok",
        "fingerprint": mark,
    })
    coverage[navigation] = "ok"
    print("CAPTURE:", target.relative_to(RUN_ROOT), flush=True)


def save_error(name, navigation, source, action, error, capture=True):
    expect(navigation)
    screenshot = ""
    if capture:
        ERRORS.mkdir(parents=True, exist_ok=True)
        target = ERRORS / (safe_name(name) + ".png")
        try:
            snapshot(filename=str(target), quality=99)
            screenshot = str(target.relative_to(RUN_ROOT))
        except Exception:
            pass
    write_row({
        "screenshot": screenshot,
        "navigation_path": navigation,
        "source": source,
        "action": action,
        "status": "failed",
        "error": str(error),
    })
    coverage[navigation] = "failed"
    print("ERROR:", navigation, error, flush=True)


def wait_until(predicate, message, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return
        except Exception as error:
            last_error = error
        else:
            last_error = None
        time.sleep(1)
    if last_error:
        raise AssertionError("%s；最后错误：%s" % (message, last_error))
    raise AssertionError(message)


def wait_for(keyword, timeout=30):
    wait_until(lambda: find(keyword) is not None, "等待元素超时：%s" % keyword, timeout)


def is_market(current=None):
    current = current if current is not None else nodes()
    return bool(
        find("行情\n第 1 个标签", current)
        and find("卖价", current)
        and find("买价", current)
        and not find("登录/注册", current)
        and not find("取消", current)
    )


def is_detailed():
    return find("最低") is not None


def is_search(current=None):
    current = current if current is not None else nodes()
    return bool(find_exact("取消", current) and category_rows(current))


def is_category(category, current=None):
    current = current if current is not None else nodes()
    title = find_exact(category, current)
    if title is None:
        return False
    pos = title.get("pos") or [0.5, 0.5]
    return pos[1] < 0.08 and not find_exact("取消", current)


def is_instrument_detail(symbol, current=None):
    current = current if current is not None else nodes()
    title = find_exact(symbol, current)
    if title is None:
        return False
    pos = title.get("pos") or [0.5, 0.5]
    return bool(pos[1] < 0.08 and find("点差", current) and find("小数位", current))


def wait_market(timeout=60):
    wait_until(lambda: is_market() and find("AUDUSD") is not None, "等待行情首页及品种数据超时", timeout)


def ensure_detailed():
    wait_market()
    if not is_detailed():
        click_pos(EYE_POS, "恢复详细视图")
        wait_until(is_detailed, "无法恢复行情详细视图", 10)


def category_rows(current=None):
    result = {}
    for payload in current if current is not None else nodes():
        if not usable(payload) or payload.get("type") != "android.view.View":
            continue
        value = (payload.get("name") or "").strip()
        pos = payload.get("pos") or [0.5, 0.5]
        size = payload.get("size") or [0, 0]
        if not value or "\n" in value or len(value) > 50 or value.startswith("android."):
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 .]*", value):
            continue
        if abs(pos[0] - 0.5) < 0.02 and 0.08 < pos[1] < 0.995 and size[0] > 0.8:
            result.setdefault(value, payload)
    return result


def product_rows(current=None):
    result = {}
    for payload in current if current is not None else nodes():
        if not usable(payload) or payload.get("type") != "android.view.View":
            continue
        value = (payload.get("name") or "").strip()
        pos = payload.get("pos") or [0.5, 0.5]
        size = payload.get("size") or [0, 0]
        first_line = value.split("\n", 1)[0].strip()
        if "\n" not in value or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,30}", first_line):
            continue
        if abs(pos[0] - 0.5) < 0.02 and 0.08 < pos[1] < 0.995 and size[0] > 0.8:
            result.setdefault(first_line, payload)
    return result


def row_signature(rows):
    return tuple((name, round((payload.get("pos") or [0, 0])[1], 4)) for name, payload in rows.items())


def swipe_up():
    poco.swipe([0.5, 0.82], [0.5, 0.28], duration=0.5)
    time.sleep(1.5)


def swipe_down():
    poco.swipe([0.5, 0.25], [0.5, 0.82], duration=0.5)
    time.sleep(1.5)


def collect_rows(reader, max_scrolls=20):
    discovered = {}
    previous = None
    for _ in range(max_scrolls + 1):
        current_rows = reader()
        for name, payload in current_rows.items():
            discovered.setdefault(name, payload)
        signature = row_signature(current_rows)
        if signature == previous:
            break
        previous = signature
        swipe_up()
    return list(discovered)


def scroll_to_top(reader):
    previous = None
    for _ in range(20):
        signature = row_signature(reader())
        if signature == previous:
            return
        previous = signature
        swipe_down()


def locate_row(name, reader):
    payload = reader().get(name)
    if payload is not None:
        return payload
    previous = None
    for _ in range(20):
        signature = row_signature(reader())
        if signature == previous:
            break
        previous = signature
        swipe_up()
        payload = reader().get(name)
        if payload is not None:
            return payload
    raise AssertionError("列表中未找到入口：%s" % name)


def open_search():
    if is_search():
        return
    ensure_detailed()
    try:
        tap("icon_com_search")
    except AssertionError:
        click_pos(SEARCH_POS, "交易品种搜索")
    wait_until(is_search, "未进入交易品种搜索", 15)


def leave_search():
    if is_search():
        tap("取消", exact=True)
        wait_market(15)


def back_to_market():
    for _ in range(5):
        if is_market():
            return
        current = nodes()
        if find_exact("取消", current):
            tap("取消", exact=True)
        elif (
            find("设置账号", current)
            or find("申请交易账号", current)
            or find("申请模拟账号", current)
            or find("点差", current)
            or product_rows(current)
        ):
            click_pos(BACK_POS, "页面内返回")
        elif find("图表", current):
            click_pos([0.1, 0.97375], "底部行情 tab")
        else:
            device.keyevent("BACK")
            print("EXIT: Android BACK", flush=True)
        time.sleep(2)
    if not is_market():
        raise AssertionError("无法返回行情首页")


def recover():
    try:
        back_to_market()
        ensure_detailed()
    except Exception as error:
        print("RECOVERY_ERROR:", error, flush=True)


def is_login_form(current=None):
    current = current if current is not None else nodes()
    return bool(find("请输入邮箱或手机号", current) and find("请输入密码", current) and find("立即注册", current))


def is_register(current=None):
    current = current if current is not None else nodes()
    return bool(find("国家/地区", current) and find("账号与验证", current) and find("同意服务条款并注册", current))


def is_forgot(current=None):
    current = current if current is not None else nodes()
    return bool(find("忘记密码", current) and find("设置新密码", current))


def is_document(title, current=None):
    current = current if current is not None else nodes()
    payload = find_exact(title, current)
    if payload is None:
        return False
    return (payload.get("pos") or [0.5, 0.5])[1] < 0.08


def close_country_sheet():
    if find("选择国家/地区") is None:
        return
    click_pos(SHEET_CLOSE_POS, "关闭国家/地区选择")
    wait_until(lambda: is_register() and find("选择国家/地区") is None, "国家/地区选择未关闭", 10)


def recover_login():
    for _ in range(4):
        current = nodes()
        if is_login_form(current):
            return
        if find("选择国家/地区", current):
            close_country_sheet()
        elif (
            is_register(current)
            or is_forgot(current)
            or is_document("人工客服", current)
            or is_document("客户协议", current)
            or is_document("隐私和个人数据保护政策", current)
        ):
            click_pos(BACK_POS, "登录子页返回")
        else:
            raise AssertionError("无法识别登录子页，停止盲目返回")
        time.sleep(2)
    if not is_login_form():
        raise AssertionError("无法返回账号登录页")


def attempt_login_capture(navigation, filename, source, action, operation):
    expect(navigation)
    try:
        operation()
        save_capture(Path("00_登录") / filename, navigation, source, action)
    except Exception as error:
        save_error(filename.replace(".png", ""), navigation, source, action, error)
    finally:
        try:
            recover_login()
        except Exception as error:
            print("RECOVERY_ERROR:", error, flush=True)


def open_forgot_email():
    tap("忘记密码")
    wait_until(
        lambda: is_forgot() and find("邮箱验证") is not None and find("使用手机号找回密码") is not None,
        "未进入忘记密码邮箱验证状态", 15,
    )


def open_forgot_phone():
    open_forgot_email()
    tap("使用手机号找回密码")
    wait_until(
        lambda: is_forgot() and find("手机验证") is not None and find("使用邮箱找回密码") is not None,
        "未切换忘记密码手机验证状态", 10,
    )


def open_register():
    tap("立即注册")
    wait_until(lambda: is_register() and find("邮箱验证") is not None, "未进入注册邮箱验证状态", 15)


def open_register_phone():
    open_register()
    tap("邮箱验证")
    wait_until(lambda: is_register() and find("手机验证") is not None, "未切换注册手机验证状态", 10)


def open_country():
    open_register()
    tap("中国", exact=True)
    wait_for("选择国家/地区", 10)


def open_phone_code():
    open_register()
    tap("+86", exact=True)
    wait_for("选择国家/地区", 10)


def open_agreement():
    open_register()
    click_pos(AGREEMENT_POS, "打开客户协议")
    wait_until(lambda: is_document("客户协议"), "客户协议未加载", 20)


def open_privacy():
    open_register()
    click_pos(PRIVACY_POS, "打开隐私和个人数据保护政策")
    wait_until(lambda: is_document("隐私和个人数据保护政策"), "隐私政策未加载", 20)


def open_support():
    tap("chatHeaderButton")
    wait_until(lambda: is_document("人工客服"), "人工客服未加载", 20)


def capture_login_entries():
    captures = (
        ("登录/注册/账号登录/忘记密码/邮箱验证", "003_忘记密码_邮箱验证.png", "登录/注册/账号登录", "点击忘记密码（未提交）", open_forgot_email),
        ("登录/注册/账号登录/忘记密码/手机验证", "004_忘记密码_手机验证.png", "登录/注册/账号登录", "切换手机号找回（未提交）", open_forgot_phone),
        ("登录/注册/账号登录/注册/邮箱验证", "005_注册_邮箱验证.png", "登录/注册/账号登录", "点击立即注册（未提交）", open_register),
        ("登录/注册/账号登录/注册/手机验证", "006_注册_手机验证.png", "登录/注册/账号登录", "切换手机验证（未发送验证码）", open_register_phone),
        ("登录/注册/账号登录/注册/选择国家地区", "007_注册_选择国家地区.png", "登录/注册/账号登录/注册", "打开国家/地区选择（未选择）", open_country),
        ("登录/注册/账号登录/注册/选择手机区号", "008_注册_选择手机区号.png", "登录/注册/账号登录/注册", "打开手机区号选择（未选择）", open_phone_code),
        ("登录/注册/账号登录/注册/客户协议", "009_客户协议.png", "登录/注册/账号登录/注册", "打开客户协议", open_agreement),
        ("登录/注册/账号登录/注册/隐私和个人数据保护政策", "010_隐私和个人数据保护政策.png", "登录/注册/账号登录/注册", "打开隐私政策", open_privacy),
        ("登录/注册/账号登录/人工客服", "011_人工客服.png", "登录/注册/账号登录", "打开人工客服（未发送消息）", open_support),
    )
    for navigation, filename, source, action, operation in captures:
        attempt_login_capture(navigation, filename, source, action, operation)


def is_account_tab(tab, current=None):
    current = current if current is not None else nodes()
    if find("设置账号", current) is None:
        return False
    if tab == "实盘账号":
        return find("开设真实账号", current) is not None
    if tab == "模拟账号":
        return find("开设模拟账号", current) is not None
    return find("以下账号已被归档", current) is not None


def capture_account():
    folder = Path("01_行情/01_设置账号")
    for index, tab in enumerate(("实盘账号", "模拟账号", "归档账号"), 1):
        navigation = "行情/设置账号/" + tab
        filename = "%03d_%s.png" % (index, tab)
        expect(navigation)
        try:
            ensure_detailed()
            tap("Live")
            wait_for("设置账号", 15)
            if tab != "实盘账号":
                tap(tab, exact=True)
            wait_until(lambda: is_account_tab(tab), "账号设置未切换到%s" % tab, 10)
            action = "点击账户下拉" if tab == "实盘账号" else "点击%s tab（未选择账号）" % tab
            save_capture(folder / filename, navigation, "行情首页", action)
            click_pos(BACK_POS, "设置账号返回")
            wait_market(15)
        except Exception as error:
            save_error(filename.replace(".png", ""), navigation, "行情首页", "采集账号设置%s" % tab, error)
            recover()


def capture_open_real_account():
    navigation = "行情/设置账号/实盘账号/开设真实账号"
    expect(navigation)
    try:
        ensure_detailed()
        tap("Live")
        wait_for("设置账号", 15)
        tap("开设真实账号", exact=True)
        wait_until(
            lambda: find("申请交易账号") is not None and find_exact("MT4") is not None and find_exact("MT5") is not None,
            "开设真实账号首个表单页未加载", 15,
        )
        save_capture(
            Path("01_行情/01_设置账号/004_开设真实账号.png"),
            navigation, "行情/设置账号/实盘账号", "打开首个表单页（未填写、未提交）",
        )
        click_pos(BACK_POS, "申请交易账号返回")
        wait_for("设置账号", 15)
        click_pos(BACK_POS, "设置账号返回")
        wait_market(15)
    except Exception as error:
        save_error("004_开设真实账号", navigation, "行情/设置账号/实盘账号", "采集开设真实账号首屏", error)
        recover()


def capture_open_demo_account():
    navigation = "行情/设置账号/模拟账号/开设模拟账号"
    expect(navigation)
    try:
        ensure_detailed()
        tap("Live")
        wait_for("设置账号", 15)
        tap("模拟账号", exact=True)
        wait_until(lambda: is_account_tab("模拟账号"), "账号设置未切换到模拟账号", 10)
        tap("开设模拟账号", exact=True)
        wait_until(
            lambda: find("申请模拟账号") is not None and find_exact("MT4") is not None and find_exact("MT5") is not None,
            "开设模拟账号首个表单页未加载", 15,
        )
        save_capture(
            Path("01_行情/01_设置账号/005_开设模拟账号.png"),
            navigation, "行情/设置账号/模拟账号", "打开首个表单页（未填写、未提交）",
        )
        click_pos(BACK_POS, "申请模拟账号返回")
        wait_for("设置账号", 15)
        click_pos(BACK_POS, "设置账号返回")
        wait_market(15)
    except Exception as error:
        save_error("005_开设模拟账号", navigation, "行情/设置账号/模拟账号", "采集开设模拟账号首屏", error)
        recover()


def capture_view_toggle(label, pos, filename):
    navigation = "行情/首页/" + label
    expect(navigation)
    try:
        ensure_detailed()
        click_pos(pos, label)
        wait_until(lambda: not is_detailed(), "%s未切换到简洁视图" % label, 10)
        save_capture(Path("01_行情") / filename, navigation, "行情首页", "点击%s切换简洁视图" % label)
        click_pos(pos, "恢复详细视图")
        wait_until(is_detailed, "%s无法恢复详细视图" % label, 10)
    except Exception as error:
        save_error(filename.replace(".png", ""), navigation, "行情首页", "采集%s" % label, error)
        recover()


def capture_edit():
    navigation = "行情/自选列表编辑"
    expect(navigation)
    try:
        ensure_detailed()
        before = fingerprint()
        try:
            tap("icon_com_plus_black")
        except AssertionError:
            click_pos(EDIT_POS, "自选列表编辑")
        time.sleep(2.5)
        if before == fingerprint():
            raise AssertionError("点击后未识别到页面变化")
        if find("完成") is not None:
            save_capture(
                Path("01_行情") / "004_自选列表编辑_新手引导.png",
                navigation + "/新手引导", "行情首页", "点击自选列表编辑",
            )
            tap("完成", exact=True)
            time.sleep(2)
        save_capture(Path("01_行情") / "005_自选列表编辑.png", navigation, "行情首页", "进入自选列表编辑")
        click_pos(EDIT_POS, "退出自选列表编辑")
        wait_market(15)
    except Exception as error:
        save_error("自选列表编辑", navigation, "行情首页", "采集自选列表编辑", error)
        try:
            if find("完成") is not None:
                tap("完成", exact=True)
                time.sleep(2)
            if not is_market():
                click_pos(EDIT_POS, "退出自选列表编辑")
                time.sleep(2)
        except Exception as recovery_error:
            print("RECOVERY_ERROR:", recovery_error, flush=True)
        recover()


def capture_market_detail():
    navigation = "行情/行情详情/AUDUSD"
    expect(navigation)
    try:
        ensure_detailed()
        before = fingerprint()
        tap("AUDUSD")
        time.sleep(2.5)
        if before == fingerprint():
            raise AssertionError("点击后未识别到行情详情")
        save_capture(Path("01_行情") / "006_行情详情_AUDUSD.png", navigation, "行情首页", "点击AUDUSD")
        back_to_market()
        ensure_detailed()
    except Exception as error:
        save_error("行情详情_AUDUSD", navigation, "行情首页", "采集AUDUSD行情详情", error)
        recover()


REPRESENTATIVE_PRODUCTS = (
    ("MT4", "FX Majors.pro", "USDCAD.pro"),
    ("MT5", "FX Majors", "AUDUSD"),
)


def capture_product(platform, category, category_folder, symbol):
    navigation = "行情/交易品种搜索/%s/%s/%s" % (platform, category, symbol)
    expect(navigation)
    source = "行情/交易品种搜索/%s/%s" % (platform, category)
    try:
        payload = locate_row(symbol, product_rows)
        pos = payload.get("pos") or [0.5, 0.5]
        click_pos([0.35, pos[1]], platform + "品种详情/" + symbol)
        wait_until(lambda: is_instrument_detail(symbol), "未进入品种规格详情：%s" % symbol, 15)
        filename = "002_%s_%s详情.png" % (symbol, platform)
        save_capture(category_folder / filename, navigation, source, "点击代表品种行（避开加号）")
        click_pos(BACK_POS, "品种详情返回")
        wait_until(lambda: is_category(category), "未返回分类列表：%s" % category, 15)
    except Exception as error:
        save_error(platform + "_" + category + "_" + symbol, navigation, source, "采集代表品种详情", error)
        recover()
        raise


def capture_category(platform, category, symbol, category_index):
    navigation = "行情/交易品种搜索/%s/%s" % (platform, category)
    expect(navigation)
    folder = Path("01_行情/02_交易品种搜索") / (
        "%02d_%s_%s" % (category_index, platform, safe_name(category))
    )
    try:
        open_search()
        payload = locate_row(category, category_rows)
        pos = payload.get("pos") or [0.5, 0.5]
        click_pos([0.35, pos[1]], platform + "搜索分类/" + category)
        wait_until(lambda: is_category(category), "未进入搜索分类：%s" % category, 15)
        save_capture(folder / "001_分类列表.png", navigation, "行情/交易品种搜索", "点击%s代表分类%s" % (platform, category))
        capture_product(platform, category, folder, symbol)
        if is_category(category):
            click_pos(BACK_POS, "分类返回搜索")
            wait_until(is_search, "分类未返回搜索首页", 15)
        leave_search()
    except Exception as error:
        save_error(platform + "_分类_" + category, navigation, "行情/交易品种搜索", "采集代表分类及单个详情", error)
        recover()


def capture_search_tree():
    navigation = "行情/交易品种搜索"
    expect(navigation)
    try:
        open_search()
        save_capture(
            Path("01_行情/02_交易品种搜索/001_搜索首页.png"),
            navigation, "行情首页", "点击交易品种搜索",
        )
        leave_search()
    except Exception as error:
        save_error("交易品种搜索", navigation, "行情首页", "打开交易品种搜索", error)
        recover()
        return
    print("REPRESENTATIVE_PRODUCTS:", REPRESENTATIVE_PRODUCTS, flush=True)
    for index, (platform, category, symbol) in enumerate(REPRESENTATIVE_PRODUCTS, 1):
        capture_category(platform, category, symbol, index)


def audit_coverage():
    pending = [name for name, status in coverage.items() if status == "pending"]
    for navigation in pending:
        save_error(
            "未覆盖_" + safe_name(navigation), navigation, "覆盖验收", "入口覆盖核销",
            "入口已发现但没有截图或明确失败记录", capture=False,
        )
    counts = {status: list(coverage.values()).count(status) for status in ("ok", "failed")}
    print("COVERAGE:", counts, "TOTAL:", len(coverage), flush=True)
    if pending:
        raise AssertionError("存在未核销入口：%s" % pending)


def main():
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    device.shell("pm clear " + PACKAGE)
    device.shell("am start -n %s/%s" % (PACKAGE, ACTIVITY))
    wait_for("登录/注册", 40)
    save_capture(Path("00_登录/001_登录注册.png"), "登录/注册", "启动 App", "清除数据并启动")

    tap("登录/注册")
    wait_for("请输入邮箱或手机号", 15)
    save_capture(Path("00_登录/002_账号登录.png"), "登录/注册/账号登录", "登录/注册", "点击登录/注册")
    capture_login_entries()
    if not is_login_form():
        raise AssertionError("登录子页采集后未返回账号登录页")

    tap("请输入邮箱或手机号")
    device.shell('input text "%s"' % ACCOUNT)
    tap("请输入密码")
    device.shell('input text "%s"' % PASSWORD)
    tap("登录")
    wait_market(40)
    ensure_detailed()
    save_capture(Path("01_行情/001_首页.png"), "行情/首页", "账号登录", "新账号登录")

    capture_account()
    capture_open_real_account()
    capture_open_demo_account()
    capture_view_toggle("眼睛图标", EYE_POS, "002_眼睛图标_简洁视图.png")
    capture_view_toggle("列表图标", LIST_POS, "003_列表图标_简洁视图.png")
    capture_edit()
    capture_market_detail()
    capture_search_tree()
    back_to_market()
    ensure_detailed()
    audit_coverage()
    print("RUN_ROOT:", RUN_ROOT, flush=True)


if __name__ == "__main__":
    main()
