@echo off
taskkill /F /IM chrome.exe >nul 2>&1
ping 127.0.0.1 -n 2 >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\Admin\AppData\Local\Google\Chrome\User Data" --restore-last-session
exit /b 0
