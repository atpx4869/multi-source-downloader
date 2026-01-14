@echo off
REM -*- coding: utf-8 -*-
REM 标准下载器 - 启动脚本
REM 用途: 便携式 Python 版本的应用启动器

setlocal enabledelayedexpansion

REM 设置编码
chcp 65001 > nul 2>&1

REM 检查 WinPython
if not exist "WinPython-3.11.9\python.exe" (
    echo.
    echo 错误: 找不到 WinPython
    echo 请先下载并解压 WinPython 到 WinPython-3.11.9 目录
    echo 下载地址: https://winpython.github.io/
    echo.
    pause
    exit /b 1
)

REM 启动应用
"WinPython-3.11.9\python.exe" desktop_app.py

REM 如果有错误代码，显示错误信息
if errorlevel 1 (
    echo.
    echo 应用退出，错误代码: %errorlevel%
    pause
)
