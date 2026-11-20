# 掌上华医刷课环境搭建（换机配置手册）

目的：在另一台 Windows 机器上，用最短步骤复现「掌上华医（com.huayi.cme）自动播放课件 + 自动进考试 + 按规范截图」这套流程。
本文只描述环境与操作；业务判定规则见最后一节。

---

## 1. 需要准备的东西

| 项目 | 要求 | 说明 |
| --- | --- | --- |
| 系统 | Windows 10/11 | 脚本用 PowerShell 调用 adb |
| 模拟器 | 雷电模拟器 LDPlayer 14（或任意 Android 7~11 模拟器） | 分辨率固定 **900×1800 竖屏**；脚本里的点击坐标都是这个分辨率下的绝对值 |
| adb | 随模拟器自带 | 默认路径 `E:\leidian\LDPlayer14\adb.exe`，换机需改 |
| Python | 3.10.x（本机 3.10.11） | 守护脚本只用标准库 |
| App | 掌上华医 `com.huayi.cme` | 装好并登录课程账号 |
| OCR（可选） | easyocr 1.7.2 + torch 2.14.0+cpu + numpy + Pillow | 只有读播放器时间、读截图文案时需要 |
| 控制台（可选） | fastapi + uvicorn | 只有用 Web 控制台时需要，见 4.6 |

> 注意：`_ocr_image.py` 名字像 PaddleOCR，实际用的是 **easyocr**，首次运行会下载识别模型（约 100MB），需要能联网。

---

## 2. 安装步骤

```powershell
# 1) 安装 Python 3.10，确认可用
python --version

# 2) 仅当需要 OCR 时安装（守护脚本本身不需要）
pip install easyocr==1.7.2 numpy pillow
# torch 会自动作为依赖装上；如装成 GPU 版过大，可改装 CPU 版：
# pip install torch --index-url https://download.pytorch.org/whl/cpu
```

模拟器：

1. 新建/启动模拟器，**分辨率设为 900×1800、DPI 320**，竖屏。
2. 打开模拟器内置 adb 调试（默认开启），确认端口：雷电一般是 `127.0.0.1:5555`。
3. 安装 App 并登录，进入「学习 → 继续教育」能正常打开项目页。
4. 首次启动若弹「严正声明」，点「我已阅读」关掉。

连接验证：

```powershell
E:\leidian\LDPlayer14\adb.exe devices
# 期望看到 127.0.0.1:5555   device
E:\leidian\LDPlayer14\adb.exe -s 127.0.0.1:5555 shell "dumpsys window | grep mCurrentFocus"
```

---

## 3. 换机必须改的配置

三个脚本里 **ADB 路径是硬编码的**，换机第一件事就是改：

- `flybirds_demo/pscript/huayi_course_guard.py`
- `flybirds_demo/pscript/huayi_ui.py`
- `flybirds_demo/pscript/huayi_cme_inventory.py`

```python
ADB = r"E:\leidian\LDPlayer14\adb.exe"          # 改成新机器的 adb 路径
DEVICE = os.environ.get("HUAYI_DEVICE", "127.0.0.1:5555")   # 可用环境变量覆盖
```

设备号可用环境变量临时覆盖，不必改代码：

```powershell
$env:HUAYI_DEVICE = "127.0.0.1:5555"
```

另外两处输出路径按需改：

- 日志：`--log`，默认 `d:\trae_flybirds\app_page_captures\huayi_course\guard.log`
- 任务目录：`--out-root`，每个课件会在其下自动建 `<序号>_<课程名>\`

---

## 4. 脚本清单与用法

### 4.1 播放守护（主力）

```powershell
python flybirds_demo\pscript\huayi_course_guard.py `
  --lesson-index 6 `
  --lesson-name "儿童鼻病外治技术之应用" `
  --duration 3525 `
  --played 1900 `
  --out-root "d:\trae_flybirds\app_page_captures\huayi_course\tasks\中西医结合诊治儿童鼻科疾病新进展" `
  --max-hours 2
```

| 参数 | 含义 |
| --- | --- |
| `--lesson-index` / `--lesson-name` | 只用于建任务目录与截图文件名 |
| `--duration` | 课件总秒数；日志里取不到时必传 |
| `--played` | 进入时的已播秒数；**传错不会卡死**（脚本会用 ts 分片号自校正） |
| `--out-root` | 任务根目录，建议按项目名分一层 |
| `--next-name` / `--next-index` | 考完自动打开下一个课件；不传则考完即停 |
| `--interval` | 轮询秒数，默认 60 |
| `--max-hours` | 最长运行小时数，默认 4 |

运行前提：**App 已经在播放器页（MediaPlayNewActivity）且视频正在播放**。脚本负责处理弹窗、卡顿恢复、结束判定、五张截图和自动点「考试」，但**不答题、不交卷**。

### 4.2 成绩页识别

出现「考试结果 / 考试通过 / 考试未通过」时，脚本自动截「考试结果」并退出（或切下一课）。所以答题必须在它下次轮询前完成，或接受它先退出、你答完再手动收尾。

### 4.3 选课盘点（只读）

起点：课程列表页（顶部有「请输入项目名称」）。

```powershell
python flybirds_demo\pscript\huayi_cme_inventory.py --screens 12
# 输出 app_page_captures\huayi_course\inventory.csv          （项目汇总）
# 输出 app_page_captures\huayi_course\inventory_lessons.csv （课件明细）
```

旧版 `inventory.csv` 可以继续展示项目，但只有重新执行盘点后才会生成课件明细。课件状态里的「播放至…」会归一为「播放中」；「待考试」只是项目页标签，不可信，仍以真实播放进度为准。

### 4.4 界面探针（排障用）

```powershell
python flybirds_demo\pscript\huayi_ui.py
# 逐行输出「x,y  文本」，用于定位按钮、读题干、核对选项是否选中
python flybirds_demo\pscript\huayi_ui.py --state    # 额外打印 checked/selected 的节点
```

### 4.5 截图 OCR（可选）

```powershell
E:\leidian\LDPlayer14\adb.exe -s 127.0.0.1:5555 shell screencap -p /sdcard/a.png
E:\leidian\LDPlayer14\adb.exe -s 127.0.0.1:5555 pull /sdcard/a.png "$env:TEMP\a.png"
python flybirds_demo\pscript\_ocr_image.py "$env:TEMP\a.png"
```

### 4.6 本地控制台（刷课管理页面）

Windows 下可直接双击仓库根目录的 `启动掌上华医控制台.bat`：服务已在运行就直接打开页面；未运行则启动服务窗口，等待就绪后打开浏览器。运行期间不要关闭 `Huayi Console Server` 窗口。首次使用仍需先完成下面的依赖安装与 `.env` 配置。

```powershell
python -m pip install -r huayi_console\requirements.txt   # fastapi + uvicorn
Copy-Item huayi_console\.env.example huayi_console\.env   # 按本机改 ADB_PATH / 设备号
python huayi_console\app.py                               # 浏览器打开 http://127.0.0.1:8765
```

- 配置只读 `huayi_console/.env`（`ADB_PATH`、`HUAYI_DEVICE`、`CONSOLE_PORT`），改完重启服务生效；系统环境变量优先于该文件。
- 控制台只把 `huayi_course_guard.py` 当子进程调起，不改变播放判定逻辑；「暂停」= 播放器暂停 + 挂起守护进程，「继续」= 恢复进程 + `keyevent 126`。
- 配置的设备号不在线、且只连了一台设备时，控制台会自动改用该设备号，并在事件流里提示。
- 运行数据存 `huayi_console/console.db`（已 gitignore），截图仍落在任务根目录。
- **课件盘点**：先将 App 停在课程列表页，再点「重新盘点」。盘点会操作 App 遍历项目，与播放守护互斥；完成后展示项目汇总和课件明细。
- **任务队列**：在课件明细中勾选并入队，可上移、下移、跳过、重试、删除；「开始下一项」会启动真实播放，操作前先确认设备与课件页面正确。
- 队列检测到成绩页后会标记完成并连播下一项；普通播放结束会标为「待考试」并暂停队列，等待人工考试或人工确认完成；手动停止会退回排队，异常退出会标为失败并暂停。
- 队列页显示预计播放时长和实际耗时汇总。盘点明细没有时长时显示「时长未知」，守护仍会从播放器日志自校正；控制台不会自动提交证书。

---

## 5. 运行守则（判定逻辑，换机后别改错）

1. **进度以 ts 分片为准**：logcat 里 `_(\d+)\.ts` 的序号 × 约 8.57 秒 ≈ 播放位置；约 7 片/分钟。静态 PPT 也会涨分片，所以「分片不动」才是真停。
2. **分片序号取最后一条，不取最大值**。上一个课件的残留序号会把新课误判成快播完。
3. **结束判定**：出现「谢谢观看」或「请点击左下角"考试"」提示 → 直接按结束处理；否则要分片停滞 ≥5 分钟 **且** 进度 ≥85% 才算结束，不足 85% 一律当卡顿恢复。
4. **不要点「确定」**：播放器结束时那个提示框点确定会退回项目页、把播放器关掉。`POPUP_WORDS` 里刻意不含「确定」。
5. **测验页只观察**：出现「交卷/答题状态/提交」或 Activity 为 `TestQuestionsActivity`/`WebActivity` 时，脚本停止一切点击，只截图、抄题干。
6. **弹窗**：约每 15 分钟一次「温馨提示 / 学习是马拉松…」+「好的，知道了」，按子串匹配点击。
7. **恢复播放用 `keyevent 126`（MEDIA_PLAY）**，不要用 85（TOGGLE_PAUSE），否则可能把正在播的按暂停。
8. **答题必须按题干文本匹配**，题目顺序每次随机；交卷前用 `--state` 核对 `checked="true"`。
9. **完成规则**：视频播到结束 + 课后测验通过 = 已完成。只答题不改进度；项目页「待考试」不可信，必须进项目页读真实进度。

---

## 6. 截图规范

每个课件一个目录，5 张图，文件名 = 课程名 + 阶段：

```
app_page_captures\huayi_course\tasks\<项目名>\<序号>_<课程名>\
    课程名_开始.png
    课程名_中间.png        # 播放到 50%
    课程名_结束.png
    课程名_考试开始.png
    课程名_考试结果.png
```

已存在的不覆盖。中文路径不能直接 `adb pull`，脚本做法是先拉到 `%TEMP%` 再 `Move-Item`。

---

## 7. 常见故障对照

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 日志一直「已播 X」不涨 | 视频暂停或分片没增长 | 点视频画面；或用 `keyevent 126` |
| 明明播完却不结束 | `--played` 偏低 / 分片取到旧值 | 已修：按分片自校正；确认用最新脚本 |
| 点「考试」没反应 | 结束提示框盖住底部按钮 | 先点「确定」关提示再点「考试」 |
| 掉回项目页空转 | 弹窗把播放器关了 | 脚本会自动重新点进当前课件 |
| `uiautomator dump` 只有几百字节 / 焦点异常 | 模拟器卡死或 ADB 半断 | `adb reboot`，重启后重新 `adb connect` |
| 截图报 WinError 2/17 | 中文路径 | 先 pull 到 `%TEMP%` 再移动 |
| 换课件后立刻判「停滞」 | 分片号从 0 重新计 | 脚本检测到回落会重置基线 |
| OCR 只出时钟 | 截到黑屏（模拟器未渲染） | 等画面出来再截；或改用 `uiautomator` 读文本 |

---

## 8. 换机后 3 分钟自检清单

1. `adb devices` 能看到设备。
2. `python huayi_ui.py` 能列出当前页文本坐标（如不能，先查 ADB 路径）。
3. 手动进一个课件，`dumpsys window | grep mCurrentFocus` 显示 `MediaPlayNewActivity`。
4. 起守护 2 分钟，日志出现「进度：已播 … 秒」且分片在涨。
5. 到 50% 时任务目录里出现「中间」截图。
