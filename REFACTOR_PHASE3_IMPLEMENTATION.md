# Phase 3 实施步骤 - UI 集成详细指南

## 概述

在 `app/desktop_app_impl.py` 中集成新的 Service 层，使用 `UIDownloadAdapter` 和 `UISearchAdapter`。

## 第一步：修改导入（第 1-60 行）

在文件顶部添加新的导入：

```python
# 添加到现有导入之后
from app.ui_service_adapter import (
    get_download_adapter, 
    get_search_adapter,
    shutdown_adapters,
    UIDownloadAdapter,
    UISearchAdapter
)
```

## 第二步：修改类初始化（init 方法）

在 `MainWindow.__init__` 中添加：

```python
# 初始化服务适配器
self.download_adapter = get_download_adapter()
self.search_adapter = get_search_adapter()

# 连接下载适配器信号
self.download_adapter.download_started.connect(self._on_download_started)
self.download_adapter.download_progress.connect(self.on_download_progress)
self.download_adapter.download_completed.connect(self._on_download_completed)
self.download_adapter.download_failed.connect(self._on_download_failed)
self.download_adapter.all_downloads_finished.connect(self.on_download_finished)

# 连接搜索适配器信号
self.search_adapter.search_started.connect(self._on_search_started)
self.search_adapter.search_result.connect(self._on_search_result)
self.search_adapter.search_completed.connect(self._on_search_completed)
self.search_adapter.search_failed.connect(self._on_search_failed)
```

## 第三步：修改 on_download() 方法（第 4236 行）

**原逻辑保持不变**：
- 选择检查
- 日志记录
- 优先级配置
- 进度条显示
- 源选择验证

**只修改最后一部分**：

```python
# 删除这部分：
# self.download_thread = DownloadThread(...)
# self.download_thread.log.connect(...)
# self.download_thread.start()

# 替换为：
# 使用适配器提交下载
self.download_adapter.submit_downloads(
    standards=selected,  # 现有的 selected 列表
    output_dir=Path(output_dir),
    batch_callback=None  # 或定义一个回调处理批次完成
)

# 记录任务开始
self.append_log(f"🚀 已提交 {len(selected)} 个下载任务到后台")
```

## 第四步：添加新的信号槽方法

在下载相关方法后添加：

```python
def _on_download_started(self, task_id: str):
    """下载任务开始"""
    # 可选：记录任务 ID 供之后查询
    if not hasattr(self, '_active_task_ids'):
        self._active_task_ids = []
    self._active_task_ids.append(task_id)

def _on_download_completed(self, task_id: str, file_path: Path):
    """单个下载完成"""
    self.append_log(f"   ✅ {file_path.name}")

def _on_download_failed(self, task_id: str, error: str):
    """单个下载失败"""
    self.append_log(f"   ❌ {error}")
```

## 第五步：修改 on_download_progress() 方法

```python
def on_download_progress(self, task_id: str, current: int, total: int, message: str):
    """更新下载进度（来自适配器）"""
    # 获取批次状态
    if hasattr(self.download_adapter, 'get_batch_status'):
        status = self.download_adapter.get_batch_status()
        self.progress_bar.setMaximum(status['total'])
        self.progress_bar.setValue(status['completed'] + status.get('running', 0))
        self.status.showMessage(message)
```

## 第六步：清理程序退出（closeEvent 方法）

```python
def closeEvent(self, event):
    """程序关闭时清理资源"""
    try:
        # 停止所有下载
        if hasattr(self, 'download_adapter'):
            self.download_adapter.cancel_all_downloads()
            self.download_adapter.shutdown()
        
        # 停止所有搜索
        if hasattr(self, 'search_adapter'):
            self.search_adapter.shutdown()
    except Exception as e:
        print(f"关闭适配器时出错: {e}")
    
    # 调用父类的 closeEvent
    super().closeEvent(event)
```

## 第七步：可选 - 搜索相关修改（如有搜索功能）

如果有搜索功能，类似修改搜索方法：

```python
def on_enhanced_search(self):
    """启动搜索（使用新的 SearchService）"""
    keyword = self.search_input.text().strip()
    if not keyword:
        QtWidgets.QMessageBox.information(self, "提示", "请输入搜索关键词")
        return
    
    # 使用适配器
    task_id = self.search_adapter.submit_search(keyword)
    self.append_log(f"🔍 开始搜索: {keyword}")
```

---

## 回滚说明

如果新代码有问题，可以：

1. **临时回滚**：注释掉适配器相关代码，恢复 DownloadThread 的使用
2. **完全回滚**：
   ```bash
   git checkout main~1 -- app/desktop_app_impl.py
   ```
3. **调试**：在适配器中添加日志来追踪事件流

---

## 验证检查表

实施每一步后，验证：

- [ ] 导入正确（没有 ImportError）
- [ ] 初始化成功（程序能启动）
- [ ] 下载能提交（能看到"已提交"日志）
- [ ] 信号能接收（能看到进度日志）
- [ ] 下载能完成（最后看到汇总日志）
- [ ] 可以取消（点取消按钮，下载停止）
- [ ] 关闭应用无错（没有异常提示）

---

## 分步实施建议

1. **第一天**：只做第 1-2 步（导入和初始化），验证程序能启动
2. **第二天**：做第 3-4 步（修改 on_download），测试简单下载
3. **第三天**：做第 5-6 步（进度和清理），完整测试
4. **第四天**：测试异常情况（取消、重复下载等），如有问题调试

---

## 常见问题排查

**问题 1：ImportError: cannot import UIDownloadAdapter**
- 检查 `app/ui_service_adapter.py` 是否存在
- 检查导入路径是否正确

**问题 2：程序启动后无响应**
- 可能是 Service 初始化耗时
- 在 `get_download_adapter()` 中添加日志跟踪

**问题 3：信号无法接收到**
- 检查信号参数类型是否匹配
- 确保 `connect()` 在初始化时调用，而不是在方法内部

**问题 4：下载没有进度更新**
- Service 可能没有发送 progress 事件
- 检查 Service 的 `_on_service_progress` 方法

---

## 后续优化

完成基础集成后，可考虑：

1. **进度显示增强**：显示每个源的进度
2. **取消功能增强**：显示正在取消的消息
3. **队列管理 UI**：显示待处理队列
4. **性能监控**：显示内存和 CPU 使用
5. **错误恢复**：提供重试失败项的选项
