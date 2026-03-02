@echo off
title MANPADS_LocalFile
chcp 65001 >nul 2>&1
echo === MANPADS Local File Mode ===
echo.
echo   Tracking data will be written to:
echo   build\Release\tracking_data.json
echo.
echo   Software team can poll-read this file for real-time data.
echo   Press [Q] in the tracker window to quit.
echo.

cd /d "%~dp0..\build\Release"
copy /Y "%~dp0..\scenes.json" ".\scenes.json" >nul 2>&1

TrackingMinimalDemo.exe "..\..\scenes.json"

pause
