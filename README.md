# 标准下载 - 桌面应用

一款高效的中文标准文档下载工具，支持多个数据源（国家标准、内部系统、标准云等），提供友好的图形界面。

## 功能特性

- 📚 **多源支持**：聚合多个标准数据源
  - GBW（国家标准）
  - BY（内部系统）
  - ZBY（标准云）

- 🔍 **快速搜索**：实时搜索标准号、名称等
- 📥 **批量下载**：支持选中多个标准进行批量下载
- 💾 **导出功能**：将搜索结果导出为 CSV 格式
- ⚙️ **自定义路径**：灵活设置下载目录
- 📊 **实时日志**：查看操作日志和下载进度
- 🔗 **连通性检测**：自动检测各数据源的可用状态

## 系统要求

- Windows 10 或更高版本
- Python 3.8+（如果从源码运行）

## 快速开始

### 方式 1：使用可执行文件（推荐）

从 [GitHub Releases](../../releases) 下载最新的 `标准下载.exe`，双击即可运行。

### 方式 2：从源码运行

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/standard-downloader.git
cd standard-downloader

# 2. 创建虚拟环境（可选但推荐）
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行应用
python desktop_app.py
```

## 项目结构

```
.
├── desktop_app.py          # 主应用（PySide6 GUI）
├── core/                   # 核心业务逻辑
│   ├── __init__.py
│   ├── aggregated_downloader.py    # 多源聚合下载器
│   ├── by_download.py      # BY 源下载模块
│   ├── by_source.py        # BY 源连接模块
│   ├── gbw_download.py     # GBW 源下载模块
│   ├── gbw_source.py       # GBW 源连接模块
│   ├── standard_downloader.py      # 标准下载基类
│   ├── zby_download.py     # ZBY 源下载模块
│   └── zby_source.py       # ZBY 源连接模块
├── ppllocr/                # OCR 支持库
├── requirements.txt        # Python 依赖
├── README.md              # 本文件
└── README_DESKTOP.md      # 桌面应用详细说明
```

## 核心特性

### 📊 多源聚合
- **GBW**：国家标准官方库
- **BY**：内部系统数据源
- **ZBY**：标准云开放平台

### 🔗 源连通性检测
- 自动检测各数据源可用状态
- 实时显示源连通情况
- 搜索时智能跳过不可用源

### 💻 现代化界面
- PySide6 跨平台 GUI
- 实时日志面板
- 快速路径设置
- 搜索结果 CSV 导出

## 技术栈

- **GUI 框架**：PySide6（Qt6 Python 绑定）
- **数据处理**：pandas
- **并发处理**：Python threading + Qt signals/slots
- **网络请求**：requests, urllib3
- **OCR 支持**：ppllocr

## 依赖

```bash
pip install -r requirements.txt
```

## 许可证

MIT License - 详见 LICENSE 文件（如存在）
