# -*- coding: utf-8 -*-
"""生成两个 Windows 批处理文件（GBK 编码 + CRLF 换行）：
- 启动Codex账号管家.bat  （双击启动器：自动探测 Python、全程反馈、窗口留存）
- build.bat              （一键打包 exe：PyInstaller）

运行：python make_bats.py
变更 bat 内容后：改本文件后重新运行即可（不要用普通文本编辑器直接改 bat）。
"""
from pathlib import Path

LAUNCHER_BAT = r"""@echo off
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
"""

BUILD_BAT = r"""@echo off
setlocal
cd /d "%~dp0"

if "%BUTLER_DRY%"=="1" (
    echo DRY RUN OK - 脚本解析正常（未执行打包）。
    exit /b 0
)

echo ============================================
echo   Codex 账号管家 - 打包脚本
echo ============================================
echo.

echo [1/4] 查找 Python...
set "PY_CMD="
where python >nul 2>nul
if not errorlevel 1 set "PY_CMD=python"
if not defined PY_CMD (
    where py >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    echo        [X] 未找到 Python，请先安装 Python 3.9+ 并加入 PATH。
    echo.
    pause
    exit /b 1
)
echo        使用：%PY_CMD%

echo [2/4] 检查打包工具 PyInstaller...
%PY_CMD% -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo        未安装，正在通过 pip 安装...
    %PY_CMD% -m pip install pyinstaller
    if errorlevel 1 (
        echo.
        echo        [X] 安装失败：请检查网络（或先配置好代理后重试）。
        echo.
        pause
        exit /b 1
    )
)

echo [3/4] 开始打包（约 1-3 分钟，请耐心等待）...
%PY_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name CodexAccountButler --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQuick3D --exclude-module PySide6.Qt3DCore --exclude-module PySide6.Qt3DRender --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtMultimediaWidgets --exclude-module PySide6.QtCharts --exclude-module PySide6.QtDataVisualization app.py

if errorlevel 1 (
    echo.
    echo        [X] 打包失败，请把上面的报错截图发给开发者。
    echo.
    pause
    exit /b 1
)

echo [4/4] 完成！
echo.
echo       exe 已生成：%~dp0dist\CodexAccountButler.exe
echo.
pause
"""

base = Path(__file__).resolve().parent
targets = [
    ("启动Codex账号管家.bat", LAUNCHER_BAT, "本窗口会保留在这里"),
    ("build.bat", BUILD_BAT, "打包脚本"),
]

for name, content, probe in targets:
    p = base / name
    p.write_text(content, encoding="gbk", newline="\r\n")
    back = p.read_text(encoding="gbk")
    assert probe in back, "%s GBK 回读失败" % name
    data = p.read_bytes()
    print("written: %s (%d bytes, CRLF=%d)" % (name, len(data), data.count(b"\r\n")))

print("done.")
