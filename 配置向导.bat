@echo off
chcp 65001 >nul
REM ===========================================================
REM 智护银伴 · 单独打开配置向导（不启动服务）
REM
REM 用途：日常想改 .env（换 Token、切 LLM 后端、换端口等）时，
REM       不必再敲命令行，双击本文件即可弹出图形化向导。
REM ===========================================================

setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-wizard.ps1"

if errorlevel 1 (
    echo.
    echo 配置向导已退出。如取消保存属正常情况。
    echo 如出现错误信息请截图反馈。
    pause >nul
)

endlocal
