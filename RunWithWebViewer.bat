@echo off
echo === FIM92 Tracking + Web Viewer ===
echo.

cd /d "%~dp0build\Release"
copy /Y "%~dp0scenes.json" ".\scenes.json" >nul 2>&1

echo Starting web server on http://localhost:8080 ...
start "FIM92 Web Server" python "%~dp0web\server.py"

timeout /t 2 >nul
start http://localhost:8080

echo Starting tracker...
TrackingMinimalDemo.exe "..\..\scenes.json"

echo.
echo Tracker stopped. Closing web server...
taskkill /FI "WINDOWTITLE eq FIM92 Web Server" >nul 2>&1
pause
