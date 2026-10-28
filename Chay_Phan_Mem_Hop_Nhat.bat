@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
title He Thong Hop Nhat XNK & Thuy San (eCoSys C/O & Doi Chieu SC)
echo ======================================================================
echo    HE THONG QUAN TRI XUAT NHAP KHAU & THUY SAN TOAN DIEN (v3.0)
echo    Hop nhat: Khai bao C/O eCoSys & Doi chieu SC Cang ca (Chi Nguyen)
echo    Tich hop: Gemini 3.8 Flash & Cong APIZ Vietnam Gateway
echo ======================================================================
echo.
echo Dang khoi chay ung dung hop nhat...
python app_unified_suite.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Khong the khoi chay ung dung. Vui long kiem tra lai moi truong Python.
    pause
)
