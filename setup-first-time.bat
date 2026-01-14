@echo off
REM 标准下载器 - 首次运行安装脚本
REM 用途: 自动安装所有 Python 依赖

setlocal enabledelayedexpansion

REM 设置编码
chcp 65001 > nul 2>&1

echo.
echo ============================================================
echo  标准下载器 - 依赖安装
echo ============================================================
echo.

REM 检查 WinPython
if not exist "WinPython-3.11.9\Scripts\pip.exe" (
    echo 错误: 找不到 WinPython
    echo 请先下载并解压 WinPython-3.11.9 目录
    echo 下载: https://winpython.github.io/
    echo.
    pause
    exit /b 1
)

REM 检查 requirements 文件
if not exist "requirements_distribute.txt" (
    echo 正在使用 requirements.txt...
    copy requirements.txt requirements_distribute.txt
)

echo 正在安装依赖...
echo 这可能需要几分钟，请耐心等待...
echo.

REM 升级 pip
"WinPython-3.11.9\Scripts\pip.exe" install --upgrade pip setuptools wheel

REM 安装项目依赖
"WinPython-3.11.9\Scripts\pip.exe" install -r requirements_distribute.txt

if errorlevel 1 (
    echo.
    echo 安装失败！请检查错误信息
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  安装完成！
echo ============================================================
echo.
echo 现在可以运行:
echo   1. 双击 run.bat 启动应用
echo   2. 或在命令行运行: WinPython-3.11.9\python.exe desktop_app.py
echo.
pause
