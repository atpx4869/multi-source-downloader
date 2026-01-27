# Phase 3 - UI 层集成指南

**状态**: 进行中  
**目标**: 整合 UI 层与 Service 层，启用新的任务管理和并发框架  
**预计工作量**: 2-3 天

---

## 概述

Phase 3 是架构重构的最后一步，将之前创建的 Service 层（Phase 2）和 Registry 系统（Phase 1）集成到现有的 UI 层。核心思想是**逐步迁移** UI 代码到新架构，同时维护向后兼容性。

### 关键改变

| 方面 | 之前 | 之后 | 好处 |
|------|------|------|------|
| 线程管理 | QThread 在 UI 中分散 | ThreadPoolExecutor 在 Service 中 | 关注点分离，易于测试 |
| 任务状态 | 临时变量追踪 | TaskStatus + TaskEvent | 完整的状态机和事件流 |
| 错误处理 | 异常捕获分散 | DownloadResult 统一收集 | 一致的错误信息 |
| 扩展性 | 修改多个源文件添加新功能 | 通过 Registry 装饰器添加 | 减少改动范围 |

---

## Phase 3 的三个子阶段

### 阶段 3.1：适配器层（DONE ✅）

**目标**: 创建 UI 和 Service 层之间的桥梁

**实现**:
- `UIDownloadAdapter`: 将 DownloadService 事件转换为 Qt Signal
- `UISearchAdapter`: 将 SearchService 事件转换为 Qt Signal
- 全局单例: `get_download_adapter()`, `get_search_adapter()`

**特点**:
- 信号名称与原有 UI 兼容（download_started, download_progress, download_completed）
- 批次管理（多个标准一次提交）
- 原有 UI 代码改动最小

**文件**: `app/ui_service_adapter.py`

### 阶段 3.2：UI 集成（下一步）

**目标**: 修改 UI 代码使用 UIDownloadAdapter 和 UISearchAdapter

**修改范围**:
1. `app/desktop_app_impl.py` 中的下载相关方法：
   - `on_download()` - 提交下载任务
   - `on_download_progress()` - 处理进度信号
   - `on_download_finished()` - 处理完成信号
   - `_show_download_list()` - 显示下载队列（新功能）

2. `app/desktop_app_impl.py` 中的搜索相关方法：
   - `on_enhanced_search()` - 提交搜索任务
   - `_on_search_result()` - 处理搜索结果

**不修改**:
- UI 布局和样式
- 用户交互逻辑
- 信号-槽连接方式（外部保持不变）

### 阶段 3.3：测试与优化（之后）

**目标**: 验证所有功能正常，性能满足要求

**测试内容**:
- 单下载
- 批量下载
- 取消下载
- 搜索功能
- 错误处理
- 多线程安全

---

## 技术细节

### 信号映射

**DownloadService 事件 → Qt Signal**:
```
"progress" event → download_progress signal
    event.task_id → task_id
    event.message → message
    
"completed" event → download_completed signal
    event.task_id → task_id
    event.result.file_path → file_path
    
"failed" event → download_failed signal
    event.task_id → task_id
    event.error → error_message
```

### 使用示例

```python
# 获取适配器
adapter = get_download_adapter()

# 连接信号
adapter.download_progress.connect(self.on_download_progress)
adapter.download_completed.connect(self.on_download_finished)
adapter.download_failed.connect(self.on_download_error)
adapter.all_downloads_finished.connect(self.on_batch_completed)

# 提交下载
task_ids = adapter.submit_downloads(
    standards=[std1, std2, std3],
    output_dir=Path("./downloads"),
    batch_callback=lambda s, f: print(f"Success: {s}, Failed: {f}")
)

# 获取状态
status = adapter.get_status(task_ids[0])
batch_status = adapter.get_batch_status()  # 返回 {"total": 3, "running": 1, "completed": 1, "failed": 1}

# 取消下载
adapter.cancel_download(task_ids[0])
```

### 线程安全

- Service 层使用 ThreadPoolExecutor（线程安全的）
- UI 线程通过信号进行通信（Qt 提供线程安全）
- 适配器中的 `_batch_tasks` 列表在主线程中访问（安全）
- 任何跨线程访问都通过 Signal/Slot 或 ThreadPoolExecutor 队列

---

## 迁移策略

### 不破坏现有代码的关键

1. **信号兼容**: 新信号名称与旧代码期望的槽匹配
2. **异步兼容**: Service 层也是异步的（不会阻塞 UI）
3. **错误兼容**: 错误通过 `download_failed` 信号发送（与原有 on_download_error 兼容）
4. **进度兼容**: 进度通过 `download_progress` 信号发送（与原有处理方式兼容）

### 示例：迁移 on_download() 方法

**原有代码**:
```python
def on_download(self):
    # ... 获取标准列表 ...
    self.download_thread = DownloadThread(standards, output_dir)
    self.download_thread.progress.connect(self.on_download_progress)
    self.download_thread.finished.connect(self.on_download_finished)
    self.download_thread.start()
```

**迁移后**:
```python
def on_download(self):
    # ... 获取标准列表 ...
    adapter = get_download_adapter()
    task_ids = adapter.submit_downloads(standards, output_dir)
    # 信号已在 __init__ 中连接，无需再连接
```

---

## 回滚计划

如果出现问题，可以通过 git 恢复：

```bash
# 查看提交历史
git log --oneline | head -20

# 回滚到 Phase 2 完成时
git reset --hard <commit-before-phase3>

# 或创建临时分支进行调试
git checkout -b debug-phase3
```

Phase 1 和 Phase 2 的代码已经在版本控制中，可以随时恢复。

---

## 检查清单

### 实施前

- [ ] 确认所有 Phase 1/2 分支已合并到 main
- [ ] 备份当前代码（已提交到 git）
- [ ] 在本地测试适配器基本功能

### 实施中

- [ ] 修改 UI 中的下载方法
- [ ] 修改 UI 中的搜索方法
- [ ] 修改 UI 中的队列显示
- [ ] 测试单个功能

### 实施后

- [ ] 运行所有功能测试
- [ ] 性能基准对比
- [ ] 用户反馈收集
- [ ] 生成最终报告

---

## 注意事项

### 可能的问题

1. **Signal 连接问题**: 确保信号参数类型与槽匹配
2. **线程切换**: Qt 信号自动处理线程切换，无需显式调用
3. **内存泄漏**: Service 使用单例，关闭应用时调用 `shutdown_adapters()`
4. **重复提交**: 同一任务不要多次 submit，使用 task_id 跟踪

### 性能考虑

- ThreadPoolExecutor 默认 3 个工作线程（与原有 DownloadThread 数量一致）
- 如果需要调整并发数，修改 `get_download_adapter()` 中的 `max_workers` 参数
- 搜索任务使用单独的 SearchService，不共享线程池

### 调试建议

- 在适配器 `_on_service_*` 方法中添加日志
- 监控 `_batch_tasks` 列表确保任务被正确追踪
- 检查 Service 是否正确发送事件（可能需要增加事件日志）

---

## 后续计划

完成 Phase 3 后，架构就达到稳定状态。后续可考虑：

1. **持久化**: 将 Task 对象保存到数据库（task 历史）
2. **重试机制**: 对失败的下载自动重试
3. **优先级队列**: 支持设置下载优先级
4. **带宽限制**: 限制并发数量以保护网络
5. **UI 增强**: 显示更详细的任务信息和统计

---

## 相关文档

- [Phase 1 - Registry + Protocol Guide](REFACTOR_PHASE1_REPORT.md)
- [Phase 2 - Service Layer Guide](REFACTOR_PHASE2_GUIDE.md)
- [Quick Start Guide](REFACTOR_QUICK_GUIDE.md)
