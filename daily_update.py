#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 活动日志生成脚本
定期更新项目以在 GitHub 贡献图表显示活动
"""

import subprocess
from datetime import datetime
import os

def update_contribution_log():
    """更新贡献日志"""
    
    log_file = "ACTIVITY_LOG.txt"
    
    # 创建或追加日志
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 读取或创建文件
    if os.path.exists(log_file):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] Project activity recorded")
    else:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"# GitHub Activity Log\n\n[{timestamp}] Initial log created")
    
    # 暂存文件
    run_cmd("git add ACTIVITY_LOG.txt")
    
    # 提交
    message = f"chore: activity log update at {timestamp}"
    run_cmd(f'git commit -m "{message}"')
    
    # 推送
    run_cmd("git push origin main")
    
    return timestamp

def run_cmd(cmd):
    """执行命令"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

if __name__ == "__main__":
    timestamp = update_contribution_log()
    print(f"✓ 已更新贡献记录: {timestamp}")
