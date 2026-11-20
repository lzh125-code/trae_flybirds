@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "APP_DIR=%ROOT%huayi_console"
set "PORT=8765"
set "ADB_PATH=E:\leidian\LDPlayer14\adb.exe"
set "EMULATOR_PATH=E:\leidian\LDPlayer14\dnplayer.exe"

if exist "%APP_DIR%\.env" (
  for /f "usebackq eol=# tokens=1,2 delims==" %%A in ("%APP_DIR%\.env") do (
    if /i "%%A"=="CONSOLE_PORT" if not "%%B"=="" set "PORT=%%B"
    if /i "%%A"=="ADB_PATH" if not "%%B"=="" set "ADB_PATH=%%B"
    if /i "%%A"=="EMULATOR_PATH" if not "%%B"=="" set "EMULATOR_PATH=%%B"
  )
)
set "URL=http://127.0.0.1:%PORT%"

if not exist "%APP_DIR%\app.py" (
  echo [ERROR] Console app not found: %APP_DIR%\app.py
  pause
  exit /b 1
)

if not exist "%ADB_PATH%" (
  echo [ERROR] adb not found: %ADB_PATH%
  echo Set ADB_PATH in huayi_console\.env.
  pause
  exit /b 1
)

call :is_device_ready
if not errorlevel 1 goto device_ready
if not exist "%EMULATOR_PATH%" (
  echo [ERROR] Emulator not found: %EMULATOR_PATH%
  echo Set EMULATOR_PATH in huayi_console\.env.
  pause
  exit /b 1
)

tasklist /FI "IMAGENAME eq dnplayer.exe" /NH | find /I "dnplayer.exe" >nul
if errorlevel 1 (
  echo Starting the Android emulator...
  start "" "%EMULATOR_PATH%"
) else (
  echo The emulator is already running. Waiting for Android...
)

for /l %%I in (1,1,60) do (
  powershell -NoProfile -Command "Start-Sleep -Seconds 2"
  call :is_device_ready
  if not errorlevel 1 goto device_ready
)

echo [ERROR] Android did not become ready within 120 seconds.
echo Check the emulator and adb connection, then try again.
pause
exit /b 1

:device_ready
echo Android device is ready.

call :is_ready
if not errorlevel 1 (
  echo Console is already running. Opening the page...
  goto open_browser
)

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.10 and add it to PATH.
  pause
  exit /b 1
)

echo Starting the console server...
start "Huayi Console Server" /D "%APP_DIR%" cmd /k python app.py

for /l %%I in (1,1,30) do (
  call :is_ready
  if not errorlevel 1 goto open_browser
  powershell -NoProfile -Command "Start-Sleep -Seconds 1"
)

echo [ERROR] The console did not become ready within 30 seconds.
echo Check the Huayi Console Server window for details.
echo First-time setup: python -m pip install -r "%APP_DIR%\requirements.txt"
pause
exit /b 1

:open_browser
echo Opening %URL%
start "" "%URL%"
endlocal
exit /b 0

:is_device_ready
powershell -NoProfile -ExecutionPolicy Bypass -Command "$lines = & '%ADB_PATH%' devices 2>$null | Select-Object -Skip 1; foreach ($line in $lines) { $parts = $line.Trim() -split '\s+'; if ($parts.Count -ge 2 -and $parts[1] -eq 'device') { $boot = & '%ADB_PATH%' -s $parts[0] shell getprop sys.boot_completed 2>$null; if ($boot -match '1') { exit 0 } } }; exit 1" >nul 2>&1
exit /b %errorlevel%

:is_ready
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%URL%/api/status'; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
exit /b %errorlevel%
