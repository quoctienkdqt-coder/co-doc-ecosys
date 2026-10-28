@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
title Khoi chay eCoSys AI Extractor
echo Dang khoi chay eCoSys AI C/O Extractor (Gemini 3.8 Flash)...
python app_co_extractor.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Khong the khoi chay ung dung. Vui long kiem tra lai moi truong Python.
    pause
)
