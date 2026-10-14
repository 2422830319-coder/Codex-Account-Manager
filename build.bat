@echo off
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
