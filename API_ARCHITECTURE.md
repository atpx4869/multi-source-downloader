# API 框架架构说明

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      应用层 (Application Layer)                   │
├─────────────────────────────────────────────────────────────────┤
│  • 桌面应用 (PyQt/PySide)                                        │
│  • Web 前端 (React/Vue)                                          │
│  • CLI 工具                                                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ REST API / Python API
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                      API 层 (api/ 包)                             │
├─────────────────────────────────────────────────────────────────┤
│  APIRouter (api/router.py)                                       │
│  ├─ search_single()        搜索单个源                            │
│  ├─ search_all()           搜索所有源                            │
│  ├─ download()             下载指定源                            │
│  ├─ download_first_available()  自动选择源                       │
│  └─ check_health()         健康检查                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
        ┌────────┴────────┬───────────────┬──────────────┐
        │                 │               │              │
┌───────▼────────┐ ┌─────▼──────┐ ┌──────▼─────┐ ┌──────▼─────┐
│  BYSourceAPI   │ │ ZBYSourceAPI│ │ GBWSourceAPI│ │ BaseSourceAPI│
│ (api/by_api.py)│ │(api/zby_api)│ │(api/gbw_api)│ │  (interface)  │
└───────┬────────┘ └─────┬──────┘ └──────┬─────┘ └──────┬─────┘
        │                │              │               │
        │  统一接口实现   │              │               │
        └────────┬────────┴──────────────┴────────────┬──┘
                 │                                     │
                 │ 调用源的实现                        │
                 │                                     │
┌────────────────▼────────────────────────────────────▼──────────┐
│                  源实现层 (sources/ 包)                          │
├─────────────────────────────────────────────────────────────────┤
│  • BYSource (sources/by.py)                                     │
│  • ZBYSource (sources/zby.py)                                   │
│  • GBWSource (sources/gbw.py)                                   │
│  • ZBYPlaywright (sources/zby_playwright.py)                    │
└─────────────────────────────────────────────────────────────────┘
```

## 数据流向

### 搜索流程

```
用户请求 (query: "GB/T 3324")
    ↓
APIRouter.search_all()
    ↓
遍历启用的源
    ├─→ BYSourceAPI.search()      → BYSource.search()      → 内网系统
    ├─→ ZBYSourceAPI.search()     → ZBYSource.search()     → Playwright / HTTP
    └─→ GBWSourceAPI.search()     → GBWSource.search()     → HTTP
    ↓
统一转换为 StandardInfo 对象
    ↓
返回 SearchResponse (包含所有结果)
    ↓
用户获得统一格式的数据，可直接 to_dict() 转为 JSON
```

### 下载流程

```
用户请求 (source: ZBY, std_no: "GB/T 3324-2024")
    ↓
APIRouter.download(source, std_no)
    ↓
ZBYSourceAPI.download()
    ↓
ZBYSource.download()
    ├─ search 获取标准信息
    ├─ 提取 standardId
    ├─ 打开详情页 (/standardDetail?standardId=...)
    ├─ 监听网络请求，捕获 immdoc UUID
    ├─ 下载图片页面
    └─ 合成为 PDF
    ↓
返回 DownloadResponse (包含文件路径、大小、日志等)
    ↓
用户获得统一的下载结果
```

## 核心设计原则

### 1. 统一接口 (Unified Interface)

所有源都实现 `BaseSourceAPI` 接口，提供一致的方法签名：

```python
class BaseSourceAPI(ABC):
    def search(self, query: str, limit: int) -> SearchResponse
    def download(self, std_no: str, output_dir: str, progress_callback) -> DownloadResponse
    def check_health(self) -> SourceHealth
```

### 2. 数据模型 (Data Models)

统一的数据模型确保输入输出格式一致：

- `StandardInfo`: 标准基本信息
- `SearchResponse`: 搜索结果
- `DownloadResponse`: 下载结果
- `SourceHealth`: 源健康状态

所有模型都支持：
- `.to_dict()` - 转换为字典
- JSON 序列化
- 类型检查

### 3. 灵活的源管理 (Flexible Source Management)

- 支持启用/禁用源
- 自动按优先级选择源
- 完整的错误处理
- 独立的初始化和健康检查

### 4. 可扩展性 (Extensibility)

添加新源只需：
1. 在 `sources/` 中实现源类
2. 在 `api/` 中创建 API 包装类
3. 在 `APIRouter` 中注册源

## 模块职责

### api/models.py
- 定义所有数据模型
- 支持 JSON 序列化
- 统一的响应格式

### api/base.py
- 定义 BaseSourceAPI 抽象接口
- 确保所有源都遵循相同的契约

### api/by_api.py, zby_api.py, gbw_api.py
- 实现 BaseSourceAPI 接口
- 对应的源实现的薄包装层
- 统一输入输出格式

### api/router.py
- 管理多个源的实例
- 编排搜索和下载逻辑
- 自动选择源
- 健康检查聚合

### api/__init__.py
- 导出公共 API
- 简化用户导入

## 集成场景

### 场景 1: 桌面应用

```python
from api import APIRouter, SourceType

class StandardDownloaderApp:
    def __init__(self):
        self.router = APIRouter()
    
    def on_search_button_clicked(self, query):
        # 在所有源中搜索
        results = self.router.search_all(query)
        # 更新 UI
        self.show_results(results)
    
    def on_download_button_clicked(self, source, std_no):
        # 下载标准
        response = self.router.download(source, std_no)
        # 更新 UI
        self.show_download_status(response)
```

### 场景 2: Web API

```python
from flask import Flask, request, jsonify
from api import APIRouter

app = Flask(__name__)
router = APIRouter()

@app.route('/api/search', methods=['GET'])
def search():
    query = request.args.get('q')
    results = router.search_all(query)
    return jsonify({src.value: res.to_dict() for src, res in results.items()})

@app.route('/api/download', methods=['POST'])
def download():
    data = request.json
    response = router.download(SourceType[data['source']], data['std_no'])
    return jsonify(response.to_dict())
```

### 场景 3: 命令行工具

```python
from api import APIRouter

def main():
    router = APIRouter()
    
    # 搜索
    results = router.search_all("GB/T 3324-2024")
    for source, response in results.items():
        print(f"{source.value}: {response.count} 结果")
    
    # 下载
    response = router.download_first_available("GB/T 3324-2024")
    print(f"下载: {response.filepath}")
```

## 性能考虑

### 搜索优化

- 并行搜索多个源（可选实现）
- 缓存搜索结果
- 限制返回结果数量

### 下载优化

- ZBY 源使用 Playwright 进行动态页面处理
- 支持重试机制
- 断点续传（未来实现）

### 健康检查

- 缓存检查结果（60 秒有效期）
- 异步执行（可选实现）

## 错误处理策略

```
源初始化失败
    ↓
SourceAPI 初始化时记录错误
    ↓
APIRouter 跳过该源
    ↓
返回响应时包含错误信息
    ↓
用户应用层处理错误

---

搜索失败
    ↓
SearchResponse.error 包含错误信息
    ↓
count = 0
    ↓
用户应用层检查 error 字段

---

下载失败
    ↓
DownloadResponse.status = ERROR / FAILED / NOT_FOUND
    ↓
error 字段包含详细信息
    ↓
logs 字段包含执行日志
    ↓
用户应用层根据 status 决定是否重试其他源
```

## 后续扩展方向

1. **缓存层**: 为搜索结果添加缓存
2. **异步 API**: 使用 async/await 提升性能
3. **WebSocket**: 实时推送下载进度
4. **数据库**: 存储搜索历史和下载记录
5. **认证**: 添加用户认证和权限管理
6. **监控**: 添加性能监控和日志系统
7. **分布式**: 支持分布式部署
