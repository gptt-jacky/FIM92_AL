@echo off
title FIM92_HighSpeed_Server
chcp 65001 >nul 2>&1
echo === FIM92 High Speed Data Server (500Hz) ===
echo.
echo [Mode] Pipe Mode (Memory-to-Memory, Zero Latency)
echo [Port] WebSocket: ws://localhost:8765
echo [Info] Ready for software team connection.
echo.

cd /d "%~dp0build\Release"
copy /Y "%~dp0scenes.json" ".\scenes.json" >nul 2>&1

echo Piping C++ output to WebSocket server...
TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0web\pipe_server.py"

pause