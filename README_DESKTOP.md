# 标准下载 - 桌面版

快速、高效的标准文档聚合下载工具。支持 GBW（国家标准）、BY（内部系统）、ZBY（标准云）多源搜索与批量下载。

## 功能

- **三源聚合搜索**：同时搜索 GBW、BY、ZBY 三大标准库
- **实时日志与进度**：后台线程不阻塞 UI，日志自动滚动展示
- **智能源检测**：60 秒缓存机制避免频繁检测
- **批量下载**：支持选中多条标准并批量下载
- **结果导出**：支持导出搜索结果为 CSV
- **灵活配置**：自定义数据源、下载目录、每页数量

## 快速开始

### 环境要求

- Python 3.11+
- Windows / macOS / Linux

### 安装

1. 克隆或下载项目：
```bash
cd 标准下载
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

3. 安装依赖：
```bash
pip install PySide6 pandas
```

### 运行

```bash
python desktop_app.py
```

窗口将在本地启动。操作流程：
1. 在顶部搜索框输入关键词（如 `GB/T 3324`）
2. 点击"🔍 检索"或按 Enter 键开始搜索
3. 在结果表中勾选要下载的行（支持多选）
4. 点击"📥 下载选中"，观察右侧日志窗口的实时进度
5. 可选：点击"💾 导出为 CSV"保存搜索结果

## 配置

### 菜单选项

**文件 → 设置**
- **启用的数据源**：选择要搜索的标准库（GBW、BY、ZBY）
- **下载配置**：设置下载目录和每页数量

**帮助 → 关于**
- 查看工具版本和功能说明

## 打包为 EXE（Windows）

如果希望打包为独立的 `.exe` 文件（不需要 Python 环境即可运行）：

### 方法 1：使用打包脚本

```bash
pip install pyinstaller
python build_exe.py
```

输出文件在 `dist/标准下载.exe`，可直接双击运行。

### 方法 2：手动 PyInstaller 命令

```bash
pip install pyinstaller
pyinstaller --onefile --name "标准下载" desktop_app.py
```

### 注意事项

- 首次打包可能需要几分钟
- 生成的 `.exe` 文件包含所有依赖，体积约 150-200MB
- 可选：指定图标 `--icon=icon.ico`（需提前准备 ICO 文件）

## 项目结构

```
.
├── desktop_app.py          # PySide6 桌面应用主文件
├── build_exe.py            # PyInstaller 打包脚本
├── core/                   # 业务逻辑核心库
│   ├── __init__.py
│   ├── aggregated_downloader.py
│   ├── gbw_download.py
│   ├── by_download.py
│   ├── zby_download.py
│   └── ...
├── sources/                # 数据源实现
├── downloads/              # 下载文件存储目录（自动创建）
└── README.md              # 本文件
```

## 常见问题

### Q: 搜索或下载为什么没有反应？

A: 检查右侧日志窗口是否有错误信息。可能的原因：
- 网络连接不稳定
- 数据源暂时不可用（可在设置中禁用该源）
- 关键词格式不正确

### Q: 如何修改默认下载目录？

A: 菜单 → 文件 → 设置 → 下载配置，修改"下载目录"字段。

### Q: 打包后的 EXE 文件能在没有网络的环境下运行吗？

A: 可以，但搜索和下载功能需要网络连接才能正常工作。

### Q: 如何隐藏服务器信息以保护隐私？

A: 代码中的 URL 和配置信息已在业务逻辑层进行了隐私处理，UI 界面仅显示"GBW / BY / ZBY"简称。

## 开发与扩展

若要扩展功能或修改 UI：

1. 修改 `desktop_app.py` 中的 `MainWindow` 类（UI 布局）或线程类（业务逻辑）
2. 修改 `core/aggregated_downloader.py` 以适配新的数据源或下载逻辑
3. 测试后重新打包

## 许可证

本项目仅限自用环境运行，不建议公开发布。

## 支持

如有问题，请查看日志信息或联系开发者。

---

**版本**: 1.0.0  
**更新**: 2025-12-16
