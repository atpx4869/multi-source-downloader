# -*- coding: utf-8 -*-
"""
下载队列管理模块
支持优先级队列、任务暂停/继续、自动重试、崩溃恢复
"""
import uuid
import time
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from core.database import get_database


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 运行中
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class DownloadTask:
    """下载任务数据模型"""
    task_id: str
    std_no: str
    std_name: str = ""
    status: str = TaskStatus.PENDING.value
    priority: int = 5  # 1-10，数字越大优先级越高
    source: str = ""
    retry_count: int = 0
    max_retries: int = 3
    error_msg: str = ""
    created_time: str = None
    started_time: str = None
    completed_time: str = None
    file_path: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DownloadTask':
        """从字典创建"""
        # 处理字段名不匹配：数据库使用 'id'，dataclass 使用 'task_id'
        data = dict(data)  # 创建副本避免修改原始数据
        
        # 如果有 'id' 字段，将其映射到 'task_id'
        if 'id' in data:
            if 'task_id' not in data:
                data['task_id'] = data['id']
            data.pop('id')  # 删除 'id' 字段，避免传递给 __init__
        
        return cls(**data)


class DownloadQueueManager:
    """下载队列管理器"""
    
    def __init__(self, max_workers: int = 3):
        self.db = get_database()
        self.max_workers = max_workers
        
        # 优先级队列（使用元组：(-priority, timestamp, task)）
        self._queue = queue.PriorityQueue()
        self._tasks: Dict[str, DownloadTask] = {}  # 内存中的任务字典
        self._workers: List[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()
        
        # 信号回调
        self.on_task_start: Optional[Callable[[DownloadTask], None]] = None
        self.on_task_complete: Optional[Callable[[DownloadTask], None]] = None
        self.on_task_fail: Optional[Callable[[DownloadTask], None]] = None
        self.on_progress: Optional[Callable[[str], None]] = None
        
        # 从数据库恢复未完成任务
        self._restore_tasks()
    
    def _restore_tasks(self):
        """从数据库恢复未完成的任务"""
        # 将运行中的任务重置为待处理
        running_tasks = self.db.get_tasks_by_status(TaskStatus.RUNNING.value)
        for task_data in running_tasks:
            self.db.update_task(task_data['task_id'], {
                'status': TaskStatus.PENDING.value,
                'started_time': None
            })
        
        # 加载所有待处理和暂停的任务到内存
        for status in [TaskStatus.PENDING.value, TaskStatus.PAUSED.value]:
            tasks = self.db.get_tasks_by_status(status)
            for task_data in tasks:
                task = DownloadTask.from_dict(task_data)
                self._tasks[task.task_id] = task
                
                # 只将待处理任务加入队列
                if task.status == TaskStatus.PENDING.value:
                    self._enqueue_task(task)
    
    def _enqueue_task(self, task: DownloadTask):
        """将任务加入优先级队列"""
        # 优先级越高，值越小（因为 PriorityQueue 是最小堆）
        priority_value = -task.priority
        timestamp = time.time()
        self._queue.put((priority_value, timestamp, task.task_id))
    
    def add_task(self, std_no: str, std_name: str = "", priority: int = 5,
                 source: str = "", max_retries: int = 3, metadata: Dict = None) -> str:
        """添加下载任务"""
        task = DownloadTask(
            task_id=str(uuid.uuid4()),
            std_no=std_no,
            std_name=std_name,
            priority=priority,
            source=source,
            max_retries=max_retries,
            metadata=metadata or {}
        )
        
        with self._lock:
            # 保存到数据库
            self.db.add_task(task.to_dict())
            
            # 保存到内存
            self._tasks[task.task_id] = task
            
            # 加入队列
            self._enqueue_task(task)
        
        return task.task_id
    
    def add_batch_tasks(self, items: List[Dict]) -> List[str]:
        """批量添加任务"""
        task_ids = []
        for item in items:
            task_id = self.add_task(
                std_no=item.get('std_no', ''),
                std_name=item.get('std_name', ''),
                priority=item.get('priority', 5),
                source=item.get('source', ''),
                max_retries=item.get('max_retries', 3),
                metadata=item.get('metadata', {})
            )
            task_ids.append(task_id)
        return task_ids
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        # 从数据库获取最新状态
        task_data_list = self.db.get_all_tasks()
        tasks = []
        for task_data in task_data_list:
            task = DownloadTask.from_dict(task_data)
            # 更新内存中的任务
            if task.task_id in self._tasks:
                self._tasks[task.task_id] = task
            tasks.append(task)
        return tasks
    
    def update_task_status(self, task_id: str, status: TaskStatus,
                          error_msg: str = "", file_path: str = ""):
        """更新任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            
            updates = {'status': status.value}
            
            if status == TaskStatus.RUNNING:
                updates['started_time'] = datetime.now().isoformat()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                updates['completed_time'] = datetime.now().isoformat()
            
            if error_msg:
                updates['error_msg'] = error_msg
            
            if file_path:
                updates['file_path'] = file_path
            
            # 更新内存
            for key, value in updates.items():
                setattr(task, key, value)
            
            # 更新数据库
            self.db.update_task(task_id, updates)
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            # 只能暂停待处理或运行中的任务
            if task.status not in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
                return False
            
            self.update_task_status(task_id, TaskStatus.PAUSED)
            return True
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            if task.status != TaskStatus.PAUSED.value:
                return False
            
            # 重置为待处理并重新入队
            task.status = TaskStatus.PENDING.value
            self.db.update_task(task_id, {'status': TaskStatus.PENDING.value})
            self._enqueue_task(task)
            return True
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            self.update_task_status(task_id, TaskStatus.CANCELLED)
            return True
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务（从数据库和内存中移除）"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
            self.db.delete_task(task_id)
            return True
    
    def retry_task(self, task_id: str) -> bool:
        """重试失败的任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            if task.status != TaskStatus.FAILED.value:
                return False
            
            # 重置状态
            task.status = TaskStatus.PENDING.value
            task.retry_count += 1
            task.error_msg = ""
            task.started_time = None
            task.completed_time = None
            
            self.db.update_task(task_id, {
                'status': TaskStatus.PENDING.value,
                'retry_count': task.retry_count,
                'error_msg': '',
                'started_time': None,
                'completed_time': None
            })
            
            self._enqueue_task(task)
            return True
    
    def retry_all_failed(self) -> int:
        """重试所有失败任务"""
        failed_tasks = self.db.get_tasks_by_status(TaskStatus.FAILED.value)
        count = 0
        for task_data in failed_tasks:
            if self.retry_task(task_data['task_id']):
                count += 1
        return count
    
    def clear_completed(self):
        """清空已完成任务"""
        with self._lock:
            completed = [tid for tid, t in self._tasks.items() 
                        if t.status == TaskStatus.COMPLETED.value]
            for task_id in completed:
                del self._tasks[task_id]
            self.db.clear_completed_tasks()
    
    def get_statistics(self) -> Dict[str, int]:
        """获取队列统计信息"""
        stats = self.db.get_task_statistics()
        stats['queue_size'] = self._queue.qsize()
        stats['active_workers'] = sum(1 for w in self._workers if w.is_alive())
        return stats
    
    def start(self, worker_func: Callable[[DownloadTask], tuple]):
        """启动队列处理
        
        Args:
            worker_func: 工作函数，接收 DownloadTask，返回 (success: bool, error_msg: str, file_path: str)
        """
        if self._running:
            return
        
        self._running = True
        
        def worker_thread():
            while self._running:
                try:
                    # 从队列获取任务（超时1秒）
                    try:
                        priority, timestamp, task_id = self._queue.get(timeout=1)
                    except queue.Empty:
                        continue
                    
                    with self._lock:
                        task = self._tasks.get(task_id)
                    
                    if not task:
                        self._queue.task_done()
                        continue
                    
                    # 检查任务状态（可能被暂停或取消）
                    if task.status != TaskStatus.PENDING.value:
                        self._queue.task_done()
                        continue
                    
                    # 更新为运行中
                    self.update_task_status(task_id, TaskStatus.RUNNING)
                    
                    if self.on_task_start:
                        self.on_task_start(task)
                    
                    # 执行下载
                    try:
                        success, error_msg, file_path = worker_func(task)
                        
                        if success:
                            self.update_task_status(task_id, TaskStatus.COMPLETED, file_path=file_path)
                            if self.on_task_complete:
                                self.on_task_complete(task)
                        else:
                            # 判断是否需要重试
                            if task.retry_count < task.max_retries:
                                # 重试：重新入队
                                task.retry_count += 1
                                task.status = TaskStatus.PENDING.value
                                self.db.update_task(task_id, {
                                    'status': TaskStatus.PENDING.value,
                                    'retry_count': task.retry_count,
                                    'error_msg': f"[重试 {task.retry_count}/{task.max_retries}] {error_msg}"
                                })
                                self._enqueue_task(task)
                            else:
                                # 达到最大重试次数，标记为失败
                                self.update_task_status(task_id, TaskStatus.FAILED, error_msg=error_msg)
                                if self.on_task_fail:
                                    self.on_task_fail(task)
                    
                    except Exception as e:
                        error = f"Worker 异常: {str(e)}"
                        self.update_task_status(task_id, TaskStatus.FAILED, error_msg=error)
                        if self.on_task_fail:
                            self.on_task_fail(task)
                    
                    self._queue.task_done()
                
                except Exception as e:
                    print(f"❌ Worker 线程异常: {e}")
        
        # 启动多个 worker 线程
        for i in range(self.max_workers):
            worker = threading.Thread(target=worker_thread, daemon=True, name=f"QueueWorker-{i+1}")
            worker.start()
            self._workers.append(worker)
    
    def stop(self, wait: bool = True):
        """停止队列处理"""
        self._running = False
        
        if wait:
            # 等待所有 worker 线程结束
            for worker in self._workers:
                if worker.is_alive():
                    worker.join(timeout=5)
        
        self._workers.clear()
    
    def is_running(self) -> bool:
        """队列是否正在运行"""
        return self._running


# 全局队列管理器实例
_queue_manager: Optional[DownloadQueueManager] = None


def get_queue_manager(max_workers: int = 3) -> DownloadQueueManager:
    """获取全局队列管理器实例"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = DownloadQueueManager(max_workers=max_workers)
    elif _queue_manager.max_workers != max_workers:
        # 如果worker数量不同，需要停止旧的并创建新的
        if _queue_manager.is_running():
            _queue_manager.stop(wait=False)
        _queue_manager = DownloadQueueManager(max_workers=max_workers)
    return _queue_manager
