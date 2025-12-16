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
    print("🔨 开始构建应用...")
    print("=" * 60)
    
    # PyInstaller 参数
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",                          # 单文件模式
        "--windowed",                         # 窗口模式（无命令行）
        "--icon=assets/app.ico" if (project_root / "assets" / "app.ico").exists() else None,
        "--name=标准下载",                     # 应用名称
        "--add-data=core:core",               # 添加核心模块
        "--add-data=ppllocr:ppllocr",         # 添加 OCR 模块
        "--hidden-import=core",
        "--hidden-import=ppllocr",
        "--hidden-import=onnxruntime",
        "--collect-all=streamlit",
        "--collect-all=pandas",
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
                print(f"✅ 构建成功！")
                print(f"📦 可执行文件: {exe_path}")
                print(f"📊 文件大小: {exe_path.stat().st_size / (1024*1024):.1f} MB")
                print("=" * 60 + "\n")
                return True
        else:
            print(f"❌ 构建失败，返回码: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ 构建出错: {e}")
        return False

if __name__ == "__main__":
    # 检查依赖
    try:
        import PyInstaller
    except ImportError:
        print("📥 安装 PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    success = build_app()
    sys.exit(0 if success else 1)
