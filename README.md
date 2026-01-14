# Multi-Source Downloader

> 多源数据下载器 | 标准文献智能查新工具

一个功能强大的桌面应用，集多源数据下载、标准文献查询、批量信息补全于一体。

## ✨ 核心功能

### 📥 多源数据下载
- 聚合多个数据源（ZBY、GBW、BY 等）
- 统一搜索接口，智能结果聚合
- 断点续传、批量下载支持
- 实时进度反馈和错误处理

### 📋 标准文献查新
- **批量查询**：上传标准号列表，自动补全元数据
- **智能匹配**：支持模糊查询、版本自动识别
- **替代标准检测**：自动识别新旧版本关系
- **彩色渲染**：不同状态不同颜色（现行/废止/即将实施）
- **格式化导出**：Excel导出支持颜色、对齐、自适应列宽

### 🎯 数据补全
- 获取：发布日期、实施日期、状态、替代标准等完整信息
- 支持 Excel/CSV 导出
- 批量处理，性能优化

### 🖥️ 用户界面
- 现代化 PyQt5 界面
- 直观的操作流程
- 详细的日志和反馈
- 自定义配置面板

## 🔧 系统要求

- **Windows 7 或更新版本**
- **Python 3.8+** （如果从源码运行）
- **互联网连接**（用于API调用）

## 📦 安装和使用

### 方式一：可执行文件（推荐）

从 [Releases](https://github.com/atpx4869/Multi-source-downloader/releases) 下载最新版本，直接运行即可。

### 方式二：从源码运行

1. **克隆仓库：**
   ```bash
   git clone https://github.com/atpx4869/Multi-source-downloader.git
   cd Multi-source-downloader
   ```

2. **创建虚拟环境：**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **安装依赖：**
   ```bash
   pip install -r requirements.txt
   ```

4. **运行应用：**
   ```bash
   python desktop_app.py
   ```

## ⚙️ 配置

### API 配置

编辑 `config/api_config.json` 配置数据源：

```json
{
  "zby": {
    "enabled": true,
    "timeout": 30
  },
  "gbw": {
    "enabled": true,
    "timeout": 30
  },
  "by": {
    "enabled": true,
    "timeout": 30
  }
}
```

详见 `config/API_CONFIG_GUIDE.md`

## 📁 项目结构

```
multi-source-downloader/
├── api/                      # 数据源 API 适配层
├── app/                      # 桌面应用 UI 层
│   ├── desktop_app_impl.py   # 主窗口实现
│   ├── standard_info_dialog.py # 标准查新对话框
│   ├── excel_dialog.py       # Excel导入对话框
│   └── ...
├── config/                   # 配置文件和指南
├── core/                     # 核心业务逻辑
│   ├── aggregated_downloader.py  # 聚合搜索引擎
│   ├── api_client.py         # API 调用层
│   ├── cache_manager.py      # 缓存管理
│   └── ...
├── sources/                  # 数据源实现
│   ├── zby.py               # 中标委数据源
│   ├── gbw.py               # 国标网数据源
│   ├── by.py                # 标准分享网数据源
│   └── ...
├── web_app/                  # Web 版本相关
├── docs/                     # 文档
├── examples/                 # 使用示例
└── requirements.txt          # Python 依赖
```

## 🚀 使用示例

### 1. 标准查新

1. 打开应用，进入"标准查新"选项卡
2. 上传包含标准号的 Excel/CSV 文件（支持批量）
3. 点击"开始查询"，系统自动从多个数据源查询
4. 查看结果表格，不同颜色标记不同状态
5. 导出为 Excel，格式化表格已保留

### 2. 多源数据搜索

1. 在主搜索框输入关键词
2. 选择要搜索的数据源
3. 系统聚合多源结果
4. 支持下载、导出等操作

### 3. 标准信息补全

- 自动检测不完整的标准号
- 智能推荐完整的标准信息
- 支持批量处理

## 📊 性能指标

| 操作 | 性能 |
|------|------|
| 单条标准查询 | ~0.3-0.5 秒 |
| 批量处理（100项） | ~1-2 分钟 |
| 应用启动 | ~2-3 秒 |
| 缓存命中 | 毫秒级 |

## 🐛 故障排查

### 常见问题

| 问题 | 解决方案 |
|------|--------|
| API 连接超时 | 检查网络、增加超时时间 |
| 找不到标准 | 检查标准号格式、尝试其他数据源 |
| Excel 导出失败 | 关闭其他打开的 Excel 文件 |
| 程序启动缓慢 | 清理缓存：删除 `cache/` 文件夹 |

### 清理缓存

```bash
# 删除所有缓存
Remove-Item cache/* -Recurse
```

## 📚 文档

- [API 架构说明](config/API_CONFIG_GUIDE.md)
- [本地运行指南](docs/guides/LOCAL_RUN_GUIDE.md)
- [性能优化建议](docs/guides/PERFORMANCE_OPTIMIZATION.md)
- [Excel 工具使用](web_app/WEB_APP_GUIDE.md)

## 🔄 技术栈

- **前端**：PyQt5 / PySide6
- **后端**：Python 3.8+
- **数据处理**：Pandas、openpyxl
- **网络**：aiohttp、requests、playwright
- **缓存**：SQLite

## 💡 工作原理

```
用户输入标准号
    ↓
智能解析和标准化
    ↓
多源并行查询（ZBY、GBW、BY）
    ↓
结果聚合和去重
    ↓
版本智能比对和替代检测
    ↓
格式化输出（UI 显示/Excel 导出）
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目仅供个人和内部使用。

## 📞 支持

如有问题或建议，请在 GitHub 提交 Issue。

---

**版本**：4.0+  
**最后更新**：2026 年 1 月
