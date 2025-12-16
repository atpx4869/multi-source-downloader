#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitHub 发布辅助脚本
自动创建 tag 和发起 GitHub Actions 打包

使用方法：
    python github_release.py "v1.0.0" "Release v1.0.0 - Add feature X"
"""

import sys
import subprocess
import re
from datetime import datetime

def run_command(cmd, capture=False):
    """执行 shell 命令"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True)
            return None
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {e}")
        sys.exit(1)

def validate_version(version):
    """验证版本号格式 (v1.0.0)"""
    if not re.match(r'^v\d+\.\d+\.\d+', version):
        print(f"❌ 无效的版本号格式: {version}")
        print("   应为: v1.0.0, v1.1.0, 等")
        sys.exit(1)

def create_release(version, message):
    """创建 Git tag 和推送到 GitHub"""
    print(f"\n🚀 开始发布版本: {version}")
    print(f"   描述: {message}")
    
    # 验证版本号
    validate_version(version)
    
    # 检查 git 状态
    print("\n📋 检查 Git 状态...")
    status = run_command("git status --porcelain", capture=True)
    if status:
        print("❌ 工作目录有未提交的变更:")
        print(status)
        print("\n请先提交所有变更:")
        print("  git add .")
        print("  git commit -m 'Your message'")
        sys.exit(1)
    print("✅ 工作目录干净")
    
    # 创建 tag
    print(f"\n🏷️  创建 tag: {version}")
    run_command(f'git tag -a {version} -m "{message}"')
    print(f"✅ Tag 创建成功")
    
    # 推送 tag
    print(f"\n📤 推送 tag 到 GitHub...")
    run_command(f"git push origin {version}")
    print("✅ Tag 推送成功")
    
    print(f"\n✨ 版本 {version} 已发布!")
    print("\n📌 GitHub Actions 将自动开始打包...")
    print("   请在以下位置查看进度:")
    print("   👉 https://github.com/YOUR_USERNAME/standard-downloader/actions")
    print(f"\n   打包完成后，可在 Releases 页面下载:")
    print(f"   👉 https://github.com/YOUR_USERNAME/standard-downloader/releases/tag/{version}")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python github_release.py <version> [message]")
        print("\n示例:")
        print("  python github_release.py v1.0.0")
        print("  python github_release.py v1.0.0 'Release v1.0.0 - First stable release'")
        sys.exit(1)
    
    version = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 else f"Release {version}"
    
    create_release(version, message)

if __name__ == "__main__":
    main()
