@echo off
cd /d "%~dp0..\build\Release"
copy /Y "%~dp0..\scenes.json" ".\scenes.json" >nul 2>&1
TrackingMinimalDemo.exe "..\..\scenes.json"
pause
