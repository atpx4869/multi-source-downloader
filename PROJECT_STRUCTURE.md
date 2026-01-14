# 项目文件结构说明

## 📂 项目组织

```
Multi-source-downloader/
├── 📄 核心文件
│   ├── desktop_app.py              # ⭐ 应用主入口 (PyQt6 GUI)
│   ├── ui_styles.py                # 界面样式配置
│   └── app.ico                     # 应用图标
│
├── 📁 源代码模块
│   ├── api/                        # API 接口 (BY, GBW, ZBY)
│   ├── core/                       # 核心功能 (下载、缓存、数据库)
│   ├── sources/                    # 数据源实现 (HTTP, Playwright)
│   ├── app/                        # GUI 应用组件
│   ├── examples/                   # 示例代码
│   ├── ppllocr/                    # OCR 识别模块
│   └── web_app/                    # Web 应用 (Flask)
│
├── ⚙️ 配置文件
│   ├── config/                     # API 配置目录
│   ├── setup.py                    # cx_Freeze 打包配置
│   ├── requirements.txt            # 主要依赖
│   └── requirements_win7.txt       # Windows 7 兼容依赖
│
├── 🚀 启动脚本
│   ├── run.bat                     # 应用启动 (需要 WinPython)
│   ├── setup-first-time.bat        # 首次安装依赖
│   └── package.bat                 # 打包工具
│
├── 📚 文档
│   ├── README.md                   # 项目说明
│   ├── CONTRIBUTION_GUIDE.md        # 贡献指南
│   ├── FINAL_PACKAGING_SOLUTION.md # ⭐ 最终打包方案
│   ├── CLEANUP_COMPLETE.md         # 清理报告
│   └── docs/                       # 详细文档目录
│
├── 💾 数据目录
│   ├── cache/                      # 缓存数据 (downloads/, search/)
│   └── data/                       # 应用数据
│
└── 🔧 系统文件
    ├── .git/                       # Git 版本控制
    ├── .github/                    # GitHub 配置
    ├── .gitignore                  # Git 忽略规则
    └── .venv/                      # Python 虚拟环境
```

---

## 📋 核心模块说明

### 🌐 API 模块 (`api/`)
- `base.py` - API 基类
- `by_api.py` - BY 来源 API (HTTP)
- `gbw_api.py` - GBW 来源 API (国家标准化管理委员会)
- `zby_api.py` - ZBY 来源 API (最完整的标准库)
- `models.py` - 数据模型
- `router.py` - API 路由

### 🔧 核心功能 (`core/`)
- `aggregated_downloader.py` - 多源聚合下载器 (支持多源 fallback)
- `api_client.py` - API 客户端 (包含超时保护)
- `api_config.py` - API 配置管理
- `cache_manager.py` - 缓存管理
- `database.py` - SQLite 数据库操作
- `download_queue.py` - 下载队列管理
- `loader.py` - 模块加载器
- `models.py` - 核心数据模型

### 📥 数据源 (`sources/`)
- `by.py` - BY 来源爬虫
- `gbw.py` - GBW 来源爬虫
- `gbw_download.py` - GBW 下载逻辑
- `zby.py` - ZBY 来源爬虫 (推荐)
- `zby_http.py` - ZBY HTTP 实现
- `zby_playwright.py` - ZBY Playwright 实现 (JS 渲染)
- `http_search.py` - HTTP 搜索通用工具
- `standard_downloader.py` - 通用标准下载器

### 🖥️ GUI 应用 (`app/`)
- `desktop_app_impl.py` - ⭐ 主应用实现 (4400+ 行)
- `excel_dialog.py` - Excel 导出对话框
- `history_dialog.py` - 下载历史对话框
- `queue_dialog.py` - 下载队列对话框

### 🕸️ Web 应用 (`web_app/`)
- `web_app.py` - Flask Web 应用
- `excel_standard_processor.py` - Excel 标准处理
- `templates/` - HTML 模板
- `index.html` - Web 主页面

---

## 🎯 关键优化说明

### ⏱️ 超时保护 (已优化)
- **总超时**: 20 秒/标准 (aggregated_downloader.py)
- **单源超时**: 10 秒/源 (core/aggregated_downloader.py)
- **机制**: ThreadPoolExecutor + join()
- **效果**: 最多 13 秒获得结果，避免卡顿

### 📊 批量下载优化
- **方法分解**: 6 个专用方法 (BatchDownloadThread)
- **错误分类**: 5 种错误类型 (DownloadErrorClassifier)
- **CSV 导出**: 支持导出失败项 (export_failed_to_csv)
- **重试机制**: 自动识别可重试的失败

### 🎨 进度显示
- 实时显示: 进度条、当前项、成功/失败统计
- 错误统计: 按错误类型分组
- 历史跟踪: 保存到数据库

---

## 🚀 运行指南

### 快速启动 (便携式 Python)

```bash
# 第一次运行 - 安装依赖
setup-first-time.bat

# 之后每次启动
run.bat
```

### 开发模式 (使用虚拟环境)

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行应用
python desktop_app.py
```

### 打包分发

参考: [FINAL_PACKAGING_SOLUTION.md](FINAL_PACKAGING_SOLUTION.md)

1. 下载 WinPython
2. 解压到 `WinPython-3.11.9/`
3. 运行 `setup-first-time.bat`
4. 压缩整个文件夹分发

---

## 📖 文件查询索引

| 需求 | 查看文件 |
|------|---------|
| 启动应用 | `desktop_app.py` |
| 修改 GUI | `app/desktop_app_impl.py` |
| 添加新数据源 | `sources/standard_downloader.py` |
| 修改下载逻辑 | `core/aggregated_downloader.py` |
| 配置 API | `config/api_config.json` |
| 修改样式 | `ui_styles.py` |
| Web 应用 | `web_app/web_app.py` |
| 打包应用 | `FINAL_PACKAGING_SOLUTION.md` + `run.bat` |
| 贡献代码 | `CONTRIBUTION_GUIDE.md` |

---

## 🔍 常用命令

```bash
# 运行应用
python desktop_app.py

# 运行 Web 应用
python web_app/web_app.py

# 生成可执行文件
python setup.py build_exe

# 清理缓存
find . -type d -name __pycache__ -exec rm -rf {} +

# 运行单个模块测试
python -m pytest api/tests/

# 查看项目统计
find . -name "*.py" | wc -l
```

---

## 🎓 学习路径

### 新手入门
1. 阅读 [README.md](README.md)
2. 运行应用体验功能
3. 查看 `examples/` 目录示例

### 开发贡献
1. 阅读 [CONTRIBUTION_GUIDE.md](CONTRIBUTION_GUIDE.md)
2. 研究 `core/aggregated_downloader.py` (核心逻辑)
3. 修改 `api/` 或 `sources/` 添加功能
4. 测试修改

### 高级定制
1. 修改 `app/desktop_app_impl.py` (GUI)
2. 修改 `web_app/` (Web 功能)
3. 参考 `config/` 配置系统

---

## 📊 统计信息

- **Python 文件**: ~150 个
- **代码行数**: ~15,000+ 行
- **文档**: 5+ 个详细指南
- **支持数据源**: 3 个 (ZBY, BY, GBW)
- **Python 版本**: 3.8+
- **UI 框架**: PyQt6 / PySide6

---

**最后更新**: 2026-01-14  
**项目状态**: ✅ 生产就绪

