# Flybirds 项目学习记录

用于沉淀每天聊天和实践中验证有效的经验，方便后续快速了解项目状态、复用自动化方法并避开已解决的问题。记录以可复用结论为主，不复制完整聊天过程，不记录账号密码等敏感信息。

## 项目环境

- 工作目录：`D:\trae_flybirds`
- Android 设备：雷电模拟器 `emulator-5554`
- 测试 App：`com.wetrade.crm.trial`
- 启动 Activity：`com.wetrade.crm.MainActivity`
- App 技术形态：React Native 与 Flutter 混合，不能按单一原生或 Flutter 页面处理
- 主要自动化工具：Flybirds、Airtest、Poco、ADB

## 2026-10-30

### Android 登录用例已跑通

登录用例位于 `flybirds_demo/features/android_login.feature`。已验证新测试账号可以登录， Flybirds 结果为 1 个 feature、1 个 scenario、10 个 steps 全部通过。

项目默认配置是 Web 平台，并且默认 APK 配置指向无关应用。因此运行 Android 用例时必须显式覆盖配置：

```powershell
flybirds run --path features/android_login.feature --define platform=android --define deviceId=emulator-5554 --define packageName=com.wetrade.crm.trial
```

雷电精简镜像可能没有 `monkey`，应通过自定义步骤使用包名和 Activity 显式启动 App。

### 限定范围页面采集

采集脚本位于 `flybirds_demo/pscript/crawl_login_market.py`，从清除 App 数据、登录入口开始，覆盖登录子页、账号设置及第一个“行情”tab 的限定页面。

当前采集范围包括：忘记密码的邮箱/手机状态、注册的邮箱/手机状态、国家/地区与区号选择、客户协议、隐私政策、人工客服；设置账号的实盘/模拟/归档 tab 和开设真实账号、开设模拟账号的首个表单页；行情首页入口；交易品种搜索只采 MT4 `FX Majors.pro/USDCAD.pro` 与 MT5 `FX Majors/AUDUSD` 两个代表分类及各自一个详情，不递归其他分类或品种。每个目标入口必须在 `manifest.csv` 中有正常截图或明确失败记录。

安全边界：不提交注册或找回密码，不发送验证码或客服消息；账号设置不点击账号卡片、不实际切换账号；开设真实账号和开设模拟账号都只进入首屏，不填写、不切换平台、不提交，不完成开户流程；不点击搜索加号或交易按钮，不执行下单、保存资料、入出金、删除、注销或退出登录。

历史采集目录按最多保留最近两次的规则清理；本次验收后保留 `app_page_captures/potatolin/20261030_181136/` 与 `20261030_175427/`。最新清单共 26 个目标：25 个 `ok`、1 个 `failed`（眼睛图标未切换到简洁视图），无 `pending`；26 张截图均已核对，清单路径一一对应，尺寸均为 `900x1600`。开设真实账号、开设模拟账号两个首屏，以及 MT4/MT5 代表分类及各自一个品种详情均已成功采集。

设置账号各 tab 的下级入口需要显式登记，脚本不会自动发现。`capture_account()` 只截三个 tab 本身，开户类页面由独立函数采集；`audit_coverage()` 只核销代码中 `expect()` 登记过的入口，未登记的页面不会报 `pending`，因此新增入口时必须同步补函数和覆盖项。

### RN 与 Flutter 混合 App 的有效定位方法

- 同时检查控件 `name`、`desc`、`text`，文本不一定位于 `text`。
- 跳过不可见节点，并排除 `com.android.systemui`。否则搜索“完成”可能误匹配状态栏的“充电已完成”。
- 包含匹配可能命中全屏父容器，选择匹配节点中面积最小者。
- 搜索分类需排除 `android.*` 容器名，避免把 `android.view.View` 误收为分类入口。
- 当前模拟器上 `device.touch()` 不可靠，优先使用 `poco.click(pos)` 或 Poco 节点点击。
- 无名称图标先尝试资源名，再使用已验证的归一化坐标作为 fallback。
- 不假设不同账号布局一致。分类栏、品种后缀、新手引导和列表数据都可能不同。

### 页面等待、返回与截图经验

- 不要只等待表头或页面框架。行情首页需要等实际品种行出现后再截图，否则会得到空白列表。
- 使用控件树结构指纹判断页面变化，忽略包含数字的动态文本和纯大写品种名，避免价格、时间和行情变化造成误判。
- 截图使用 `snapshot(filename=..., quality=99)`。Minicap 或 Yosemite 初始化报错后，如果 ADB 回退能生成有效截图，就不作为阻塞问题。
- 不连续盲目发送 Android BACK，否则可能退出 App。
- 搜索页通过“取消”返回。
- 自选列表引导页的“完成”只关闭引导，不退出编辑状态。
- 编辑状态通过原铅笔位置的勾选图标退出。
- 页面返回失败时先检查当前控件树和截图，不重复同一失败动作。
- 创建 Poco 前固定竖屏，避免旋转后控件树缺失、坐标变化和截图横屏。当前设备已验证尺寸为 `900x1600`。

### 采集结果的组织规则

每次运行使用独立时间戳目录，按导航层级保存截图，文件名使用三位序号、真实页面语义和必要的状态后缀。异常截图进入 `errors`，正常截图进入 `screenshots`。

`manifest.csv` 使用 `utf-8-sig`，便于 Excel 打开，字段包括：

- `screenshot`
- `navigation_path`
- `source`
- `action`
- `status`
- `fingerprint`
- `error`

交付前需要逐张打开截图，核对文件与清单一一对应，并检查是否进入范围外页面。脚本退出码为 0 不能替代内容验收。

### 已形成可复用 Skill

项目级 Skill 位于 `.trae/skills/android-hybrid-page-capture/SKILL.md`，用于后续复用 Android 混合 App 的限定页面采集流程。

Skill 已沉淀设备固定、控件查找、点击、页面等待、返回、截图、清单和验收规则。后续扩展其他主 tab 时，应先复用该流程完成小范围采集，再逐步扩大范围。

### 跨端修改邮箱用例已编写

跨端场景已由“App 修改微信”调整为“App 修改邮箱 + Web 后台校验对应字段”，因为 App 个人信息页只有邮编、邮箱、手机号，没有微信字段。App 与后台保持为两个独立 feature：

- App 用例：`flybirds_demo/features/app_update_profile.feature`
- Web 后台用例：`flybirds_demo/features/web_check_customer_profile.feature`
- 新增的 Web 文本级步骤：`flybirds_demo/pscript/dsl/step/web_steps.py`
- 步骤注册入口：`flybirds_demo/features/steps/steps.py`

两个用例及配套步骤代码已编写，但尚未在 demo 环境验证。后台菜单文案、搜索框占位符和字段实际写法需在环境恢复后按真实 DOM 校准。编写类似用例时，提供页面路径和截图可加快定位器与步骤编写。

### 视觉检测方案（设计待落地）

- 建议按“控件遮挡检测 → 文字截断检测 → 静态页基线回归”的顺序落地，静态页基线回归的维护成本最高。
- Flutter 语义节点包含 `pos`、`size`、`zOrders`、`visible`，可通过节点重叠计算实现遮挡检测。
- Flutter release 包没有 overflow 黄黑条，不能依赖该特性判断文字截断；可对比 OCR 识别结果与语义树原文，检查尾部文字是否缺失。
- 现有 `android_steps.py` 已包含 Flutter 语义节点命中处理，可在实现时复用相关逻辑。

### 全页面自动遍历方案（设计待落地）

- 采用基于 accessibility 语义树的 BFS 自研爬虫，不使用 `adb shell monkey` 作为页面遍历方案。
- Flutter、RN、原生节点统一按 `content-desc/text/resource-id/class/bounds` 五元组解析；RN 页面需要滚动探索，混合页面连续两次 dump 指纹一致后再判定稳定。
- 过滤面积超过全屏 60% 的节点，避免误触 Flutter 空白区域；表单和危险操作按钮需要黑名单或特殊处理。
- 未添加 Semantics 的 Flutter 自绘控件无法仅靠语义树识别，需要额外处理。demo 后端异常导致登录后白屏时，不应运行遍历，否则产物没有验收价值。

### 尚未完成的事项

- Web 后台邮箱核对用例已编写但仍处于暂停状态，之前出现过 `/login` 404、根路径空白及前端脚本异常，不能视为已完成。
- App 修改邮箱用例已编写但尚未最终验证；App 信息页控件无响应可能是 demo 后端挂起导致遮罩拦截，需待环境恢复后复测。
- 视觉检测和全页面自动遍历目前只有设计方案，尚未实现或验证。
- 当前完成的是登录和第一个行情 tab 的限定采集，不代表 App 全部页面已经遍历。

## 每日维护规则

后续每天将当天聊天和实践中的有效内容追加到对应日期章节：

- 记录已验证结论、关键命令、文件位置、失败原因和修复方法。
- 更新任务状态，明确哪些已完成、哪些暂停、哪些尚未验证。
- 优先补充新经验，避免重复抄写已有内容。
- 不记录密码、令牌等敏感信息，不保留无学习价值的重复调试过程。
