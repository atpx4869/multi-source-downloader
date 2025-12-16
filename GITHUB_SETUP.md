# GitHub 上传和自动打包指南

本文档详细说明如何将项目上传到 GitHub 并设置自动打包。

## 📋 前置条件

1. **Git 已安装**：从 [git-scm.com](https://git-scm.com/download/win) 下载安装
2. **GitHub 账号**：注册于 [github.com](https://github.com)
3. **GitHub 认证**：
   - 方式 A（推荐）：使用 Personal Access Token
   - 方式 B：配置 SSH 密钥

---

## 🚀 第 1 步：本地 Git 初始化

在项目目录（`C:\Users\PengLinHao\Desktop\合并`）打开 PowerShell，执行：

```powershell
# 初始化 Git 仓库
git init

# 配置用户信息（使用你的 GitHub 用户名和邮箱）
git config user.name "YourGitHubUsername"
git config user.email "your.email@example.com"

# 查看配置是否成功
git config --list
```

---

## 📝 第 2 步：创建第一次提交

```powershell
# 添加所有文件到暂存区
git add .

# 检查要提交的文件
git status

# 创建首次提交
git commit -m "Initial commit: Clean PySide6 desktop application"

# 查看提交历史
git log --oneline
```

---

## 🌐 第 3 步：在 GitHub 上创建远程仓库

### 3.1 创建新仓库

1. 登录 GitHub 账号
2. 点击右上角 **+** → **New repository**
3. 填写信息：
   - **Repository name**：`standard-downloader` 或你喜欢的名字
   - **Description**：`A Chinese standard document downloader with multi-source support`
   - **Public/Private**：选择 Public（开源）或 Private（私有）
   - **Initialize repository**：**不勾选**（本地已有代码）
4. 点击 **Create repository**

### 3.2 连接本地仓库到 GitHub

创建成功后，GitHub 会显示推送指令。按以下步骤执行：

```powershell
# 添加远程仓库（替换 YOUR_USERNAME 和 REPO_NAME）
git remote add origin https://github.com/YOUR_USERNAME/standard-downloader.git

# 验证远程仓库配置
git remote -v

# 重命名主分支为 main（如果需要）
git branch -M main

# 推送到 GitHub
git push -u origin main
```

**需要输入凭证？**

- 如果使用 **HTTPS**：输入 GitHub 用户名和 Personal Access Token（不是密码）
- 如果提示保存凭证，选择 **Yes**

---

## 🔐 第 4 步：获取 Personal Access Token（如果使用 HTTPS）

1. 登录 GitHub
2. 点击右上角头像 → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. 点击 **Generate new token**
4. 设置：
   - **Token name**：`GitHub Push`
   - **Expiration**：No expiration（或自定义）
   - **Select scopes**：勾选 `repo`（完整控制）
5. 点击 **Generate token**
6. **复制 token**（关闭后无法再看）

在 Git 提示输入密码时，粘贴这个 token。

---

## 🤖 第 5 步：GitHub Actions 自动打包设置

### 5.1 工作流已自动创建

项目中已包含 `.github/workflows/build.yml`，会在以下情况自动触发：

- ✅ 推送到 `main` 或 `master` 分支
- ✅ 创建新的 Tag（版本发布）
- ✅ 手动触发（Actions 界面）

### 5.2 查看自动打包结果

1. 推送代码到 GitHub：
   ```powershell
   git push -u origin main
   ```

2. 在 GitHub 仓库页面：
   - 点击 **Actions** 标签
   - 查看最新的 workflow 运行状态
   - 等待 **Build Executable** 完成（通常 3-5 分钟）

3. 下载可执行文件：
   - 在 workflow 运行页面，点击 **Artifacts** 部分
   - 下载 `标准下载-executable.zip`

---

## 📦 第 6 步：创建版本发布（可选但推荐）

使用 Tag 和 Release 来正式发布版本：

### 6.1 创建本地 Tag

```powershell
# 创建 tag
git tag -a v1.0.0 -m "First release: v1.0.0"

# 推送 tag 到 GitHub
git push origin v1.0.0
```

### 6.2 在 GitHub 创建 Release

1. 在仓库页面，点击右侧 **Releases**
2. 点击 **Draft a new release**
3. 选择 Tag：`v1.0.0`
4. 填写信息：
   - **Release title**：`v1.0.0 - Initial Release`
   - **Description**：描述本版本的功能和改进
5. 点击 **Publish release**

### 6.3 自动生成可执行文件

- 当 Release 发布时，GitHub Actions 会自动打包
- 打包完成后，`.exe` 文件会自动上传到 Release 页面
- 用户可以直接从 Release 下载 `标准下载.exe`

---

## 🔄 工作流程总结

```
本地修改代码
    ↓
git add . && git commit -m "message"
    ↓
git push origin main
    ↓
GitHub Actions 自动触发
    ↓
编译 → 打包 → 上传到 Artifacts
    ↓
可下载 .exe 文件
```

---

## 🏷️ 日常开发流程

### 修改代码后推送

```powershell
# 查看改动
git status

# 添加改动
git add .

# 提交改动
git commit -m "Update feature XYZ"

# 推送到 GitHub
git push
```

### 发布新版本

```powershell
# 1. 修改版本号（可在 desktop_app.py 或 README 中更新）
# 2. 提交改动
git add .
git commit -m "v1.1.0: Add new features"

# 3. 创建 tag
git tag -a v1.1.0 -m "v1.1.0 release"

# 4. 推送 tag
git push origin v1.1.0

# GitHub Actions 自动打包并创建 Release（需在 GitHub 手动发布）
# 或在 GitHub Releases 页面手动创建
```

---

## ❓ 常见问题

### Q1：如何修改已推送的提交信息？

```powershell
# 修改最后一次提交
git commit --amend -m "New message"

# 强制推送（谨慎使用）
git push --force-with-lease
```

### Q2：如何删除错误推送的 commit？

```powershell
# 查看提交历史
git log --oneline

# 回滚到某个 commit
git reset --hard <commit-id>

# 强制推送
git push --force-with-lease
```

### Q3：GitHub Actions 打包失败怎么办？

1. 查看 **Actions** 标签中的错误日志
2. 常见原因：
   - 依赖未安装：检查 `requirements.txt`
   - 文件路径错误：检查 `build.yml` 中的路径
   - Python 版本不兼容：使用 Python 3.11+
3. 修复后重新推送，workflow 自动重试

### Q4：如何在本地测试打包？

```powershell
# 安装 PyInstaller
pip install pyinstaller

# 打包
pyinstaller --onefile `
  --name "标准下载" `
  --windowed `
  --collect-all PySide6 `
  desktop_app.py

# 查看输出
dir dist/
```

---

## 📚 有用链接

- [GitHub 文档](https://docs.github.com)
- [GitHub Actions 入门](https://docs.github.com/en/actions/quickstart)
- [PyInstaller 文档](https://pyinstaller.org)
- [Git 官方教程](https://git-scm.com/doc)

---

**现在，你可以开始推送代码到 GitHub 了！🎉**
