# 标准下载器 EXE 打包 - 快速解决方案

> **问题**: PyInstaller 和 cx_Freeze 都在处理 PySide6 时出现问题  
> **原因**: 这个项目的依赖复杂（PySide6 + Playwright + pandas 等）  
> **解决**: 使用**便携式 Python** 方案（最简单、最可靠）

---

## 🎯 推荐方案：便携式 Python（5分钟完成）

不需要编译，直接分发 Python + 脚本

### 第 1 步：下载便携式 Python

下载 **WinPython**（免费便携式 Python）：
- **官网**: https://winpython.github.io/
- **下载**: 选择 `Python 3.11` + `Bundle with Jupyter` 版本
- **大小**: ~500MB

### 第 2 步：解压到项目目录

```
Multi-source-downloader/
├── WinPython-3.11.X/     ← 解压 WinPython 到这里
├── desktop_app.py
├── run.bat               ← 新建这个文件
└── ... (其他文件)
```

### 第 3 步：创建启动脚本 `run.bat`

在项目根目录创建文件 `run.bat`，内容如下：

```batch
@echo off
chcp 65001 > nul
WinPython-3.11.9\python.exe desktop_app.py
pause
```

### 第 4 步：安装依赖（一次性）

```batch
WinPython-3.11.9\Scripts\pip.exe install -r requirements.txt
```

### 第 5 步：打包分发

将整个文件夹压缩：
```
Multi-source-downloader.zip  (~600MB)
```

**用户使用**:
1. 解压 `Multi-source-downloader.zip`
2. 双击 `run.bat`
3. 应用启动

---

## ✅ 优点

| 优点 | 说明 |
|------|------|
| ✅ 100% 兼容 | 完全规避 PyInstaller/cx_Freeze 的 PySide6 问题 |
| ✅ 超快启动 | 直接 Python 执行，无编译开销 |
| ✅ 易于维护 | 更新依赖只需 pip install |
| ✅ 零编译 | 不依赖编译工具链 |
| ✅ 跨平台基础 | 相同代码可运行在不同 Python 版本上 |

## ⚠️ 缺点

| 缺点 | 解决方案 |
|------|---------|
| ❌ 包体积大 (~600MB) | 可用 7-Zip 压缩到 200MB |
| ❌ 启动较慢 (2-3秒) | 正常，Electron 应用也这样 |
| ❌ 用户看得到 Python 目录 | 可用 `folder_lock` 隐藏 |

---

## 💡 完整打包步骤（详细版）

### 1. 下载 WinPython
```bash
# 方式 1：手动下载
# 访问 https://winpython.github.io/
# 下载 `winpython-64bit-3.11.X.exe`

# 方式 2：命令行下载（需要 curl）
curl -O https://github.com/winpython/winpython/releases/download/.../WinPython64-3.11.X.exe
```

### 2. 解压 WinPython
```bash
# 直接解压到项目目录
# WinPython-3.11.X/  <- 这个目录
```

### 3. 创建 `run.bat`
```batch
@echo off
REM 设置编码为 UTF-8
chcp 65001 > nul

REM 运行应用
WinPython-3.11.9\python.exe desktop_app.py

REM 如果有错误，暂停让用户看到
if errorlevel 1 pause
```

### 4. 创建 `requirements_distribute.txt`（仅分发版需要的）
```
PySide6>=6.0
Playwright>=1.40
openpyxl>=3.0
requests>=2.28
beautifulsoup4>=4.11
lxml>=4.9
```

### 5. 创建 `首次运行.bat`（自动安装依赖）
```batch
@echo off
echo 正在安装依赖... (首次运行，需要几分钟)
WinPython-3.11.9\Scripts\pip.exe install -r requirements_distribute.txt
echo 安装完成！
pause
```

### 6. 压缩分发
```bash
# 使用 7-Zip（压缩率最高）
7z a -t7z -m0=lzma2 -mx=9 Multi-source-downloader.7z Multi-source-downloader/

# 或使用 ZIP（更兼容）
# 直接在 Windows 资源管理器中右键 → 发送到 → 压缩文件夹
```

### 7. 文件清单
```
Multi-source-downloader/
├── WinPython-3.11.9/           # 便携式 Python 环境
├── api/                        # 项目源代码
├── core/
├── sources/
├── app/
├── desktop_app.py
├── requirements_distribute.txt
├── run.bat                     # 用户双击这个
├── 首次运行.bat                # 用户首次运行这个
├── README.md                   # 安装说明
└── ... (其他文件)
```

---

## 📋 用户使用说明 (README.md)

```markdown
# 标准下载器 - 使用说明

## 第一次使用（需要 5 分钟）

1. **安装依赖**
   - 双击 `首次运行.bat`
   - 等待安装完成
   - 关闭窗口

2. **启动应用**
   - 双击 `run.bat`
   - 应用启动

## 之后每次启动
- 双击 `run.bat`

## 如果遇到问题
- 重新运行 `首次运行.bat` 
- 或联系技术支持

## 系统要求
- Windows 10 以上
- 磁盘空间：至少 1GB
```

---

##  生成脚本版本 `build_package.bat`

将所有打包步骤自动化：

```batch
@echo off
setlocal enabledelayedexpansion

echo ========================================
echo  标准下载器 - 便携式打包工具
echo ========================================

REM 清理旧构建
echo.
echo [1/5] 清理旧文件...
if exist Multi-source-downloader-dist rmdir /s /q Multi-source-downloader-dist
echo  OK

REM 复制项目文件
echo.
echo [2/5] 复制项目文件...
mkdir Multi-source-downloader-dist
xcopy /E /I api Multi-source-downloader-dist\api
xcopy /E /I core Multi-source-downloader-dist\core
xcopy /E /I sources Multi-source-downloader-dist\sources
xcopy /E /I app Multi-source-downloader-dist\app
xcopy /E /I config Multi-source-downloader-dist\config
xcopy /E /I web_app Multi-source-downloader-dist\web_app
copy desktop_app.py Multi-source-downloader-dist\
copy requirements.txt Multi-source-downloader-dist\requirements_distribute.txt
copy app.ico Multi-source-downloader-dist\
echo  OK

REM 创建批处理脚本
echo.
echo [3/5] 创建启动脚本...
(
  echo @echo off
  echo chcp 65001 ^> nul
  echo WinPython-3.11.9\python.exe desktop_app.py
  echo if errorlevel 1 pause
) > Multi-source-downloader-dist\run.bat
echo  OK

REM 创建安装脚本
echo.
echo [4/5] 创建安装脚本...
(
  echo @echo off
  echo echo Initializing dependencies...
  echo WinPython-3.11.9\Scripts\pip.exe install -r requirements_distribute.txt
  echo echo Installation complete!
  echo pause
) > Multi-source-downloader-dist\setup-first-time.bat
echo  OK

REM 压缩
echo.
echo [5/5] 压缩文件...
echo  Please download and install 7-Zip manually, then run:
echo  7z a -t7z -m0=lzma2 -mx=9 Multi-source-downloader.7z Multi-source-downloader-dist\

echo.
echo ========================================
echo  打包完成！
echo ========================================
echo.
echo 下一步：
echo  1. 下载 WinPython-3.11.9 到 Multi-source-downloader-dist\
echo  2. 运行：7z a Multi-source-downloader.7z Multi-source-downloader-dist\
echo  3. 生成的文件：Multi-source-downloader.7z
echo.
pause
```

---

## 对比：各打包方案最终评估

| 方案 | 时间 | 体积 | 可靠性 | 推荐度 |
|------|------|------|--------|--------|
| **便携式 Python** | 5分钟 | 600MB (200MB压缩) | ⭐⭐⭐⭐⭐ | ✅ **推荐** |
| PyInstaller 6.17 | 5分钟 | 300MB | ❌ PySide6 问题 | ❌ 放弃 |
| cx_Freeze | 5分钟 | 250MB | ❌ 失败 | ❌ 放弃 |
| Nuitka | 30分钟 | 150MB | ⭐⭐⭐ 缓慢 | ⏳ 不推荐 |

---

## 总结

**面对 PyInstaller / cx_Freeze 的 PySide6 兼容性问题时，便携式 Python 是最简洁、最可靠的解决方案。** 

虽然包体积大一些，但：
- ✅ 100% 保证能用
- ✅ 无编译复杂度
- ✅ 用户体验一致
- ✅ 维护成本低

**立即开始**: 
1. 下载 WinPython
2. 创建 `run.bat`
3. 压缩分发
4. 完成！

