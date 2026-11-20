@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "APP_DIR=%ROOT%huayi_console"
set "PORT=8765"

if exist "%APP_DIR%\.env" (
  for /f "usebackq eol=# tokens=1,2 delims==" %%A in ("%APP_DIR%\.env") do (
    if /i "%%A"=="CONSOLE_PORT" if not "%%B"=="" set "PORT=%%B"
  )
)
set "URL=http://127.0.0.1:%PORT%"

if not exist "%APP_DIR%\app.py" (
  echo [ERROR] Console app not found: %APP_DIR%\app.py
  pause
  exit /b 1
)

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

:is_ready
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%URL%/api/status'; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
exit /b %errorlevel%
