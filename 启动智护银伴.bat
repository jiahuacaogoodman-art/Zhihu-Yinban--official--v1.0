@echo off
chcp 65001 >nul
REM ===========================================================
REM 智护银伴 · Windows 双击启动器
REM
REM 作用：让不熟悉 PowerShell / 命令行的院方运维人员可以
REM       直接双击运行，绕过 PowerShell 的执行策略限制。
REM
REM 调用：scripts\launch-local.ps1（首次会自动弹出 GUI 配置向导）
REM ===========================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   智护银伴 · 启动中...
echo ============================================================
echo.
echo   首次启动会弹出 [配置向导] 窗口，请按照提示填写。
echo   服务起来后，浏览器会自动打开管理端页面。
echo.

REM -ExecutionPolicy Bypass：让 .ps1 脚本绕过 Restricted 策略一次性运行
REM -NoProfile：忽略用户 PowerShell profile，避免被自定义模块影响
REM -NoExit：服务起来后保留窗口，方便看日志和按 Ctrl+C 停服务
powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0scripts\launch-local.ps1"

if errorlevel 1 (
    echo.
    echo ============================================================
    echo   启动失败。请按任意键关闭，并查看上方红色错误信息。
    echo   如需协助，运行: scripts\diagnose.ps1 -WriteReport
    echo ============================================================
    pause >nul
)

endlocal
