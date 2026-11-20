---
name: huayi-cme-direct
description: 使用 Trae、Python 与 ADB 直接完成掌上华医课件播放、考试和结果核验。用户要求掌上华医刷课、继续教育视频守护、逐题考试或换机恢复此流程时使用；不用于 Web 控制台、证书申请或无关账号操作。
---

# 掌上华医直接刷课

以 `flybirds_demo/pscript/huayi_course_guard.py`、`huayi_ui.py` 和 `huayi_cme_inventory.py` 为已验证实现。先阅读根目录 README 的换机章节及 `docs/huayi_environment_setup.md`；若当次任务没有已确认的需求与技术设计，先按项目文档门禁补齐并核对，再操作设备。

## 固定模式与安全边界

- 使用 Trae + Python + ADB 直接操作模拟器，不启动 Web 控制台，不调用控制台 API。
- 三个直接脚本只依赖 Python 标准库；OCR 仅用于读取播放器时间或截图文字。
- 优先处理真实待考试课件，再播放后续视频。
- 不点击“申请证书”，不执行无关账号、支付、资料修改或选课操作。
- 不把“守护启动”“进入考试”“已交卷”当作完成。必须看到“考试通过”，并回到项目页确认进度增加。
- 同一时刻只运行一个播放守护。守护运行期间不要人工同时操作 App，也不要运行课程盘点。

## 1. 检查设备和起点

本机基线为 Windows、Python 3.10、雷电 900×1800、DPI 320、竖屏。换机先修改三个脚本顶部的 `ADB` 硬编码路径，再按 `adb devices` 的真实输出设置设备号。每个新 PowerShell 窗口都要重新设置：

```powershell
$env:HUAYI_DEVICE = "emulator-5554"
& "E:\leidian\LDPlayer14\adb.exe" devices
& "E:\leidian\LDPlayer14\adb.exe" -s $env:HUAYI_DEVICE shell getprop sys.boot_completed
python flybirds_demo\pscript\huayi_ui.py --state
```

只有设备状态为 `device`、`sys.boot_completed=1` 且界面探针能输出文字坐标时才继续。播放器页应显示 `MediaPlayNewActivity`：

```powershell
& "E:\leidian\LDPlayer14\adb.exe" -s $env:HUAYI_DEVICE shell dumpsys window | Select-String "mCurrentFocus"
```

## 2. 盘点和选择课件

只读盘点必须从顶部有“请输入项目名称”的课程列表页启动：

```powershell
python flybirds_demo\pscript\huayi_cme_inventory.py --screens 12
```

盘点输出项目汇总 `inventory.csv` 和课件明细 `inventory_lessons.csv`。项目页的“待考试”标签只能作为线索，真实完成状态仍以播放结果、考试结果和项目进度为准。

从考试结果页或项目列表进入下一课时，先重新读取 UI，再点击目标课件；进入详情页后核对完整课件标题。不要沿用旧页面坐标，避免打开同名系列中的错误课件。

## 3. 读取视频时间并启动守护

先手动打开目标课件视频并确认能播放。点击视频区域显示控制条，截图后用 `_ocr_image.py` 读取当前时间和总时长，把 `HH:MM:SS` 或 `MM:SS` 换算成秒。OCR 的 torch 警告不影响识别结果，但时间文本不清晰时必须重新截图核对。

从已打开且正在播放的目标播放器页启动守护：

```powershell
python -u flybirds_demo\pscript\huayi_course_guard.py `
  --lesson-index 5 `
  --lesson-name "筋骨痛证中医处方技巧漫谈（1）" `
  --duration 2298 `
  --played 237 `
  --out-root "$PWD\app_page_captures\huayi_course\tasks\常见骨慢病的诊治及临床实践" `
  --log "$PWD\app_page_captures\huayi_course\guard_05.log" `
  --max-hours 2
```

- `--duration` 是 OCR 核对后的总秒数，`--played` 是当前已播秒数。
- 启动后读取新日志，确认课件名、时长、任务目录和开始截图正确。
- 长时间任务使用独立后台命令，并单独监控 `TestQuestionsActivity`。不要重复启动同一课件的第二个守护，不要复用上一课的 PID 或后台任务编号。

## 4. 按真实分片判断播放

- 进度以 logcat 最后一个 `_数字.ts` 分片估算，每片约 8.57 秒；不能取历史最大分片号。
- `--played` 偏低时允许守护按分片自校正，以校正后的日志为准。
- 静态 PPT 也会持续产生分片，分片不动才是真停滞。
- 出现“谢谢观看”或“请点击左下角考试”等结束提示时，可按完成处理，即使分片估算尚未达到标称总时长。
- 没有结束提示时，只有分片停滞至少 5 分钟且进度达到 85% 才按结束处理；不足 85% 按卡顿恢复。
- 恢复播放使用 `keyevent 126`，不要用可能暂停视频的 `keyevent 85`。
- 不主动点击结束提示框的“确定”，避免退回项目页并关闭播放器。
- 守护在考试页停留超过 30 分钟可能自动退出，这是守护超时，不等于考试失败，也不代表 App 已退出。

## 5. 逐题考试并核验通过

进入 `TestQuestionsActivity`，或页面出现“交卷 / 答题状态 / 提交”后，守护只观察，不再点击。通过界面探针逐题读取题干、选项和状态：

```powershell
python flybirds_demo\pscript\huayi_ui.py --state
```

1. 按当前页面的完整题干匹配答案，不按上一轮的题号、选项字母或固定坐标作答；试题顺序可能变化。
2. 参考资料只用于候选答案，必须以当前题干和选项文本复核，不能盲用资料中的空格或位置规律。
3. 每题选择后确认目标选项为 `checked="true"` 或 `selected="true"`。
4. 交卷前逐题复核，并打开“答题状态”确认没有漏题。
5. 交卷后读取结果页，只有明确出现“考试通过”才记为通过；若未通过，记录本题题干和结果，再次考试时重新按题干核对。
6. 保存考试结果截图，回到项目详情页刷新 UI，确认学习进度按预期增加，例如从 `4/11` 变为 `5/11`。
7. 核对完成后再选择下一课；不要点击“申请证书”。

## 6. 保存证据和排障

每个课件任务目录为：

```text
app_page_captures/huayi_course/tasks/<项目名>/<序号>_<课件名>/
```

阶段截图包括开始、中间、结束、考试开始、考试结果，已有截图不覆盖。向中文长路径保存设备截图失败时，使用 `exec-out screencap -p` 获取 PNG 字节，再由 Python `Path.write_bytes()` 写入目标路径，不重复尝试已失败的 `adb pull` 中文路径写法。

| 现象 | 处理 |
| --- | --- |
| 打开了错误课件 | 未播放则立即返回，刷新 UI 后重新点击并核对标题 |
| 视频时间不准 | 重新显示控制条并 OCR；同时允许守护按最后 TS 分片校正 |
| 进度长期不涨 | 检查是否暂停或卡顿，必要时用 `keyevent 126` 恢复 |
| 分片低于总时长但出现结束提示 | 以真实结束提示和后续考试入口为准，不仅凭估算秒数否定完成 |
| 守护在考试页超时退出 | 检查当前 Activity 和考试页面，继续逐题考试，不据此判定失败 |
| 图片读取失败 | 用 OCR 或像素统计辅助检查，不反复执行同一失败读取 |
| 中文路径 `adb pull` 失败 | 改用 `exec-out screencap` 加 Python 二进制写入 |

最终汇报必须区分已播放、已进入考试、已交卷、考试通过和项目进度已增加，不用脚本退出码替代内容验收。
