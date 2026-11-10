@echo off
chcp 65001 >nul
title ouVPN Control Panel
cd /d "%~dp0"
echo ========================================================
echo               🛡️ ouVPN Control Panel
echo ========================================================
echo [*] Запуск графической панели управления...
start "" pythonw panel.py
if %ERRORLEVEL% NEQ 0 (
    python panel.py
    pause
)
