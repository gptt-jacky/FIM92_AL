@echo off
title MANPADS_Tracker_Window
chcp 65001 >nul 2>&1
echo === MANPADS Tracking - Pipe Mode (Zero File I/O) ===
echo.
echo [!] Need: pip install websockets
echo.

cd /d "%~dp0..\build\Release"
copy /Y "%~dp0..\scenes.json" ".\scenes.json" >nul 2>&1

echo Starting pipe server...
start "" "http://localhost:8080/viewer_ws.html?v=8"

echo Piping C++ output to WebSocket server...
TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0..\web\pipe_server.py"

pause
