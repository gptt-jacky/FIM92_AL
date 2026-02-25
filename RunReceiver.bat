@echo off
title FIM92_Receiver_Client
chcp 65001 >nul

echo === FIM92 訊號接收模擬器 ===
echo.
echo [!] 請確保第二台電腦已安裝 Python 和 websockets (pip install websockets)
echo.

set /p IP="請輸入第一台電腦 (發送端) 的 IP 位址: "

echo.
echo 正在連線到 %IP% ...
python "%~dp0ReceiveTest.py" %IP%

pause
