@echo off
title MANPADS_DataServer
chcp 65001 >nul 2>&1
echo === MANPADS Data Server (for Software Team) ===
echo.

set WS_HOST=0.0.0.0
set WS_PORT=8765

set /p WS_HOST="Server Host [%WS_HOST%]: " || set WS_HOST=%WS_HOST%
set /p WS_PORT="Server Port [%WS_PORT%]: " || set WS_PORT=%WS_PORT%

echo.
echo [Host] %WS_HOST%
echo [Port] %WS_PORT%
echo [URI]  ws://%WS_HOST%:%WS_PORT%
echo.
echo Starting...
echo.

cd /d "%~dp0build\Release"
copy /Y "%~dp0scenes.json" ".\scenes.json" >nul 2>&1

TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0web\data_server.py" --host %WS_HOST% --port %WS_PORT%

pause
