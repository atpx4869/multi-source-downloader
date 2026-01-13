#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 贡献图表自动化脚本
定期提交代码以保持 GitHub 贡献图表活跃
"""

import subprocess
import os
from datetime import datetime, timedelta
import random

def run_command(cmd):
    """执行命令"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def commit_with_date(message, days_ago=0):
    """使用指定日期进行提交"""
    # 计算日期
    target_date = datetime.now() - timedelta(days=days_ago)
    date_str = target_date.strftime("%Y-%m-%d %H:%M:%S")
    
    # 创建或更新一个日志文件
    log_file = "CONTRIBUTION_LOG.md"
    
    # 追加内容
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n- {date_str}: Activity recorded\n")
    
    # 暂存文件
    run_command("git add CONTRIBUTION_LOG.md")
    
    # 提交，使用指定的日期和时间
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    
    cmd = f'git commit -m "{message}"'
    subprocess.run(cmd, shell=True, env=env)
    
    print(f"✓ 已提交: {message} (日期: {date_str})")

def make_contributions(num_days=30):
    """生成过去 N 天的贡献记录"""
    print(f"开始生成 {num_days} 天的贡献记录...\n")
    
    for day in range(num_days):
        # 随机决定是否在这一天提交
        if random.random() > 0.3:  # 70% 概率提交
            # 随机提交次数 (1-3 次)
            num_commits = random.randint(1, 3)
            for i in range(num_commits):
                message = f"chore: activity update (day {num_days-day}, commit {i+1})"
                commit_with_date(message, days_ago=day)
    
    # 推送到远端
    print("\n开始推送到 GitHub...")
    success, stdout, stderr = run_command("git push origin main")
    
    if success:
        print("✓ 已成功推送到 GitHub")
    else:
        print(f"✗ 推送失败: {stderr}")

if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════╗
║         GitHub 贡献图表自动化脚本                              ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    # 验证 git 配置
    success, stdout, _ = run_command("git config user.email")
    if not stdout.strip():
        print("✗ 错误: 请先配置 git user.email")
        print("  运行: git config --global user.email 'your-email@example.com'")
        exit(1)
    
    print(f"✓ Git 用户邮箱: {stdout.strip()}")
    print()
    
    # 询问生成天数
    try:
        days = int(input("请输入要生成的天数 (默认 30): ") or "30")
    except ValueError:
        days = 30
    
    # 生成贡献记录
    make_contributions(days)
    
    print(f"\n✓ 完成！已生成 {days} 天的贡献记录。")
    print("  访问你的 GitHub 主页查看贡献图表变化。")
