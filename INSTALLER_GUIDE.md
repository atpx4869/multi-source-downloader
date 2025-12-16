# 标准下载 - Windows 安装程序指南

## 快速开始

### 方式 1：使用安装程序（推荐）

1. **下载安装程序**
   - 从 GitHub Releases 下载 `Installer.exe`

2. **运行安装程序**
   - 双击 `Installer.exe`
   - 按照向导完成安装（选择安装路径）
   - 自动创建开始菜单和桌面快捷方式

3. **启动应用**
   - 从开始菜单或桌面快捷方式启动

### 方式 2：直接运行（免安装）

- 直接双击 `app.exe` 立即运行（无需安装）

### 方式 3：卸载

**Windows 设置：**
- 打开 "设置" → "应用" → "应用和功能"
- 找到 "Standard Downloader"
- 点击卸载

**或通过开始菜单：**
- 开始菜单 → 标准下载 → 卸载

## 系统要求

- Windows 10 或更高版本
- 磁盘空间：约 800 MB（安装 + 应用）
- 无需安装 Python 或任何其他环境

## 文件说明

| 文件 | 说明 |
|------|------|
| `Installer.exe` | 标准 Windows 安装程序（推荐） |
| `app.exe` | 独立可执行文件（直接运行） |

## 故障排除

### 无法启动应用

1. 确保已安装最新的 Windows 更新
2. 检查磁盘空间是否充足
3. 尝试以管理员身份运行

### 权限错误

- 右击 `Installer.exe` → "以管理员身份运行"

## 版本信息

- 构建日期：2025-12-16
- 包含模块：PySide6, pandas, onnxruntime, PIL
- 包大小：约 400 MB

---

需要帮助？提交 Issue：https://github.com/atpx4869/Multi-source-downloader/issues
