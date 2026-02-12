@echo off
title FIM92_Tracker_Window
chcp 65001 >nul 2>&1
echo === FIM92 Tracking - Pipe Mode (Zero File I/O) ===
echo.
echo [!] Need: pip install websockets
echo.

cd /d "%~dp0build\Release"
copy /Y "%~dp0scenes.json" ".\scenes.json" >nul 2>&1

echo Starting pipe server...
start "" "http://localhost:8080/viewer_ws.html?v=8"

echo Piping C++ output to WebSocket server...
TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0web\pipe_server.py"

pause
