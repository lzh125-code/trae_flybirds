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

当前项目已验证设备为 `emulator-5554`，包名为 `com.wetrade.crm.trial`，启动 Activity 为 `com.wetrade.crm.MainActivity`。

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

## 等真实内容再截图

不要只等页面框架或表头。行情首页必须同时满足页面标识和真实品种行出现，例如 `卖价`、`买价`、第一个行情 tab 以及 `AUDUSD`。

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

从项目根目录运行当前基线：

```powershell
python "flybirds_demo/pscript/crawl_login_market.py"
```

交付前逐项检查：

1. 逐张打开截图，确认方向正确、页面真实、数据已加载且没有诊断浮层。
2. 核对截图路径、序号、导航名称和清单记录一一对应。
3. 统计 `ok` 与 `failed`，有失败项时明确说明，不只检查脚本退出码。
4. 核销每个目标入口：登录子页、账号设置三个 tab、开设真实账号与开设模拟账号首屏、行情入口、MT4/MT5 代表分类及各自一个品种详情都必须有正常截图或明确失败记录，不允许停留在 `pending`。tab 内的下级入口不会自动发现，新增入口必须同时补采集函数和 `expect()` 登记，否则不会被 `audit_coverage()` 报出。
5. 排除名为 `android.view.View` 等伪分类；当前代表项为 MT4 `FX Majors.pro/USDCAD.pro` 与 MT5 `FX Majors/AUDUSD`，不递归其他分类或品种。
6. 确认未进入范围外页面，未执行禁止操作。
7. 返回最终时间戳目录和清单链接，并简述成功页面与失败项。

早期 6 张截图目录只代表有限基线，不得表述为完整覆盖示例；完整结果以当次时间戳目录和 `manifest.csv` 的验收统计为准。
