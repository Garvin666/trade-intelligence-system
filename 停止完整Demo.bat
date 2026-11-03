@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_complete_demo.ps1"
pause
