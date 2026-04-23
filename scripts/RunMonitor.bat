@echo off
title MANPADS_Monitor
chcp 65001 >nul 2>&1
echo === MANPADS Tracking Monitor ===
echo.
echo Loading...
echo.

cd /d "%~dp0..\build\Release"
copy /Y "%~dp0..\scenes.json" ".\scenes.json" >nul 2>&1

TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0..\faymantu\monitor.py"

pause
