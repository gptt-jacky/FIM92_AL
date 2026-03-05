@echo off
title MANPADS_WS_Client
chcp 65001 >nul 2>&1
echo === MANPADS WebSocket Client ===
echo.
echo [Local IP Addresses]
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4"') do (
    echo   %%a
)
echo.

set WS_HOST=localhost
set WS_PORT=8765

echo   Enter Server IP to connect (localhost = same machine)
echo.
set /p WS_HOST="Server Host [%WS_HOST%]: "
set /p WS_PORT="Server Port [%WS_PORT%]: "

echo.
echo Connecting to ws://%WS_HOST%:%WS_PORT% ...
echo.

python "%~dp0ws_client.py" --url ws://%WS_HOST%:%WS_PORT%

pause
