@echo off
chcp 65001 >nul 2>&1
echo === FIM92 Tracking + WebSocket Viewer ===
echo.
echo [!] Need: pip install websockets
echo.

cd /d "%~dp0build\Release"
copy /Y "%~dp0scenes.json" ".\scenes.json" >nul 2>&1

echo Starting WebSocket server...
start "FIM92 WebSocket Server" python "%~dp0web\server_ws.py"

timeout /t 2 >nul
start "" "http://localhost:8080"

echo Starting tracker...
TrackingMinimalDemo.exe "..\..\scenes.json"

echo.
echo Tracker stopped. Closing server...
taskkill /FI "WINDOWTITLE eq FIM92 WebSocket Server" >nul 2>&1
pause
