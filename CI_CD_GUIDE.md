# 自动化构建说明

## GitHub Actions 工作流

项目已配置 GitHub Actions 来自动构建 Windows 安装程序。

### 触发条件

工作流在以下情况自动触发：

1. **推送标签** - 当推送 `v*` 形式的标签时（如 `v1.0.0`）
2. **手动触发** - 在 GitHub Actions 页面手动运行

### 工作流步骤

1. ✅ 检出代码（含 Git LFS 文件）
2. ✅ 安装 Python 3.11
3. ✅ 安装所有依赖（requirements.txt）
4. ✅ 安装 PyInstaller 和 NSIS
5. ✅ 运行 `build_config.py` 生成 EXE
6. ✅ 运行 NSIS 生成安装程序
7. ✅ 上传到 GitHub Release
8. ✅ 保存制品（30 天）

### 如何发布新版本

#### 方式 1：通过命令行

```bash
# 创建并推送标签
git tag -a v1.0.1 -m "Release v1.0.1"
git push origin v1.0.1

# GitHub Actions 自动构建并创建 Release
```

#### 方式 2：手动触发

在 GitHub 网页上：
1. 进入 Actions 标签页
2. 选择 "Build Windows Installer" 工作流
3. 点击 "Run workflow"
4. 选择分支和输入版本号
5. 点击 "Run workflow"

### 发布的文件

构建完成后，GitHub Release 中会包含：

- `Installer.exe` - Windows 标准安装程序（推荐用户使用）
- `app.exe` - 独立可执行文件（免安装）

### 查看构建状态

1. 进入 GitHub 仓库
2. 点击 "Actions" 标签
3. 查看 "Build Windows Installer" 工作流的运行状态

### 构建失败时

检查 Actions 日志：
1. Actions → Build Windows Installer → 选择最新的运行
2. 查看"Build executable"或"Build NSIS installer"步骤的错误信息

常见问题：
- Python 依赖缺失 → 检查 `requirements.txt`
- NSIS 安装失败 → 检查 Chocolatey 是否可用
- 编码问题 → 确保文件为 UTF-8 编码

---

这样用户就可以直接从 [Releases](https://github.com/atpx4869/Multi-source-downloader/releases) 页面下载安装程序了！
