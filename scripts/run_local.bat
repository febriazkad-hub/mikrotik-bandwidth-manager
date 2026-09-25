@echo off
title MikroTik Smart Bandwidth Manager
cd /d "%~dp0\.."
echo ====================================================
echo   MikroTik Smart Bandwidth Manager (FastAPI + Web)
echo ====================================================
echo Menjalankan Web Dashboard di http://localhost:5678 ...
echo Tekan Ctrl+C untuk menghentikan.
echo.
python -m app.main
pause
