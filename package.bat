@echo off
REM PyInstaller 快速打包脚本 (Windows Batch)
REM 用法: 在项目根目录运行此脚本
REM
REM 功能:
REM   - 清理旧构建
REM   - 运行 PyInstaller
REM   - 验证输出

setlocal enabledelayedexpansion

echo ============================================================
echo PyInstaller 快速打包工具
echo ============================================================

REM 清理旧文件
echo.
echo [1/3] 清理旧文件...
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1
if exist desktop_app.spec del /q desktop_app.spec >nul 2>&1
echo  OK

REM 检查虚拟环境
echo.
echo [2/3] 检查环境...
if not exist .venv\Scripts\pyinstaller.exe (
    echo  ERROR: PyInstaller not found
    echo  Please run: pip install pyinstaller
    pause
    exit /b 1
)
echo  OK

REM 运行打包
echo.
echo [3/3] Running packaging (Expected 2-5 minutes)...
echo  Please wait...
.\.venv\Scripts\pyinstaller.exe ^
    --onefile ^
    --windowed ^
    --icon app.ico ^
    --distpath dist ^
    --name MultiSourceDownloader ^
    desktop_app.py

REM 验证结果
echo.
if exist dist\MultiSourceDownloader.exe (
    echo ============================================================
    echo OK - Packaging successful!
    echo ============================================================
    echo.
    echo Output: dist\MultiSourceDownloader.exe
    echo.
    echo Next steps:
    echo   1. Run: dist\MultiSourceDownloader.exe
    echo   2. Distribute to users
    echo.
    pause
    exit /b 0
) else (
    echo ============================================================
    echo ERROR - Packaging failed!
    echo ============================================================
    echo Please check the error messages above.
    pause
    exit /b 1
)
