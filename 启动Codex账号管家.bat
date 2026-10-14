@echo off
title Codex 账号管家 - 启动器
cd /d "%~dp0"

echo ============================================
echo    Codex 账号管家 - 启动器
echo ============================================
echo.

echo [1/3] 检查程序文件...
if not exist app.py (
    echo        [X] 未找到 app.py，程序文件不完整！
    echo            请把本窗口截图发给开发者。
    echo.
    pause
    exit /b 1
)
echo        已找到 app.py
echo.

echo [2/3] 检查运行环境（自动探测 Python）...
set "LAUNCH_CMD="

rem 方式1：PATH 中的 pythonw（最常见）
for /f "delims=" %%i in ('where pythonw 2^>nul') do (
    if not defined LAUNCH_CMD set LAUNCH_CMD="%%i"
)
if defined LAUNCH_CMD goto :found

rem 方式2：Python Launcher（pyw）
where pyw >nul 2>nul
if not errorlevel 1 (
    set "LAUNCH_CMD=pyw"
    goto :found
)

rem 方式3：扫描用户级安装目录
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%~d\pythonw.exe" if not defined LAUNCH_CMD set LAUNCH_CMD="%%~d\pythonw.exe"
)
if defined LAUNCH_CMD goto :found

rem 方式4：扫描常见系统级安装目录
for %%d in ("C:\Python313" "C:\Python312" "C:\Python311" "C:\Python310" "C:\Python39") do (
    if exist "%%~d\pythonw.exe" if not defined LAUNCH_CMD set LAUNCH_CMD="%%~d\pythonw.exe"
)
if defined LAUNCH_CMD goto :found

echo        [X] 未找到可用的 Python 环境！
echo.
echo   本程序需要 Python 3.9 或更高版本。
echo   请到 https://www.python.org/downloads/ 下载安装，
echo   安装时勾选 Add python.exe to PATH，然后重新双击本启动器。
echo.
echo   如果已安装 Python 仍看到此提示，请把本窗口截图发给开发者。
echo.
pause
exit /b 1

:found
echo        已找到可用的 Python 环境

if "%BUTLER_DRY%"=="1" (
    echo        [DRY RUN] 探测流程正常（%LAUNCH_CMD%），跳过实际启动。
    exit /b 0
)

echo.
echo [3/3] 正在启动程序...
start "" %LAUNCH_CMD% app.py >nul 2>nul

echo        正在确认启动结果（约 2 秒）...
ping -n 3 127.0.0.1 >nul
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /I "pythonw.exe" >nul
if errorlevel 1 (
    echo.
    echo   [X] 未检测到程序进程 -- 可能启动失败了！
    echo       请把本窗口截图发给开发者。
) else (
    echo.
    echo   [OK] 程序已启动！窗口应该已经出现在你的屏幕上。
    echo        如果没有看到窗口，检查任务栏，或把本窗口截图发给开发者。
)
echo.
echo   本窗口会保留在这里（不自动关闭），
echo   看完结果后，按任意键即可关闭。
echo.
pause
exit /b 0
