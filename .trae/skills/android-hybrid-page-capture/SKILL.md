---
name: android-hybrid-page-capture
description: 采集 Android RN 与 Flutter 混合 App 的登录、账号设置及限定页面截图并生成清单。用户要求遍历 App 页面、批量截图、采集行情页或复用 Airtest Poco 自动化流程时使用；不用于无边界遍历或交易操作。
---

# Android 混合 App 限定页面采集

以 `flybirds_demo/pscript/crawl_login_market.py` 为已验证实现基线。复用其中的控件查找、页面指纹、截图、清单和恢复逻辑，按当次账号与采集范围调整主流程。

## 先限定边界

开始前确认账号、起点、终点和禁止操作。优先采用“从登录到某个主 tab 结束”的小范围任务，跑通后再扩展。

- 不进入范围外的主 tab。
- 不执行下单、保存资料、入出金、删除、注销或退出登录等操作。
- 不提交注册或找回密码，不发送验证码；账号设置不点击账号卡片或实际切换账号，不提交开设账号表单；开设真实账号和开设模拟账号都只采集首个表单页，不填写、不切换平台、不提交。
- 清数据只用于明确要求从登录态开始的采集；执行前确认对应包名。
- 不把密码写入截图、清单或结果说明。

## 固定设备状态

当前项目已验证设备为 `emulator-5554`，启动 Activity 为 `com.wetrade.crm.MainActivity`。包名按环境区分：试用包 `com.wetrade.crm.trial`，“我的”栏目采集使用 demo 包 `com.wetrade.crm.demo`，均可用 `CRAWL_PACKAGE` 覆盖。

在创建 Poco 前固定当前雷电模拟器的竖屏状态，避免旋转后控件树缺底部 tab、坐标系变化和截图横屏：

```python
device = connect_device("Android:///" + DEVICE_ID)
device.shell("settings put system accelerometer_rotation 0")
device.shell("wm user-rotation lock 0")
device.shell("wm size 900x1600")
time.sleep(1)
poco = AndroidUiautomationPoco(device=device, use_airtest_input=True)
```

`900x1600` 是当前设备的已验证尺寸；换设备时先读取实际尺寸，不要直接套用。

使用显式 Activity 启动，避免精简模拟器没有 `monkey` 导致启动失败：

```python
device.shell("pm clear " + PACKAGE)
device.shell("am start -n %s/%s" % (PACKAGE, ACTIVITY))
```

## 按混合控件树查找和点击

RN 与 Flutter 混合页面的文本可能出现在 `name`、`desc` 或 `text`，同时检查这三个属性。

- 跳过不可见节点。
- 排除 `com.android.systemui`，否则“完成”等关键词可能误匹配状态栏的“充电已完成”。
- 包含匹配可能命中全屏父容器，选择匹配节点中面积最小者。
- 优先使用 `poco.click(pos)` 或 Poco 节点点击；当前设备上 `device.touch()` 已验证不可靠。
- 图标没有可读名称时，先尝试资源名，再使用已验证的归一化坐标作为 fallback，并打印实际点击位置。
- 不假定不同账号布局相同；分类栏、品种后缀和新手引导都可能不同。
- PocoService 的 TestActivity 初始化后可能盖住目标 App；创建 Poco 后重新 `am start` 恢复原任务，再识别页面。底部导航描述可能被 `clean_labels()` 过滤，导航入口识别要直接检查原始 `node_texts()`，不能依赖过滤后的 `labels`。
- 如果当前是模拟器桌面或 PocoService，禁止继续 BACK；它不是 App 子页，继续返回只会退出到桌面。先恢复目标 App 前台，仍无法识别则明确失败。

## 日常检查的强制交互清单

每个页面只做纵向滚动会漏掉大量功能入口。日常检查按下面清单逐项覆盖，缺任一项即视为漏采：

| 交互类型 | 判定方式 | 采集动作 |
| --- | --- | --- |
| 纵向内容 | 默认 | 滚动到底逐屏截图，指纹不再变化为止 |
| 带图标/窄条行 | 宽 0.18~0.55、高 0.018~0.16 | 点进去截一屏，再返回原页 |
| 下拉/选择器 | 点开后底层文案仍保留 ≥50% | 截展开态选项列表，再逐个选中前 3 个选项各截一张 |
| 按钮 | 宽 ≥0.18 的短文案控件 | 点击后截图；确认/提交/买入/卖出类只截展开态，不点确认 |
| 横向 tab 栏 | 同一行 ≥3 个短标签（宽 0.08~0.36、高 ≤0.06） | 逐个切换并截图 |
| 横向轮播 | 页面出现 `n/m` 翻页指示 | 在同一 y 上向左滑，最多 4 屏，再滑回原位 |
| 加载完成 | 截图前 | 文案连续两轮不变，且无「加载中/Loading/読み込み中」，否则继续等 |

硬性例外：`退出/注销/登出/ログアウト/退会` 只截图不点击，一按就掉登录态，后续采集全部作废。

交互截图与普通截图放同一层级，目录名带前缀区分：`互动_<元素>/001_展开.png`、`互动_<元素>/002_选中_xx.png`、`图标行_<元素>/001_进入.png`、`横tab_<标签>/001_切换.png`、`横滑/00X_滑动X.png`，`action` 字段写清实际动作。

## 统一取数与通用交互发现

“我的”栏目以 `flybirds_demo/pscript/crawl_mine_lang.py` 为实现基线。消息中心的一次性坐标标定不能复用为其他页面的固定结论，所有页面都执行同一套发现、计划、执行、恢复和审计流程：

1. **统一取数层**：每屏通过 `page_items()` 合并控件树文本、几何和可点击父节点；稳定文案少于 3 条或没有可点击节点时，用 OCR 补充带归一化坐标的文本块。目标来源统一记录为 `tree`、`ocr` 或 `fixed`，RN、Flutter、canvas 与 H5 不因技术栈不同而跳过发现。
2. **每屏无条件发现**：`discover_generic()` 检查同行至少 3 个短标签的 Tab、右侧带 `⌄/▾` 的选择器、至少 2 行同构卡片的列表、`n/m` 轮播和可点击按钮；点开面板后独立预扫描。卡片只抽样前 3 条，其余明确记为抽样跳过，通用目标登记数量设上限，避免 canvas 文本块无限膨胀。
3. **固定注册表只做兜底**：固定文案、资源名和已验证坐标可以补充 OCR/控件树漏识别，但未命中必须记 `failed`，不能因为有注册表就关闭通用发现。已登记文案或相同区域不得重复登记。
4. **统一点击变更判定**：控件指纹变化、前后截图差分大于 1%、OCR 文本集合变化，任一成立即视为已切换。canvas 页面必须在点击前计算 `before_image` 与 `before_signature`，否则点击后的 OCR 会被误当成点击前基线。
5. **滚动与页面变化分开**：自动轮播会持续改变整页指纹，不能用整页指纹判断滚动位置。`scroll_hash()` 只取页头约 6%~30% 区域，`scroll_top()`、滚动预扫描和采集前位置恢复统一使用它；页面业务变化仍按上面的三条件判定。顶部/底部手势后的回弹也会让哈希短暂变化，纵滑后必须等回弹结束再比较，不能连续滑屏把动画反复触发。
6. **弹层与补充预扫描防空转**：补充预扫描设置次数上限；一次没有新增目标后标记为空，不再因轮播或动态内容反复触发。消息详情和客服会话正文不纳入卡片点击范围。
7. **覆盖审计门禁**：每页输出 `tree_items`、`ocr_items`、新增目标数和 `unplanned_regions`。可交互区域未被计划覆盖时必须列入未完成；最终至少满足 `pending=0`、`planned=ok+failed+skipped`、`unplanned_actions=0`、`unplanned_regions=0`，并具有首张有效截图证据，不能只凭进程退出码判定完成。
8. **区分同页 Tab 与独立导航页**：消息分类等入口如果会进入独立列表，就使用导航类目标和独立业务键，并在分类详情禁止再次登记当前分类，不能按 Tab 在同页反复点击。恢复来源页时忽略未读角标和金额等动态值；真正的 Tab 定位器要保留 `selected/checked`，避免重复点击当前状态。
9. **覆盖审计同时防漏报和误报**：坐标覆盖复用 `region_registered()`，不能把固定目标的大搜索区域当成点击覆盖区域。忽略未读徽标、轮播状态、中央页头、消息正文等非独立入口；轮播 `n/m` 正则必须带数字和斜杠边界，避免把 `04/09/2025` 误识别为 `4/9`。页头宽度会随未读数变化，不能只靠固定宽度过滤标题。
10. **执行必须复用统一取数层**：发现器如果使用可点击父节点合成文案或 OCR，执行重定位就不能只查原始 `nodes`，否则会出现计划已生成但目标永远无法命中的假失败。`execute_target()` 必须基于同一套 `page_items()` 重定位。
11. **应用边界和状态开关属于安全门禁**：每次动作前后检查前台包名；进入系统设置、应用信息等外部页面后立即恢复目标 App，不预扫描、不点击。通知的 `开启/已开启/关闭/已关闭` 等状态开关会修改账户设置，与手势密码、Google Authenticator、生物识别及系统卸载/清数据/强制停止一样，只登记禁止状态，不执行。

## 1.6 采集方案：键体系、页面地图与双覆盖对账

“我的”栏目按 `flybirds_demo/pscript/crawl_mine_lang.py`（1.6）执行。核心是**先登记可复算的采集目标键，再执行，最后用同一套键对账**，避免“跑完了但不知道漏了什么”。

### 键体系

| 键 | 组成 | 用途 |
| --- | --- | --- |
| `visit_key` | `language \| page_id \| business_key \| view_state_hash` | 一次页面访问的唯一身份；换语言、换 Tab、换展开态都不合并 |
| `plan_key` | `run_id \| visit_key \| target_id` | 本轮计划行主键，必须唯一 |
| `target_key` | `SHA256(visit_key \| target_id \| normalized_locator \| planned_action \| expected_view_state)` | 同一目标在跨轮、跨入口时保持稳定，用于复用判断 |
| `expansion_key` | `language \| root_page_key \| depth=4` | 一个起点页的一次四层扩展 |
| `route_key` / `edge_key` | `language \| source_page_key \| target_id \| normalized_locator \| expected_view_state` / 其 SHA256 | 页面地图的边 |
| `skip_class` | `depth_limit \| safety \| duplicate \| resource \| error` | 跳过必须有分类，`error` 只能用于真实异常 |

- 弱身份页面（只知道文案、还不知道业务键）先占位登记，业务键确定后调用 `rekey_targets()` 重算 `visit_key/plan_key/target_key`，不能留下两套键。
- 定位器入库前必须归一化（坐标保留两位小数、去动态数字），否则同一目标每轮都会产生新键。

### 每页独立四层扩展

- “最多 4 层”指**每个起点页各自向下最多 4 层**，不是全局层数。`relative_depth` 从起点算 1，`path_depth` 只用于诊断。
- 第 4 层页面禁止再进入第 5 层，拦截时写 `skip_class=depth_limit`、`error=第 4 层不再进入第 5 层（当前扩展链）`。
- 每轮起点页强制重扫（只有 `parent is not None` 才走复用判断），保证入口变化能被发现；已完成且证据有效的子页面跨轮、跨入口复用，不重复采集。
- 扩展用 `expansion_key` 注册到页面地图，记录每层节点/边数、第 4 层边界目标和未完成原因。

### 页面地图与快照

持久文件放在语言根目录下，跨轮累积：

```text
app_page_captures/lang/<语言>/
├─ page_map.json          # 节点、边、扩展状态（注册表也从这里恢复）
├─ page_map.mmd           # Mermaid 可视化
├─ screenshots/           # 稳定证据：成功截图按导航路径存放，不随轮次目录删除
├─ <run_id>/
│  ├─ errors/             # 仅本轮错误截图
│  ├─ page_plan.csv
│  ├─ manifest.csv
│  ├─ coverage_report.json
│  ├─ run_status.json     # 完成状态与计数，供采集结束提示
│  └─ page_map_snapshot.json
```

- **成功截图不要放在 `<run_id>/screenshots`**：否则用户清理时间戳目录时会误删已完成页面的证据，页面地图里的复用引用随之失效。成功截图统一写 `lang/<语言>/screenshots/<导航路径>/NNN_名称.png`，清单和 `page_map.json` 里的路径相对语种目录（如 `screenshots/我的/消息/001_逐屏.png`）。
- 本轮目录只保留计划、清单、覆盖报告、快照和 `errors/`。`resolve_ref()` 解析路径时先查本轮目录（兼容旧结构），再查语种目录的稳定证据。
- 稳定目录会保留历史截图，覆盖审计只核销本轮实际写入的 `written_shots`，不能扫描整个 `screenshots` 目录，否则历史文件会全部被报成“未写入清单”。
- `page_map.json` 的 `nodes` 键是 `visit_key`，`edges` 键是 `edge_key`；`expansions` 必须带 `pages` 字典，旧结构缺失时用 `setdefault("pages", {})` 兼容，否则会 `KeyError: 'pages'`。
- 节点保存 `status`、`attempts`、`last_valid_capture` 和 `evidence`，复用时以证据文件真实可解码为准，不认旧状态字段。

### 记录方案 A（不建每页 JSON）

只写四个文件：`page_plan.csv`（计划）、`manifest.csv`（结果+证据）、`coverage_report.json`（对账）、`page_map.json`（全局地图）。

- `page_plan.csv` 固定列包含 `run_id/plan_key/target_key/parent_plan_key/expansion_root_key/relative_depth/path_depth/skip_class/edge_key/map_reason`；运行期字段（`label`、`locator_json` 等）只留内存，不写 CSV。
- `manifest.csv` 以截图行为单位，`screenshot` 为空表示无截图动作的结果。
- 覆盖率必须做**双覆盖对账**：
  - `reconciliation.pages[visit_key]`：`missing_result_plan_keys`、`missing_evidence_plan_keys`、`orphan_result_keys` 三者都必须为空。
  - `reconciliation.expansions[expansion_key]`：各层节点/边数、第 4 层边界、未完成原因齐全。
  - 同时校验 `plan_key` 唯一、`skip_class` 合法、页面级 `scroll_capped/scroll_note`。
- 审计不通过时 `main()` 主动 `sys.exit(1)`；这是**判定未完成**，不是脚本崩溃，汇报时必须区分。

### 长列表与回顶

- 消息中心等长列表：超过 **3 屏**（`CRAWL_LIST_SCREENS`）仍未到底，直接预设为到底，标记 `scroll_capped=True`、`scroll_note=长列表超过 3 屏，按上限视为到底`，页面按 `complete` 处理并继续执行，不再探测。
- 其他页面允许 12 屏（`CRAWL_MAX_SCREENS`），超限保留计划继续执行、页面记 `partial`。
- `scroll_top()` 预算改为 `MAX_SCREENS * 2 + 6`（默认 30 次）。预算过小会导致“来源页回到顶部失败”→ 整页停止点击，是上一轮 68 条跳过的根因之一。
- `scroll_hash()` 和列表阈值要绑定 `MAX_SCREENS`，不要写死屏数。

### 客服页：FAQ 与人工会话拆分

- 移除整页豁免。客服页按 `business_key` 拆成 `faq` 与 `conversation` 两个页面身份。
- FAQ 页用固定目标 `faq.search`（`kind=faq_search`）：打开搜索 → 点输入框 → 输入 `app` → 截图 → 清空 → 返回并校验。会话页用 `faq.human`（`kind=customer_service_conversation`）。
- 会话正文区域（约 0.10~0.85）不登记卡片目标；发送、附件等控件写 `forbidden`，输入区写 `record_only`，不执行发送。

### 证据复用门禁

`registry_decision()` 的 `done` 必须同时满足：状态为 `done` 且 `evidence` 中至少一张截图存在、非空、PIL 可解码。证据缺失一律转 `partial` 并重采，不能因为状态字段是 `done` 就跳过。

### 恢复校验只看锚点

- 子页返回来源页时不能比对整页文案：动态推荐、客户列表和轮播都会变化，Jaccard 阈值会把正常返回误判成“来源页业务内容不一致”，进而触发“此前页面状态恢复失败，停止后续点击”，一次误判会连带跳过整页所有入口。
- 恢复判定用 `restored_page()`：来源页的固定入口别名至少命中 2 个即视为恢复；未登记固定入口的页面才退回整页相似度，阈值降到 0.5。
- 消息中心首页只把“重要通知/资金动态/账户动态/品牌动态”四个分类入口当交互目标；分类详情只抽样登记“查看详情”（每个分类最多 3 条），进入详情页采集后返回。发送者、头像、正文和时间戳属于动态内容，不单独登记，也不计入未规划区域。
- 上一轮状态为 `failed` 的页面，新一轮加载页面地图时转成 `partial` 重试一次，避免一次偶发失败把页面永久封存。
- 弹层关闭后来源页通常仍停在原滚动位置，顶部锚点不在屏内会被误判成“来源页内容变化”。必须先 `scroll_top()` 再复核锚点，仍不命中才允许判定恢复失败。
- 补充预扫描“次数已达上限”只是预算耗尽，不能当成恢复失败的理由；命中上限时应直接接受已恢复状态继续。
- 恢复失败只尝试一次：同一页 `restore_failed` 后剩余目标直接核销，禁止对每个目标各发 2 次 BACK，否则会连续退到桌面把后续页面全部弄坏。

### 设备掉线：先分辨环境问题还是脚本问题

- 日志出现 `adb.exe: device 'emulator-5554' not found`、随后 `TransportDisconnected ... 127.0.0.1:<port>`，同时模拟器进程启动时间与掉线时刻吻合，就是模拟器重启导致的掉线，不是脚本死循环；这类轮次直接判废，重连后重跑。
- 重连顺序：`adb kill-server` → `adb start-server` → `adb connect 127.0.0.1:5555` → `adb devices` 与 `getprop sys.boot_completed`（返回 1 才算可用）。LDPlayer 装的是 `E:\leidian\LDPlayer14\adb.exe`，系统 PATH 里没有 adb。
- 模拟器重启后 `/data/local/tmp` 权限异常会让 minicap/Yosemite 安装失败（`INSTALL_FAILED_MEDIA_UNAVAILABLE`），截图自动降级为 `adb screencap`；采集仍可继续，只是变慢，不需要为此重装。
- 采集期间禁止执行任何 adb 命令：会重起 adb server，正在跑的 Airtest 会话立刻掉线。

### 已完成页面只复核首屏

`done` 且证据有效的页面不再整页重扫：进入后读首屏 → 用当前规则重新枚举可见采集项 → 与历史轮次 `page_plan.csv` 中该 `visit_key` 的 `ok` 目标比对 → 只执行缺失项，其余写 `skipped + skip_class=duplicate`。不重复逐屏截图，也不重复点击已采目标；补采结果写入本轮计划与覆盖报告。

```python
def recheck_done_page(ctx, parent, source_target, visit_key):
    shot = read_screen()                      # 刚导航到达，通常已在顶部
    if not restored_page(ctx, shot["labels"]):
        scroll_top()
        shot = read_screen()
    discover_generic(ctx, shot, 1, page_items(shot))
    prior = prior_ok_targets(visit_key)       # 历史 page_plan.csv 里 status=ok 的 target_id
    gaps = [t for t in ctx["targets"].values() if t["target_id"] not in prior]
    for target in gaps:
        execute_target(ctx, target)
```

**复核结果必须回写来源目标**：没有新增项时也要把 `source_target` 置为 `skipped + duplicate`，否则执行器会反复重入同一 pending 目标，表现为日志循环打印“首屏复核无新增”并连续 BACK。执行器再加一层防死循环：同一 `target_id` 连续执行超过 2 次仍为 `pending` 时，按 `skip_class=resource` 核销并写清单。

### 首屏截图后对齐采集项

每页首屏截图落盘后立即对齐一次：用同一帧的控件树与 OCR 重新枚举交互项，与已登记计划比对；新增安全项补入计划后再执行，固定项未在首屏出现时保留待后续屏核销。对齐结果写入覆盖报告的 `reconciliation.pages[visit_key].first_screen_alignment`（`matched`、`added`、`added_targets`）。

### 减少回顶下拉

- 每页维护 `at_top` 状态：同一屏连续处理多个目标时不再重复 `scroll_top()`；只有点击目标或切到第 2 屏后才重新校验。
- 从子页返回来源页时先直接 `read_screen()` 核对锚点，内容一致就视为已回顶，不再执行下拉。
- 不要为了“确认在顶部”每次都跑一遍 `scroll_top()`，长列表页会累积成几十次滑动。

## 等真实内容再截图

不要只等页面框架或表头。行情首页必须同时满足页面标识和真实品种行出现，例如 `卖价`、`买价`、第一个行情 tab 以及 `AUDUSD`。

通用做法是等页面文案稳定后再截，避免把骨架屏或加载态当成正常页面：

```python
def wait_loaded(timeout=6):
    end, previous = time.time() + timeout, None
    while time.time() < end:
        loading = any("加载中" in v or "Loading" in v or "読み込み中" in v for v in page_texts())
        current = signature()
        if not loading and current == previous:
            return True
        previous = current
        time.sleep(1.0)
    return False
```

截图前再留短暂稳定时间，使用：

```python
snapshot(filename=str(target), quality=99)
```

Airtest 的 Minicap 或 Yosemite 初始化报错不一定是阻塞项；只有自动回退后仍无法生成有效截图时才按失败处理。

使用控件树结构指纹判断页面是否变化，不用截图像素哈希。指纹应忽略包含数字的动态文本和纯大写品种名，减少时间、价格及行情数据变化造成的误判。

## 使用页面内退出入口

不要连续盲目发送 Android BACK，它可能退出 App。

当前行情范围已验证的退出方式：

| 页面 | 退出方式 |
| --- | --- |
| 交易品种搜索 | 点击页面内“取消” |
| 自选列表新手引导 | 点击“完成”，只关闭引导，不代表退出编辑 |
| 自选列表编辑 | 点击原铅笔入口位置的勾选图标，当前坐标为 `[0.186667, 0.07125]` |
| 行情详情 | 优先点击底部行情 tab；无底部 tab 时单次 BACK，再识别页面 |
| 设置账号 | 点击页面内返回；只切实盘、模拟、归档 tab，不点击账号卡片 |
| 申请交易账号 / 申请模拟账号 | 只采首个表单页，点击页面内返回；不填写、不切换平台、不提交 |
| 注册国家/地区或区号选择 | 点击弹层右上角关闭，不选择任何条目 |
| 登录子页、协议、隐私政策、人工客服 | 点击页面内返回并重新识别账号登录页；客服页不输入或发送消息 |

每次退出后重新识别行情首页或账号登录页。识别失败时先读取控件树和当前截图，不要重复同一返回动作。

## 保持输出结构一致

每次运行使用独立时间戳目录：

```text
app_page_captures/<账号标识>/<时间戳>/
├─ screenshots/
│  ├─ 00_登录/
│  └─ 01_行情/
│     ├─ 01_设置账号/
│     └─ 02_交易品种搜索/
├─ errors/
└─ manifest.csv
```

- 文件名使用三位序号、真实页面语义和必要的状态后缀。
- 新手引导与正常编辑状态分别截图；引导未出现时不要留下空文件，后续序号保持连续。
- 异常截图放入 `errors`，不要把失败页面伪装成正常结果。
- `manifest.csv` 使用 `utf-8-sig`，字段保持为 `screenshot`、`navigation_path`、`source`、`action`、`status`、`fingerprint`、`error`。
- 清单动作描述必须匹配实际发生的行为，例如未出现引导时写“进入自选列表编辑”，不要写“关闭新手引导”。

## 运行与验收

从项目根目录运行行情基线：

```powershell
python "flybirds_demo/pscript/crawl_login_market.py"
```

“我的”栏目按语言运行，每轮独立时间戳目录：

```powershell
$env:CRAWL_LANG="zh-CN"; $env:CRAWL_DEVICE="emulator-5554"; python -u "flybirds_demo/pscript/crawl_mine_lang.py"
```

- 设备未就绪（`adb devices` 没有 `emulator-5554 device`）时先启动 `E:\leidian\LDPlayer14\dnplayer.exe`，等 `sys.boot_completed=1` 再跑。
- 采集耗时较长，必须让进程脱离终端运行（例如合并成“启动模拟器 → 等待就绪 → 运行采集”的单个后台命令）。终端切换或子进程回收会静默杀掉采集，表现为没有 `coverage_report.json`。
- 采集运行期间禁止再执行 `adb devices`、`adb shell` 等命令：会重启 adb 服务、打断 Airtest 连接，进程表现为长时间不动（文件不再新增）。验收检查等采集结束后再做。
- Airtest 的 minicap/javacap 初始化失败会降级为 ADB 截图，日志里的红色时间戳和 `[ERROR]` 行不一定是阻塞项；只有仍无法生成有效截图才算失败。
- 离线回归：`python "flybirds_demo/pscript/test_crawl_mine_lang_offline.py"`，用于验证身份键、业务键、证据复用和审计对账，不连接设备。

交付前逐项检查：

1. 逐张打开截图，确认方向正确、页面真实、数据已加载且没有诊断浮层。
2. 核对截图路径、序号、导航名称和清单记录一一对应。
3. 统计 `ok` 与 `failed`，有失败项时明确说明，不只检查脚本退出码。
4. 核销每个目标入口：登录子页、账号设置三个 tab、开设真实账号与开设模拟账号首屏、行情入口、MT4/MT5 代表分类及各自一个品种详情都必须有正常截图或明确失败记录，不允许停留在 `pending`。tab 内的下级入口不会自动发现，新增入口必须同时补采集函数和 `expect()` 登记，否则不会被 `audit_coverage()` 报出。
5. 排除名为 `android.view.View` 等伪分类；当前代表项为 MT4 `FX Majors.pro/USDCAD.pro` 与 MT5 `FX Majors/AUDUSD`，不递归其他分类或品种。
6. 确认未进入范围外页面，未执行禁止操作。
7. 返回最终时间戳目录和清单链接，并简述成功页面与失败项。

早期 6 张截图目录只代表有限基线，不得表述为完整覆盖示例；完整结果以当次时间戳目录和 `manifest.csv` 的验收统计为准。

“我的”栏目额外核对：

1. `coverage_report.json` 的 `issues`、`skip_classes` 与 `reconciliation.pages/expansions`：缺失结果、缺失证据、孤立结果都必须为空，`skip_class` 只能是五类之一。
2. 每个起点页都有独立 `expansion_key`，第 4 层边界目标有 `depth_limit` 记录；不能出现第 5 层页面。
3. 消息中心若出现 `scroll_capped=true`，确认 `scroll_note` 写明“超过 3 屏按上限视为到底”，且该页按 `complete` 继续执行而非整页停止。
4. 客服页存在 `faq` 与 `conversation` 两个 `business_key`，FAQ 搜索有输入与截图证据，会话页没有发送消息。
5. 同一语言跨轮、跨入口不重复采集；重复采集只能以“证据文件缺失/不可解码”为由触发。
6. 用 `page_map.mmd` 或 `page_map_snapshot.json` 抽查 2~3 条边，确认 `source_page_key → target_page_key` 与实际导航一致。
7. 抽查 `reconciliation.pages[visit_key].first_screen_alignment`：已完成页面应有首屏对齐记录；没有新增项时只做复核，不得重复逐屏截图或重复点击历史 `ok` 目标。
8. 通知分类页抽查“查看详情”目标：每个分类最多 3 条，详情页有截图，返回后来源页锚点恢复。
