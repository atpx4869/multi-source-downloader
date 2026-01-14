@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   多源标准下载器 - 启动脚本
echo ========================================
echo.

REM 清理Python缓存
echo [1/3] 清理Python缓存...
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i" 2>nul
del /s /q *.pyc 2>nul
echo   ✓ 缓存已清理

echo.
echo [2/3] 验证修复...
.\.venv\Scripts\python.exe -c "from core.smart_search import StandardSearchMerger; from sources.zby import ZBYSource; print('  ✓ QB/T识别正确: qb/t 1950-2024 ->', 'True' if not StandardSearchMerger.is_gb_standard('qb/t 1950-2024') else 'False'); print('  ✓ GB/T识别正确: gb/t 1950-2024 ->', 'True' if StandardSearchMerger.is_gb_standard('gb/t 1950-2024') else 'False')"

echo.
echo [3/3] 启动应用...
echo.
.\.venv\Scripts\python.exe desktop_app.py

if errorlevel 1 (
    echo.
    echo 应用已退出，按任意键关闭...
    pause >nul
)

