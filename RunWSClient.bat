@echo off
title MANPADS_WS_Client
chcp 65001 >nul 2>&1
echo === MANPADS WebSocket Client ===
echo.

set WS_HOST=localhost
set WS_PORT=8765

set /p WS_HOST="Server Host [%WS_HOST%]: "
set /p WS_PORT="Server Port [%WS_PORT%]: "

echo.
echo Connecting to ws://%WS_HOST%:%WS_PORT% ...
echo.

python "%~dp0web\ws_client.py" --url ws://%WS_HOST%:%WS_PORT%

pause
