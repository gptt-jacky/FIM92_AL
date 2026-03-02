@echo off
title MANPADS_DataServer
chcp 65001 >nul 2>&1
echo === MANPADS Data Server (for Software Team) ===
echo.
echo [Local IP Addresses]
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4"') do (
    echo   %%a
)
echo.

set WS_HOST=0.0.0.0
set WS_PORT=8765

echo   0.0.0.0 = Accept all connections (default)
echo.
set /p WS_HOST="Server Host [%WS_HOST%]: " || set WS_HOST=%WS_HOST%
set /p WS_PORT="Server Port [%WS_PORT%]: " || set WS_PORT=%WS_PORT%

echo.
echo [Host] %WS_HOST%
echo [Port] %WS_PORT%
echo [URI]  ws://%WS_HOST%:%WS_PORT%
echo.
echo Starting...
echo.

cd /d "%~dp0..\build\Release"
copy /Y "%~dp0..\scenes.json" ".\scenes.json" >nul 2>&1

TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0..\web\data_server.py" --host %WS_HOST% --port %WS_PORT%

pause
