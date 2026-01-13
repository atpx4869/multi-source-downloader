# GitHub 贡献图表（Contribution Graph）配置指南

## 什么是贡献图表？

GitHub 主页显示的彩色小格子叫 **Contribution Graph**，显示你在过去一年的提交活动。格子颜色越深，说明该天的提交次数越多。

## 显示条件

### 1. Git 配置正确
```bash
# 全局配置
git config --global user.name "Your Name"
git config --global user.email "your-email@github.com"

# 查看当前配置
git config --global user.email
```

### 2. 邮箱与 GitHub 账户关联
- 进入 GitHub Settings → Emails
- 确保提交邮箱已添加到账户
- 设置为 Primary Email（可选，但推荐）

### 3. 提交在默认分支上
- 提交必须在 `main` 或 `master` 分支
- 或在 fork 的仓库中

### 4. 提交必须来自你的账户
- 提交者邮箱必须与 GitHub 账户关联的邮箱匹配

## 快速检查清单

```bash
# 1. 验证 git 用户邮箱
git config user.email

# 2. 验证最近提交
git log --oneline -5

# 3. 查看提交的邮箱
git log -1 --format="%an <%ae>"

# 4. 查看当前分支
git branch

# 5. 推送到远端
git push origin main
```

## 常见问题

### Q: 提交后没有显示在图表里？

**A:** 检查以下几点：

1. **邮箱不匹配**
   ```bash
   # 查看提交邮箱
   git log --format="%ae" | head -5
   
   # 如果不对，重新配置
   git config --global user.email "correct-email@github.com"
   ```

2. **邮箱未在 GitHub 验证**
   - 进入 GitHub Settings → Emails
   - 确认邮箱已验证

3. **提交在错误的分支**
   ```bash
   git branch  # 确保在 main 或 master
   ```

4. **刚刚推送**
   - GitHub 需要 5-30 分钟才能更新图表
   - 清除浏览器缓存（Ctrl+Shift+Delete）

### Q: 如何恢复过去的提交活动？

使用 `contribute.py` 脚本生成历史提交：

```bash
python contribute.py
# 输入要生成的天数，脚本会创建历史提交记录
```

**注意：** 这会改变 git 历史，在团队项目中应谨慎使用！

### Q: 如何自动保持活跃？

#### 方案 1：GitHub Actions（推荐）

在 `.github/workflows/` 中创建 `daily-update.yml`：

```yaml
name: Daily Activity Update

on:
  schedule:
    - cron: '0 0 * * *'  # 每天 UTC 00:00 执行
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Update activity log
        run: |
          python daily_update.py
        env:
          GIT_USER_NAME: ${{ secrets.GIT_USER_NAME }}
          GIT_USER_EMAIL: ${{ secrets.GIT_USER_EMAIL }}
```

#### 方案 2：本地定时任务

**Windows（使用任务计划程序）：**
```
任务计划程序 → 创建基本任务 → 触发器设置为每天 9:00 AM → 操作运行 python daily_update.py
```

**Linux/Mac（使用 cron）：**
```bash
# 编辑 crontab
crontab -e

# 每天 9:00 AM 执行
0 9 * * * cd /path/to/repo && python daily_update.py
```

## 最佳实践

### 1. 有意义的提交
```bash
# 好的提交消息
git commit -m "feat: add new feature"
git commit -m "fix: resolve issue #123"
git commit -m "docs: update README"

# 避免
git commit -m "update"
git commit -m "fix"
```

### 2. 定期推送
- 不要积累太多本地提交
- 定期 push 到 GitHub

### 3. 保持活跃
```bash
# 每天至少进行一个有意义的提交
# 或使用自动化脚本
python daily_update.py
```

### 4. 多个仓库
如果有多个项目，在每个项目中进行提交，会增加整体活动显示

## GitHub Profile 优化

### 完整的 GitHub Profile 包括：

1. **README.md** - 个人简介
   ```markdown
   # Hi there 👋
   
   - 🔭 Currently working on ...
   - 🌱 Learning ...
   - 💬 Ask me about ...
   ```

2. **活跃的贡献图表** - 通过定期提交实现

3. **Pinned Repositories** - 固定你最好的项目
   - 进入仓库 → Settings → 勾选 "Include this repository in the profile README"

4. **完整的 Profile 信息**
   - Avatar（头像）
   - Bio（简介）
   - Company（公司）
   - Location（位置）
   - Links（链接）

## 工具和脚本

### 提供的脚本

1. **contribute.py** - 生成历史提交记录
   ```bash
   python contribute.py
   ```

2. **daily_update.py** - 每日活动更新
   ```bash
   python daily_update.py
   ```

### 推荐工具

- **GitKraken** - 可视化 git 管理
- **GitHub Desktop** - 官方桌面客户端
- **lazygit** - 命令行 git 工具

## 总结

要让贡献图表显示活动：

1. ✅ 配置正确的 git 邮箱
2. ✅ 确保邮箱在 GitHub 验证
3. ✅ 提交到默认分支（main）
4. ✅ 定期推送到远端
5. ✅ 使用自动化脚本保持活跃
6. ✅ 清除浏览器缓存查看最新状态

---

**参考：** https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/managing-contribution-graphs-on-your-profile/why-are-my-contributions-not-showing-up-on-my-profile
