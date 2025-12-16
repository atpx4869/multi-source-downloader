# -*- coding: utf-8 -*-
"""
PyInstaller 构建配置脚本
生成单个可执行文件及其依赖
"""

import os
import sys
import subprocess
from pathlib import Path

def build_app():
    """构建可执行文件"""
    
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    
    print("=" * 60)
    print("Building application...")
    print("=" * 60)
    
    # PyInstaller 参数
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",                          # 单文件模式
        "--windowed",                         # 窗口模式（无命令行）
        "--name=标准下载",                     # 应用名称
        "--add-data=core:core",               # 添加核心模块
        "--add-data=sources:sources",         # 添加数据源模块
        "--add-data=ppllocr:ppllocr",         # 添加 OCR 模块
        "--hidden-import=core",
        "--hidden-import=core.models",
        "--hidden-import=core.aggregated_downloader",
        "--hidden-import=sources",
        "--hidden-import=sources.gbw",
        "--hidden-import=sources.by",
        "--hidden-import=sources.zby",
        "--hidden-import=ppllocr",
        "--hidden-import=ppllocr.inference",
        "--hidden-import=onnxruntime",
        "--hidden-import=requests",
        "--hidden-import=pandas",
        "--hidden-import=PySide6",
        "--collect-all=streamlit",
        "--collect-all=pandas",
        "--collect-all=PySide6",
        "--exclude-module=tests",
        "--exclude-module=pytest",
        "--clean",
        "--noconfirm",
        str(project_root / "desktop_app.py"),
    ]
    
    # 移除 None 值
    cmd = [arg for arg in cmd if arg is not None]
    
    print(f"执行命令: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, cwd=str(project_root), check=True)
        
        if result.returncode == 0:
            exe_path = dist_dir / "标准下载.exe"
            if exe_path.exists():
                print("\n" + "=" * 60)
                print("Build successful!")
                print(f"Executable: {exe_path}")
                print(f"File size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
                print("=" * 60 + "\n")
                return True
        else:
            print(f"Build failed, return code: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"Build error: {e}")
        return False

if __name__ == "__main__":
    # 检查依赖
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    success = build_app()
    sys.exit(0 if success else 1)
