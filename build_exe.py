"""
PyInstaller 打包脚本 - 修复 PySide6 和依赖问题
"""
import os
import sys
import subprocess
import shutil

def clean_build():
    """清理之前的构建"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']
    
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
            print(f"✓ 清理目录: {d}")
    
    for pattern in files_to_clean:
        for f in os.listdir('.'):
            if f.endswith('.spec'):
                os.remove(f)
                print(f"✓ 删除文件: {f}")

def build_exe():
    """构建 EXE"""
    print("\n" + "="*70)
    print("开始 PyInstaller 打包...")
    print("="*70 + "\n")
    
    # PyInstaller 命令参数
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm',                    # 不确认覆盖
        '--onefile',                       # 单文件模式
        '--windowed',                      # 无控制台窗口
        '--name=MultiSourceDownloader',    # 程序名称
        
        # 图标
        '--icon=app.ico',
        
        # PySide6 相关（关键修复）
        '--collect-all=PySide6',
        '--copy-metadata=PySide6',
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui',
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=PySide6.QtNetwork',
        
        # Playwright 相关
        '--collect-all=playwright',
        '--copy-metadata=playwright',
        '--hidden-import=playwright',
        '--hidden-import=playwright.sync_api',
        
        # HTTP 相关
        '--hidden-import=httpx',
        '--hidden-import=requests',
        '--hidden-import=urllib3',
        
        # 数据库
        '--hidden-import=sqlalchemy',
        '--hidden-import=sqlalchemy.ext.declarative',
        
        # 其他依赖
        '--hidden-import=openpyxl',
        '--hidden-import=chardet',
        '--hidden-import=lxml',
        
        # 排除不需要的大型库（注意：pandas 和 numpy 实际被使用了，不能排除）
        '--exclude-module=matplotlib',
        '--exclude-module=scipy',
        '--exclude-module=tkinter',
        '--exclude-module=jupyter',
        '--exclude-module=IPython',
        '--exclude-module=IPython.core',
        '--exclude-module=pytest',
        '--exclude-module=pytest_runner',
        
        # 添加数据文件
        '--add-data=config;config',
        
        # 主入口
        'desktop_app.py'
    ]
    
    print("执行命令:")
    print(' '.join(cmd))
    print("\n" + "-"*70 + "\n")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        
        print("\n" + "="*70)
        print("✅ 打包成功！")
        print("="*70)
        
        exe_path = os.path.join('dist', 'MultiSourceDownloader.exe')
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n📦 生成的 EXE 文件:")
            print(f"   路径: {exe_path}")
            print(f"   大小: {size_mb:.1f} MB")
            print(f"\n🚀 可以运行测试: dist\\MultiSourceDownloader.exe")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print("\n" + "="*70)
        print("❌ 打包失败")
        print("="*70)
        print(f"\n错误代码: {e.returncode}")
        print("\n可能的原因:")
        print("1. 缺少必要的库（运行: pip install -r requirements.txt）")
        print("2. PySide6 版本不兼容（尝试: pip install PySide6==6.5.0）")
        print("3. PyInstaller 版本问题（尝试: pip install pyinstaller==6.3.0）")
        print("\n建议:")
        print("- 查看上面的错误信息")
        print("- 如果是 PySide6 元数据错误，尝试升级 PyInstaller")
        print("- 如果仍然失败，考虑使用 WinPython 便携式方案")
        return False
    
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        return False

def main():
    print("="*70)
    print("Multi-Source Downloader - PyInstaller 打包工具")
    print("="*70)
    
    # 检查环境
    print("\n📋 检查环境...")
    
    if not os.path.exists('desktop_app.py'):
        print("❌ 找不到 desktop_app.py，请在项目根目录运行此脚本")
        sys.exit(1)
    
    if not os.path.exists('app.ico'):
        print("⚠️  找不到 app.ico，将使用默认图标")
    
    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("❌ 未安装 PyInstaller")
        print("   请运行: pip install pyinstaller")
        sys.exit(1)
    
    # 检查 PySide6
    try:
        import PySide6
        print(f"✓ PySide6 已安装")
    except ImportError:
        print("❌ 未安装 PySide6")
        print("   请运行: pip install PySide6")
        sys.exit(1)
    
    print("\n🧹 清理旧文件...")
    clean_build()
    
    print("\n🔨 开始打包...")
    success = build_exe()
    
    if success:
        print("\n" + "="*70)
        print("✅ 全部完成！")
        print("="*70)
        sys.exit(0)
    else:
        print("\n" + "="*70)
        print("💡 打包失败，建议使用 WinPython 便携式方案")
        print("="*70)
        print("\n详见: FINAL_PACKAGING_SOLUTION.md")
        sys.exit(1)

if __name__ == '__main__':
    main()
