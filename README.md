# Flybirds 项目学习记录

用于沉淀每天聊天和实践中验证有效的经验，方便后续快速了解项目状态、复用自动化方法并避开已解决的问题。记录以可复用结论为主，不复制完整聊天过程，不记录账号密码等敏感信息。

## 掌上华医刷课：换机安装与运行（2026-11-20）

本节用于在另一台 Windows 机器上恢复「掌上华医」直接刷课环境。当前使用 **Trae + Python + ADB 直接操作模拟器**，不启动 Web 控制台。完整细节见 [掌上华医刷课环境搭建（换机配置手册）](docs/huayi_environment_setup.md)，可复用执行流程见 [掌上华医直接刷课 Skill](.trae/skills/huayi-cme-direct/SKILL.md)。

### 1. 必装软件与依赖

| 项目 | 要求 | 用途与注意事项 |
| --- | --- | --- |
| 操作系统 | Windows 10/11 | 以下命令均在 PowerShell 中执行 |
| Python | 3.10.x，本机验证版本为 3.10.11 | 勾选加入 PATH，安装后确认 `python --version` |
| Android 模拟器 | 雷电 LDPlayer 14，或其他 Android 7～11 模拟器 | 固定为 **900×1800、DPI 320、竖屏**；脚本点击坐标依赖此配置 |
| ADB | 使用模拟器自带版本 | 本机路径为 `E:\leidian\LDPlayer14\adb.exe`，换机后按实际路径修改 |
| 掌上华医 App | 包名 `com.huayi.cme` | 提前安装、登录，并确认能进入「学习 → 继续教育」和课件播放器 |

**直接刷课不需要安装第三方 Python 包。** 以下三个脚本只使用 Python 标准库，也不需要安装 Flybirds、Airtest、Poco，更不需要启动 Web 控制台：

- `flybirds_demo/pscript/huayi_course_guard.py`：视频播放守护、弹窗处理、进度判断、阶段截图和打开考试。
- `flybirds_demo/pscript/huayi_ui.py`：读取当前页面文字、坐标和选项状态。
- `flybirds_demo/pscript/huayi_cme_inventory.py`：只读盘点项目与课件状态，输出 CSV。

### 2. 可选依赖（直接模式不用安装）

只有使用旧 Web 控制台时才安装：

```powershell
python -m pip install -r huayi_console\requirements.txt
```

依赖为 `fastapi>=0.110,<0.116` 和 `uvicorn>=0.23`。控制台是可选方案，当前直接刷课流程不要启动 `启动掌上华医控制台.bat`。

只有需要用 `_ocr_image.py` 识别截图文字时才安装 OCR；播放守护、界面探针和盘点本身不依赖 OCR：

```powershell
# 明确安装 CPU 版 torch，避免下载体积更大的 GPU 依赖
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install easyocr==1.7.2 numpy pillow
```

本机 OCR 环境记录为 `easyocr 1.7.2`、`torch 2.14.0+cpu`。首次运行 EasyOCR 还需联网下载约 100 MB 的识别模型。

### 3. 新机器首次配置

1. 将项目复制到新机器，以下命令都从项目根目录执行；不要把本机账号密码写入 README 或提交到 Git。
2. 安装并启动模拟器，设置 **900×1800、DPI 320、竖屏**，开启 ADB 调试。
3. 安装并登录掌上华医；首次出现「严正声明」时手动点「我已阅读」。
4. 修改以下三个脚本顶部的硬编码 ADB 路径，否则换机后会报找不到 `adb.exe`：
   - `flybirds_demo/pscript/huayi_course_guard.py`
   - `flybirds_demo/pscript/huayi_ui.py`
   - `flybirds_demo/pscript/huayi_cme_inventory.py`

```python
ADB = r"E:\leidian\LDPlayer14\adb.exe"  # 改成新机器上的实际路径
```

5. 在 PowerShell 验证连接，并按 `adb devices` 的真实输出设置设备号：

```powershell
Set-Location D:\trae_flybirds  # 改成新机器的项目路径
$adb = "E:\leidian\LDPlayer14\adb.exe"  # 改成新机器上的实际路径
& $adb connect 127.0.0.1:5555
& $adb devices

# 本机当前为 emulator-5554；也可能显示 127.0.0.1:5555，以实际输出为准
$env:HUAYI_DEVICE = "emulator-5554"
& $adb -s $env:HUAYI_DEVICE shell getprop sys.boot_completed
```

`sys.boot_completed` 应返回 `1`。`HUAYI_DEVICE` 只对当前 PowerShell 窗口有效；新开窗口需要重新设置。三个脚本未设置该变量时默认使用 `127.0.0.1:5555`。

6. 先运行界面探针，能输出当前 App 的文字和坐标即表示 Python、ADB 路径及设备号基本可用：

```powershell
python flybirds_demo\pscript\huayi_ui.py --state
```

### 4. 直接刷课的使用顺序

#### 4.1 盘点课程（只读，可选）

先把 App 手动停在课程列表页，顶部必须能看到「请输入项目名称」。**盘点会操作 App，与播放守护互斥，不能同时运行。**

```powershell
New-Item -ItemType Directory -Force "$PWD\app_page_captures\huayi_course" | Out-Null
python flybirds_demo\pscript\huayi_cme_inventory.py `
  --screens 12 `
  --out "$PWD\app_page_captures\huayi_course\inventory.csv" `
  --lessons-out "$PWD\app_page_captures\huayi_course\inventory_lessons.csv"
```

不传 `--out` 时默认写入 `d:\trae_flybirds\app_page_captures\huayi_course\inventory.csv`；新机器项目不在该路径时，应像上面一样显式传路径。盘点只读课程信息，不播放、不答题、不选课。

#### 4.2 优先处理待考试课件，再播放视频

启动播放守护前，必须先手动进入目标课件的播放器页并确认视频能播放。同一时刻只运行一个守护，运行期间不要人工同时操作 App，也不要执行课程盘点。

以下是第三课的完整命令示例；换课件时替换序号、课程名、总秒数、已播秒数和项目目录：

```powershell
$env:HUAYI_DEVICE = "emulator-5554"  # 以 adb devices 输出为准
python -u flybirds_demo\pscript\huayi_course_guard.py `
  --lesson-index 3 `
  --lesson-name "骨质疏松症的中医诊疗" `
  --duration 2106 `
  --played 0 `
  --out-root "$PWD\app_page_captures\huayi_course\tasks\常见骨慢病的诊治及临床实践" `
  --log "$PWD\app_page_captures\huayi_course\guard.log" `
  --max-hours 2
```

参数说明：

- `--duration` 是课件总秒数；`--played` 是进入时的已播秒数，已播不准时脚本会按 TS 分片自校正。
- `--out-root` 是某个项目的任务根目录，脚本会在其下创建 `<序号>_<课程名>` 子目录。
- `--max-hours` 是最长运行时间；不传 `--log` 时默认写到 `d:\trae_flybirds\app_page_captures\huayi_course\guard.log`。
- 日志进度以 logcat **最后一个** `_数字.ts` 分片为准，不能取历史最大分片号；每个分片约 8.57 秒。
- 守护只负责播放、处理提示弹窗、判断结束、截图和尝试打开考试，**不答题、不交卷、不申请证书**。

### 5. 考试边界与人工核对

- 优先完成已经「待考试」的课件，再继续后续视频；项目页标签只能参考，真实状态以课件进度和考试结果为准。
- 课件仍显示「学习中」时，点击「考试」可能不会跳转，这通常是学习状态限制，不是模拟器或 ADB 故障。完成视频后才进入考试。
- 进入 `TestQuestionsActivity` 或出现「交卷 / 答题状态 / 提交」后，播放守护停止点击。此时通过 Trae/ADB 逐题操作，用界面探针读取题干和选项：

```powershell
python flybirds_demo\pscript\huayi_ui.py --state
```

- 题目顺序可能随机，必须按题干文本匹配答案，不能直接复用上一次的选项位置。
- 交卷前逐题核对全部题目均已作答，并用 `--state` 确认目标选项为 `checked="true"` 或 `selected="true"`；交卷后确认页面明确显示「考试通过」。
- 不自动申请证书，不执行与刷课无关的账号、支付或资料修改操作。

### 6. 日志、截图和盘点结果

- 播放日志：`app_page_captures\huayi_course\guard.log`，或由 `--log` 指定的位置。
- 每个课件的截图：`app_page_captures\huayi_course\tasks\<项目名>\<序号>_<课程名>\`。
- 阶段截图包括：开始、中间、结束、考试开始、考试结果；已有截图不覆盖。
- 项目汇总：`app_page_captures\huayi_course\inventory.csv`。
- 课件明细：`app_page_captures\huayi_course\inventory_lessons.csv`。

### 7. 明天换机后的自检清单

- [ ] `python --version` 显示 3.10.x。
- [ ] 模拟器为 900×1800、DPI 320、竖屏，App 已安装并登录。
- [ ] 三个脚本的 `ADB` 均改为新机器路径，`adb devices` 中设备状态为 `device`。
- [ ] 当前 PowerShell 的 `HUAYI_DEVICE` 与 `adb devices` 输出一致，`sys.boot_completed=1`。
- [ ] `huayi_ui.py --state` 能读取当前页面文本和坐标。
- [ ] 手动进入课件后能正常播放，Activity 为 `MediaPlayNewActivity`。
- [ ] 守护运行约 2 分钟后，日志中的已播秒数和 TS 分片持续增长，截图目录能正常创建。
- [ ] 盘点只在课程列表页启动，且没有与播放守护同时运行。
- [ ] 未完成视频前不强行进入考试；考试后看到「考试通过」才计为完成。

## 文档先行与执行门禁（强制）

每次任务必须先完成类似产品经理的需求分析，再完成类似架构师的技术设计，核对一致后才能开始实施。不得以聊天记录、口头理解或既有代码代替需求文档和技术设计文档。

1. **需求分析先行**：明确目标、范围、页面与交互覆盖、安全边界、输出物和验收标准，并写入对应需求文档。
2. **技术设计随后**：依据需求编号逐项设计实现方式、状态恢复、异常处理、结果核销和验证方法，并写入独立技术设计文档。
3. **一致性核对**：确认需求、技术方案和验收用例一一对应；文档未完成或存在冲突时，不得修改实施代码、操作设备、切换语言或开展正式采集。
4. **需求变化先暂停**：执行中如发现遗漏、范围调整或理解偏差，立即停止相关实施，先更新需求文档，再同步技术设计；重新核对一致前不得继续。
5. **按文档实施与验收**：实施过程中以文档为唯一基线，完成后按需求编号和验收标准复核，明确完成项、失败项、跳过项及文档偏差，不得用脚本退出码代替内容验收。
6. **变更确认**：涉及采集范围、安全边界或资金、交易、账号等危险动作的变更，必须获得用户明确确认后才能实施。

当前“我的”栏目采集使用以下两份独立文档：

- 需求文档：[“我的”栏目截图采集与识别需求文档](docs/mine_capture_requirements.html)
- 技术文档：[“我的”栏目截图采集与识别技术设计](docs/mine_capture_technical_design.md)

两份 1.3 文档已于 2026-11-06 确认，采集代码按文档实施。已有截图和脚本只能作为现状参考，是否满足文档以当次计划、清单和覆盖审计结果为准。

## 项目环境

- 工作目录：`D:\trae_flybirds`
- Android 设备：雷电模拟器 `emulator-5554`
- 测试 App：`com.wetrade.crm.trial`
- 启动 Activity：`com.wetrade.crm.MainActivity`
- App 技术形态：React Native 与 Flutter 混合，不能按单一原生或 Flutter 页面处理
- 主要自动化工具：Flybirds、Airtest、Poco、ADB

## 本地凭据

按本文约定，账号密码不写进 README，统一存放在本机文件 `D:\trae_flybirds\local_credentials.env`（已加入 `.gitignore`，不会提交）。文件内的键：

- `APP_ACCOUNT` / `APP_PASSWORD`：Android App（WT-demo）登录账号
- `CRM_EMAIL` / `CRM_PASSWORD`：后台 CRM（`demo-console.crmtest.org`）登录账号

需要时在 PowerShell 里一次性载入环境变量：

```powershell
Get-Content D:\trae_flybirds\local_credentials.env |
  Where-Object { $_ -and -not $_.StartsWith("#") } |
  ForEach-Object { $k, $v = $_ -split "=", 2; Set-Item "env:$k" $v }
```

注意：

- 该文件只留在本机，不要提交、不要贴进聊天或截图；采集清单、截图中也不得出现密码。
- `flybirds_demo/pscript/crawl_login_market.py` 和 `flybirds_demo/pscript/dsl/step/strategy_list.py` 里仍内置了相同的默认值，修改密码时需要同步更新这两处，避免脚本用到旧密码。
- App 在不同环境包名不同，已出现过 `com.wetrade.crm.trial` 与 `com.wetrade.crm.demo`，登录前先确认当前安装的包名。

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

## 2026-11-07

### “我的”栏目升级为所有页面通用的采集标准

本轮确认的核心要求是：消息中心的一次性坐标标定不能成为单页特例，所有页面都统一执行“取数 → 发现 → 计划 → 执行 → 恢复 → 覆盖审计”，固定注册表仅作兜底。实现位于 `flybirds_demo/pscript/crawl_mine_lang.py`，需求与技术基线仍为上述两份 1.3 文档。

- 统一取数层 `page_items()` 合并控件树文本、几何与可点击父节点；稳定文案少于 3 条或没有可点击节点时，以 OCR 补充带坐标的文本块，目标来源记录为 `tree`、`ocr` 或 `fixed`。
- 每屏无条件运行 `discover_generic()`，发现 Tab、选择器、同构卡片、轮播、按钮和弹层。卡片抽样前 3 条，其余记录抽样跳过；固定项未命中记 `failed`，已登记文案或区域不重复登记。
- 点击变化采用“控件指纹变化 OR 图像差分大于 1% OR OCR 文本集合变化”。canvas 页面必须在点击前保存图像和签名，避免把点击后的 OCR 当成基线。
- 首页自动轮播曾导致整页指纹持续变化，表现为滚动位置恢复失败和补充预扫描反复触发。现以页头 6%~30% 区域的 `scroll_hash()` 判断滚动位置，并为补充预扫描增加次数上限及无新增目标后的空转保护。实机两帧差分还确认顶部/底部回弹会在手势后短暂改变哈希，纵滑后统一等待回弹结束再比较，避免连续滑动反复触发动画。
- 启动走查还发现两处入口问题：PocoService 初始化可能盖住目标 App，初始化后必须恢复 App 前台；`clean_labels()` 会过滤底部导航描述，进入“我的”必须检查原始节点文本，不能在过滤后的 `labels` 中找“第 5 个标签”。桌面或 PocoService 页面禁止继续盲发 BACK。
- 每页审计新增发现统计和 `unplanned_regions`；完整交付要求 `pending=0`、`planned=ok+failed+skipped`、无未规划动作或区域，并有有效截图证据。`001_逐屏.png` 表示同一页面纵向滚动采集的第 1 屏，不代表整个采集任务只有一张图。
- 安全边界保持不变：不交易、不提交入出金或转账、不修改资料或密码、不删除、不注销、不退出登录，也不创建 Git 提交。

本次重构后的 18 个离线测试和 `py_compile` 已通过。OCR 清单现保留 `page_id/target_id/visit_key` 等标识，`compare_lang_text.py` 额外生成 `language_pair_report.csv`，以双向全集列出 `paired`、`paired_pending_review`、`zh_only`、`ja_only`，不以路径交集代替完整配对。中文、日文设备结果必须以各自当次 `coverage_report.json`、`page_plan.csv` 和截图复核为准，不能用离线测试代替设备验收。

消息中心专项进一步确认：“重要通知/资金动态/账户动态/品牌动态”是进入独立列表页的导航入口，不是同页 Tab；分类详情不得递归登记自身，每个分类使用独立业务键。恢复比较会忽略合并到入口文案中的未读数及金额，轮播识别不会再把日期前缀当成 `n/m`。覆盖审计按已计划坐标去重，并排除消息正文、状态指示和中央页头；其中 `消息中心(2969)` 曾因未读数改变标题宽度而被误报，现已修复。2026-11-07 消息专项结果为 10 个目标全部 `ok`，`unplanned_regions=0`、`unplanned_actions=0`，四个分类均能进入、截图并逐级返回“我的”。完整中文、日文采集及 OCR 对照仍以各自最终运行报告为准。后续全量预检还发现系统“应用信息”页越界、通知状态开关及密码/生物识别设置缺少拦截，以及发现与执行取数层不一致导致的 `auto_002 目标未命中`。现已在每次动作前后核验前台包名，外部应用不预扫描、不点击并立即恢复目标 App；通知开关、手势密码、Google Authenticator 和系统卸载/清数据/强制停止等只登记禁止状态。执行重定位复用 `page_items()` 的合成父节点与 OCR 结果，页面失败会写明具体门禁原因。此前中止轮仅作问题基线，不作为验收结果。

## 2026-11-09

### “我的”栏目采集：三次中断的根因与修复

当天中文采集连续中断三次，原因不是同一个，最终都定位到可复现的证据：

1. **首屏复核死循环（脚本缺陷）**：`recheck_done_page()` 判定“已完成页面无新增”时只返回 `duplicate`，没有把来源目标置为终态，执行器会一直重试同一个 pending 目标。表现为日志反复打印“首屏复核无新增：我的 > 消息”并连续 BACK，70 分钟零推进。修复：无新增也必须把来源目标写为 `skipped + duplicate` 并补清单；执行器再加防死循环门禁，同一 `target_id` 连续执行超过 2 次仍为 pending 时按 `skip_class=resource` 核销。
2. **模拟器中途重启（环境问题）**：`13:47:19` LDPlayer 进程重启，`13:47:38` 日志出现 `device 'emulator-5554' not found`，随后 Poco 端口 `28361` 连接被拒，整轮退化为 `ok 4 / failed 24 / skipped 62`。这类轮次直接判废，不修改代码。
3. **弹层恢复误判引发 BACK 刷屏（脚本缺陷）**：客服 FAQ 的弹层在页面中部打开，关闭后页面仍停在滚动位置，`搜索/人工客服` 顶部锚点不在屏内被判成“来源页内容变化”；补充预扫描又刚好达到上限，恢复失败后每个待执行目标各发 2 次 BACK，形成刷屏并把 App 退到桌面。修复：关闭弹层后先 `scroll_top()` 再核对锚点；“补充预扫描次数已达上限”只算预算耗尽，不再当作恢复失败；同一页 `restore_failed` 后剩余目标直接核销，只允许一次恢复尝试。

三处修复均在 `flybirds_demo/pscript/crawl_mine_lang.py`，离线回归 `test_crawl_mine_lang_offline.py` 保持 0 失败。

### 设备与截图注意事项

- 系统 PATH 里没有 adb，LDPlayer 自带 `E:\leidian\LDPlayer14\adb.exe`；重连顺序为 `kill-server` → `start-server` → `connect 127.0.0.1:5555` → 确认 `sys.boot_completed=1`。
- 采集运行期间禁止执行任何 adb 命令，会重起 adb server 导致 Airtest 会话掉线。
- 模拟器重启后 `/data/local/tmp` 权限异常会让 minicap/Yosemite 安装失败（`INSTALL_FAILED_MEDIA_UNAVAILABLE`），截图自动降级为 `adb screencap`，采集可继续，只是变慢。

### 当天采集进度（run `20261109_140928`，未验收）

- 计划 258 项：`ok 23`、`failed 13`、`skipped 222`、`pending 0`，`complete=false`。
- 跳过构成：`safety 105`（危险/禁止操作，预期）、`resource 80`（其中 79 项为“此前页面状态恢复失败，停止后续点击”的级联跳过）、`depth_limit 21`（第 4 层边界，预期）、`error 27`、`duplicate 2`。
- 已稳定产出的页面：我的首页、消息四个分类、客服 FAQ/人工会话、设置、消息通知（声音/语言/系统日志/个人信息）、个人信息、余额显隐切换态；稳定证据累计 54 张，按导航路径存放。
- 未完成与待补：通知页预扫描未完成（四个分类固定目标未登记）、客服两个弹层预扫描未完成、“资金记录页没有采集计划”（存款/取款/转账/资金明细未进入）、12 项“点击无跳转”、2 处“未规划区域”（个人信息/地址信息）。
- 结论：中文“我的”栏目尚未通过验收，需在修复后的下一轮重跑；日文（ja-JP）采集与 OCR 对照尚未开始。

## 2026-11-10

### 人工客服截图错误：根因与修复

`我的/客服/人工客服/001_逐屏.png` 曾拍成 FAQ 搜索态（`请输入问题/热门问题/有帮助`），根因不在点击本身，而在证据与恢复链：

1. `faq.human` 采用 `evidence=first_screen`，点击后只要页面变化就截图，没有“是否真的进入会话”的内容校验。
2. 搜索态保留了 FAQ 页大量文案，`is_overlay()`（保留旧文案 ≥50% 且指纹变化）把会话页误判为弹层，节点登记为 `mine.customer_service.popup.faq.human`，错图落盘后被标记 `done`，后续轮次按 duplicate 跳过。
3. 触发条件是同一页先执行的搜索动作失败（搜索框实际在页面顶部约 5%，旧识别区域从 10% 开始），页面停在搜索态后紧接着点了人工客服。

已实施：会话内容门禁（必须命中 `在线客服/请输入内容/结束会话` 中至少 2 项）、FAQ 搜索态排除、会话页豁免弹层判定、搜索动作无论成败都退出搜索页并校验、人工客服先于搜索执行并加前置状态门禁。会话页进一步改为终端页：只采首屏、不滚动、不登记聊天内容、不点「结束会话」。

### 恢复链与审计口径修复

- 客服页恢复锚点补充 `常见问题/人工客服/新增一级分类/无二级分类`，不再只依赖无字搜索图标。
- `restored_page()` 改为“锚点命中或整页相似度”；一次返回未恢复且前台仍在本应用时允许再退一层。
- `replay_to_parent()` 先在应用内退回「我的」首页再重放路径，只有真正重启才消耗 `MAX_RESTARTS`；重启后必须 `ensure_mine_home()` 再重放。
- 会话页等终端页不做未规划区域审计；未规划区域只统计可证明可点击的控件，纯 OCR 文本不计入。

设备探针已验证：`我的 → 客服 → 人工客服 → 返回客服 → 返回我的` 全链路可恢复；`人工客服` 截图 OCR 稳定命中会话特征。离线回归 `test_crawl_mine_lang_offline.py` 保持 `FAILURES: 0`。

### 当天采集进度（run `20261110_165211`，未验收）

- 计划 373 项：`ok 67`、`failed 24`、`skipped 282`、`pending 0`，`complete=false`，`restarts=1`。
- 已达成：`zh-CN|mine.customer_service|conversation|default` 节点为 `done`，累计 7 张有效会话截图；人工客服截图（16:57:57）为真实会话页。
- 未完成：
  1. `settings` 仍为 `partial`，报 `未规划区域=2:设置,设置`；`card_01_01_01` 递归采集失败后，“我的”页 `restore_failed` 未被清除，导致 `agent/profile/copytrade/points/club/deposit/withdraw/transfer/funds` 十个一级入口全部 skipped（“此前页面状态恢复失败，停止后续点击”）。
  2. `mine.customer_service` FAQ 页仍为 `partial`（会话子页已 `done`），客服 FAQ 分类会按业务页深度展开，单支耗时约 60～80 分钟。
  3. 设置子页（个人信息/安全管理）仍有未规划区域，`unplanned_regions=31`。
- 明日起点：先修“子页恢复失败后未立即恢复「我的」并清除 `restore_failed`”，再处理设置页 `设置,设置` 重复文本的区域归属，最后重跑并验收。

采集命令（cwd=`d:\trae_flybirds`，日志 `%TEMP%\crawl_zh_rN.log`）：

```powershell
$env:CRAWL_LANG='zh-CN'; $env:CRAWL_DEVICE='127.0.0.1:5555'; python -u d:\trae_flybirds\flybirds_demo\pscript\crawl_mine_lang.py
```

## 2026-11-11

### 当日修复

1. **子页不再预置下拉**：进入子页时页面本来在顶部，预扫描只在「我的」首页执行 `scroll_top()`；子页直接从第 1 屏开始，后续用上滑翻屏，避免误触下拉刷新/回弹。
2. **恢复失败不再级联**：每次新的恢复失败都会重置 `restore_attempts`（`mark_restore_failed`），一次失败只影响当前目标；`recover_page(我的)` 增加“重启后回到我的首页”兜底，成功即清除 `restore_failed`。日志已多次出现「重启后已恢复我的首页，继续执行剩余目标」。
3. **页头标题不计未规划区域**：页面上下文补充 `title`（此前只有地图节点有标题），审计可按标题链最后一段排除页头文本，修掉设置页 `未规划区域=2:设置,设置`。
4. **安全边界**：`清理缓存` 加入禁止点击名单。

### 阻塞与恢复

- run `20261111_100547` 期间 App 弹出「您当前账号无效，请切换账号」，弹窗拦截返回手势，导致设置页与恢复链失败。采集脚本按安全规则不切换账号，需人工重新登录后继续。
- 重新登录（账号 `76100248`）并冷启动 App 后恢复正常；采集前用只读探针确认界面文本与账号状态。

### 当天采集进度

- run `20261111_133952`（跑满 240 分钟预算）：planned 861、`ok 136`、`failed 91`、`skipped 634`、`complete=false`。恢复链修复生效，十个一级入口均实际执行。
- run `20261111_175624`（人为中止，未出 coverage）：manifest `ok 31 / failed 24 / skipped 54`；`mine.settings` 已变为 `done`。
- 页面地图现状：`done 30`、`partial 58`、`failed 6`、`collecting 4`（中止遗留，下次启动按规则转 `partial`）。

### 明日待办

1. `club` 仍失败：`回到顶部失败`（2 次），检查该页是否无滚动容器或回顶手势被弹层拦截。
2. `profile` 未规划区域 `个人信息/地址信息/社交账号`，需确认这些文本是否可点击行；不可点击则不计入交互证据。
3. 弹层预扫描不稳定：`弹层预扫描时面板未保持打开`、`弹层在预扫描后已关闭`、`预扫描=incomplete`，需在预扫描前后校验面板仍然打开。
4. `目标未命中` 5 次，按页面逐一核对定位别名。
5. 修完后重跑 zh-CN 至 `complete=true`，再验收人工客服截图与十个一级入口。

设备与进程状态：采集进程已手动停止，模拟器停在 App 内，未执行其他操作。

## 2026-11-13

### 长列表最多 3 屏

所有列表页纵向预扫描最多 3 屏（`CRAWL_LIST_SCREENS=3`），到上限后再滑一次确认有新增即写 `scroll_capped=true` 并按 `complete` 收口，不再判 `incomplete`。两份文档已同步“滚到底”表述（仅保留下拉选项面板内滚到底），离线回归新增 `test_long_list_survey_caps_at_three_screens`。

### 安全口径放宽：入口全覆盖，只拦不可逆动作

用户口径：所有页面涉及的功能都要采集，放宽“危险词即不采集”的约束；可以输入但不保存，退出/注销最后点击。实现改为三档：

- `allow_entry`：修改密码、重置密码、手势解锁、Google Authenticator、绑定/解绑等入口一律进入首屏截图。
- `deferred`：退出登录、注销账号、结束会话只登记；本轮全部页面采集结束后按 `navigation_path` 重放取证，不点最终确认，顺序为普通延迟项 → 注销 → 退出登录。
- `hard_blocked`：保存、提交、发送验证码、支付/下单/买卖、删除确认、清空、清除数据/缓存、卸载、强制停止、切换语言。状态开关仍只按 `record_only` 记录，不切换。

同步落地：发现阶段按分级落计划（不再整类跳过危险词入口）；`page_plan.csv` / `manifest.csv` 新增 `label` 列，动态目标可直接追溯真实文案；未规划区域从阻断项降为 `warnings`，`coverage_report.json` 新增 `warnings/warning_total`，页面完成只看页面身份、有效截图、恢复成功、无未登记动作和预扫描完成；轮末残留 `deferred` 计入未完成项。

文档：`docs/mine_capture_requirements.html` 1.8、`docs/mine_capture_technical_design.md` 1.10；离线回归 `FAILURES: 0`。

### 增量补采：缺口盘点与计划

依据 `20261112_095343` 的 `coverage_report.json` / `page_plan.csv` / `page_map.json` 盘点，主要缺口：

| 区域 | 现状 | 主要缺口 |
| --- | --- | --- |
| 我的首页 | 部分 | 轮播三态、余额显隐、wallet 入口、客服入口、会员俱乐部入口、头像/用户名/V15/IB1.0 探测无有效证据 |
| 设置 / 我的信息 | partial | 安全管理仅手势解锁有首屏；修改密码、Google Authenticator 被旧安全规则整类跳过；注销未执行；设置首页 5 个入口被跳过 |
| 会员俱乐部 | partial | 预扫描未到底、恢复失败；18 个入口 resource 跳过；30 个未规划区域 |
| 代理专区 | partial | 6 个固定目标未命中；预扫描未到底；30 个未规划区域 |
| 跟单社区 | partial | 策略列表时间预算耗尽；21 个“跟随”按安全规则跳过 |
| 积分商城 | 无节点 | 时间预算耗尽，整类缺失 |
| 资金明细 | partial | 转账 Tab 未采；月份、筛选跳过；交易记录 planned=0 |
| 存款/取款/转账 | 无节点或 partial | 存款、转账点击无跳转，钱包弹层未独立核销 |

补采按范围分批执行，已完成且证据有效的页面跨轮 `skipped_done`，不重新预扫描或截图；`CRAWL_ROOTS=home` 只采首页固定项，范围外的首页动态卡片记 `skip_class=scope`。中间批次不执行退出/注销（`CRAWL_DEFERRED=auto`），收尾轮再执行。

| 批次 | 范围 | 目标 |
| --- | --- | --- |
| A 首页 | `CRAWL_ROOTS=home` | 轮播三态、余额显隐、wallet/客服/会员俱乐部入口、头像/用户名/徽标探测 |
| B 账号与安全 | `CRAWL_ROOTS=settings,profile` | 安全管理 6 项、设置首页 5 个入口、消息通知开关记录、我的信息根入口 |
| C 内容区 | `CRAWL_ROOTS=agent,copytrade,points` | 代理专区 6 项、跟单社区策略列表、积分商城 |
| D 俱乐部与资金 | `CRAWL_ROOTS=club,funds,deposit,withdraw,transfer` | 俱乐部列表与入口、资金明细 3 Tab/月份/筛选、钱包弹层 |
| E 收尾 | `CRAWL_ROOTS=settings CRAWL_DEFERRED=1` | 注销、退出登录首屏（最后执行） |

命令示例（每批单独一轮，均从“我的”首页启动）：

```powershell
$env:CRAWL_LANG='zh-CN'; $env:CRAWL_DEVICE='127.0.0.1:5555'; $env:CRAWL_ROOTS='home'
python -u flybirds_demo\pscript\crawl_mine_lang.py
```

已知仍需现场校准：代理专区固定目标定位、存款/转账无跳转、弹层初始态恢复。补采轮 `complete` 恒为 `false`，整体验收以缺口清单清零、各轮证据合并为准。

### 补采执行记录

- `20261113_101948` 批次 A（`home`）：`planned 38 / ok 6 / failed 7 / skipped 25`。补齐客服入口、FAQ 搜索、头像、用户名；钱包恢复、余额显隐、轮播仍失败。轮播“预扫描无 locator 提前判失败”已修复，改为执行阶段实时识别。
- `20261113_104423` 批次 B 首轮中止：轮播卡片打开后进入营销页并反复刷新，单页占用过久。已修复：轮播“打开”目标只登记不展开；非 `home` 批次跳过首页固定项；新增单页时间上限（`CRAWL_PAGE_MIN`，默认已放宽到 20 分钟），超时剩余目标记 `skip_class=resource`。离线回归 `FAILURES: 0` 后重跑批次 B。
- `20261113_134611` 批次 B 重启后完成，但未通过：`planned 123 / ok 19 / failed 4 / skipped 100`，ok 全落在“设置 > 消息通知”，设置根与安全管理未采到，并误入语言页；恢复链在“返回未回来源页 + 重启后未回首页”处断开。已加：语言页按内容兜底只取证、桌面/PocoService 时主动重新拉起 App。待设备在线后只重跑 `settings,profile`。

## 每日维护规则

后续每天将当天聊天和实践中的有效内容追加到对应日期章节：

- 记录已验证结论、关键命令、文件位置、失败原因和修复方法。
- 更新任务状态，明确哪些已完成、哪些暂停、哪些尚未验证。
- 优先补充新经验，避免重复抄写已有内容。
- 不记录密码、令牌等敏感信息，不保留无学习价值的重复调试过程。
