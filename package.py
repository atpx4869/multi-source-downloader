# -*- coding: utf-8 -*-
"""
完整打包脚本：一键生成 Windows 安装程序
流程：
1. 生成 PyInstaller 可执行文件
2. 使用 NSIS 生成 Windows 安装程序
"""

import os
import sys
import subprocess
from pathlib import Path

def check_nsis_installed():
    """检查 NSIS 是否已安装"""
    nsis_paths = [
        "C:\\Program Files\\NSIS\\makensis.exe",
        "C:\\Program Files (x86)\\NSIS\\makensis.exe",
    ]
    
    for path in nsis_paths:
        if os.path.exists(path):
            return path
    
    return None

def install_nsis():
    """安装 NSIS"""
    print("📥 NSIS 未找到，请手动安装:")
    print("   1. 访问: https://nsis.sourceforge.io/Download")
    print("   2. 下载最新版本")
    print("   3. 运行安装程序")
    print("\n或使用 winget 安装:")
    print("   winget install NSIS")
    return False

def build_exe(project_root):
    """第一步：使用 PyInstaller 构建 EXE"""
    print("\n" + "="*70)
    print("第 1/2 步：用 PyInstaller 生成可执行文件")
    print("="*70)
    
    build_script = project_root / "build_config.py"
    if not build_script.exists():
        print(f"❌ 找不到 {build_script}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=str(project_root),
            check=False
        )
        
        exe_path = project_root / "dist" / "标准下载.exe"
        if exe_path.exists():
            print(f"✅ EXE 生成成功: {exe_path}")
            return True
        else:
            print("❌ EXE 生成失败")
            return False
            
    except Exception as e:
        print(f"❌ 构建出错: {e}")
        return False

def build_installer(project_root):
    """第二步：使用 NSIS 生成安装程序"""
    print("\n" + "="*70)
    print("第 2/2 步：用 NSIS 生成 Windows 安装程序")
    print("="*70)
    
    nsis_path = check_nsis_installed()
    if not nsis_path:
        return install_nsis()
    
    nsi_file = project_root / "installer.nsi"
    if not nsi_file.exists():
        print(f"❌ 找不到 {nsi_file}")
        return False
    
    try:
        print(f"使用 NSIS: {nsis_path}")
        print(f"编译脚本: {nsi_file}\n")
        
        result = subprocess.run(
            [nsis_path, str(nsi_file)],
            cwd=str(project_root),
            check=False,
            capture_output=False
        )
        
        installer_path = project_root / "dist" / "标准下载-安装程序.exe"
        if installer_path.exists():
            size_mb = installer_path.stat().st_size / (1024*1024)
            print(f"\n✅ 安装程序生成成功!")
            print(f"📦 文件: {installer_path}")
            print(f"📊 大小: {size_mb:.1f} MB")
            return True
        else:
            print("❌ 安装程序生成失败")
            return False
            
    except Exception as e:
        print(f"❌ NSIS 编译出错: {e}")
        return False

def main():
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("\n")
    print(" " * 20 + "🚀 标准下载 - 打包工具")
    print(" " * 15 + "一键生成 Windows 安装程序\n")
    
    # 检查依赖
    print("📋 检查依赖...")
    try:
        import PyInstaller
        print("  ✓ PyInstaller 已安装")
    except ImportError:
        print("  📥 安装 PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 第一步：构建 EXE
    if not build_exe(project_root):
        print("\n❌ 打包失败：无法生成 EXE")
        return False
    
    # 第二步：构建安装程序
    if not build_installer(project_root):
        print("\n⚠️  EXE 已生成，但安装程序生成失败")
        print("请手动安装 NSIS 后重试")
        return False
    
    print("\n" + "="*70)
    print("🎉 完成！安装程序已生成")
    print("="*70)
    print(f"📂 位置: {project_root / 'dist' / '标准下载-安装程序.exe'}")
    print("\n可以现在测试安装：")
    print("1. 双击运行安装程序")
    print("2. 按照向导安装")
    print("3. 在开始菜单或桌面上找到快捷方式\n")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
