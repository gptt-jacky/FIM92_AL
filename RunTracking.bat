@echo off
cd /d "%~dp0build\Release"
copy /Y "%~dp0scenes.json" ".\scenes.json" >nul 2>&1
TrackingMinimalDemo.exe "..\..\scenes.json"
pause
