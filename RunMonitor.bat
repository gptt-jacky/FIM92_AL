@echo off
title FIM92_Monitor
chcp 65001 >nul 2>&1
echo === FIM92 Tracking Monitor ===
echo.
echo Loading...
echo.

cd /d "%~dp0build\Release"
copy /Y "%~dp0scenes.json" ".\scenes.json" >nul 2>&1

TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0web\monitor.py"

pause
