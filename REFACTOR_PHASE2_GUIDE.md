# Phase 2 Service 层重构 - 快速参考

## ✅ 已完成

### 1. 基础设施 (`core/service_base.py`)

- **TaskStatus** 枚举：PENDING → RUNNING → COMPLETED/FAILED/CANCELLED
- **TaskEvent** 数据类：统一的事件结构
- **IService** + **IEventEmitter** 接口
- **BaseService** 基类：事件管理和生命周期

### 2. 下载服务 (`core/download_service.py`)

```python
from core import DownloadService, DownloadTask

# 创建服务
service = DownloadService(max_workers=3)
service.start()

# 订阅事件
def on_completed(event: TaskEvent):
    print(f"✅ 下载完成: {event.result.file_path}")

service.subscribe("completed", on_completed)
service.subscribe("failed", lambda e: print(f"❌ {e.error}"))
service.subscribe("progress", lambda e: print(f"📊 {e.message}"))

# 提交任务
task = service.submit(
    standard=std,
    output_dir=Path("downloads"),
    priority=0
)

# 查询状态
status = service.get_status(task.id)
print(f"Status: {status.status}")

# 取消任务
service.cancel(task.id)

# 关闭服务
service.stop()
```

**关键方法：**

```python
service.submit(std, outdir, priority=0) -> DownloadTask
service.get_status(task_id) -> DownloadTask
service.cancel(task_id) -> bool
service.get_all_tasks() -> List[DownloadTask]
service.get_pending_tasks() -> List[DownloadTask]
service.get_running_tasks() -> List[DownloadTask]
service.get_completed_tasks() -> List[DownloadTask]
service.get_failed_tasks() -> List[DownloadTask]
```

### 3. 搜索服务 (`core/search_service.py`)

```python
from core import SearchService, SearchTask

service = SearchService(max_workers=3)
service.start()

# 订阅事件
service.subscribe("progress", lambda e: print(f"📊 {e.message}"))
service.subscribe("completed", lambda e: print(f"✅ 找到 {len(e.result)} 条"))

# 提交搜索任务
task = service.submit(keyword="GB 6675")

# 流式获取结果
for std in service.stream_results(task.id):
    print(f"{std.std_no}: {std.name}")

service.stop()
```

**关键方法：**

```python
service.submit(keyword) -> SearchTask
service.get_status(task_id) -> SearchTask
service.stream_results(task_id) -> Iterator[Standard]  # 阻塞式
service.get_all_tasks() -> List[SearchTask]
```

---

## 🔄 事件模型

所有服务都支持事件订阅：

```python
service.subscribe(event_type, callback)
service.unsubscribe(event_type, callback)
```

**事件类型：**

- `"submitted"` - 任务已提交
- `"progress"` - 任务进行中
- `"completed"` - 任务完成
- `"failed"` - 任务失败
- `"cancelled"` - 任务取消

**事件对象 (TaskEvent)：**

```python
@dataclass
class TaskEvent:
    task_id: str                      # 任务 ID
    event_type: str                   # submitted, progress, completed, ...
    status: TaskStatus                # 当前状态
    message: str                      # 用户友好的消息
    progress: Optional[int]           # 0-100（可选）
    error: Optional[str]              # 错误信息（失败时）
    result: Optional[Any]             # 结果数据（完成时）
    timestamp: datetime               # 事件时间戳
```

---

## 📊 架构对比

### Before (当前)
```
UI 层
  ↓
 直接操作 QThread
  ↓
 下载器/搜索器
  ↓
 数据源 (GBW, ZBY, BY)
```

**问题：**
- UI 知道线程细节
- 混乱的返回值处理
- 难以扩展（需改 UI 代码）

### After (Phase 2+)
```
UI 层
  ↓
Service 层（DownloadService, SearchService）
  ↓
 事件 (progress, completed, failed)
  ↓
工作线程池 (ThreadPoolExecutor)
  ↓
下载器/搜索器
  ↓
数据源 (GBW, ZBY, BY)
```

**优点：**
- UI 完全解耦，只监听事件
- Service 管理所有状态和生命周期
- 易于扩展（加新功能只需改 Service）
- 支持任务队列、持久化、恢复等

---

## 📝 DownloadTask vs DownloadResult

- **DownloadTask** (服务层)
  - 代表一个"下载任务"的生命周期
  - 包含：ID, 状态, 时间戳, 日志
  - 由 Service 管理

- **DownloadResult** (源层)
  - 代表一次"下载操作"的结果
  - 包含：success, file_path, error, logs
  - 由源返回

**关系：**
```
task.result = source.download(std, outdir)  # DownloadResult
```

---

## 🚀 Phase 3 的改进空间

1. **任务持久化**
   ```python
   service.save_state("tasks.json")
   service.load_state("tasks.json")
   ```

2. **任务优先级队列**
   ```python
   task = service.submit(..., priority=1)
   ```

3. **自动重试机制**
   ```python
   service.config.max_retries = 3
   ```

4. **任务历史 & 统计**
   ```python
   stats = service.get_statistics()
   history = service.get_history(start_date, end_date)
   ```

5. **Web API**
   ```
   GET /api/tasks
   POST /api/tasks/{id}/cancel
   GET /api/tasks/{id}/status
   ```

---

## 测试示例

```python
# test_service.py
from core import DownloadService, SearchService
from pathlib import Path

def test_download_service():
    service = DownloadService(max_workers=2)
    service.start()
    
    completed = []
    service.subscribe("completed", lambda e: completed.append(e))
    
    task = service.submit(std, Path("downloads"))
    
    # 等待完成
    import time
    while task.status.value == "running":
        time.sleep(0.1)
    
    assert len(completed) == 1
    assert completed[0].result.success
    
    service.stop()

def test_search_service():
    service = SearchService(max_workers=2)
    service.start()
    
    task = service.submit(keyword="GB 6675")
    
    results = list(service.stream_results(task.id))
    assert len(results) > 0
    
    service.stop()
```

---

## 下一步（Phase 2 → Phase 3）

### 立即可做
1. ✅ 服务基础设施完成（当前）
2. ⏳ 修改 UI 使用新服务（下一步）
3. ⏳ 集成测试

### 后续改进
1. 日志系统统一
2. 配置管理（app.config）
3. 任务持久化
4. Web API 层

