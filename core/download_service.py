# -*- coding: utf-8 -*-
"""
Download Service - 统一的下载任务管理

职责：
1. 接收下载请求，创建任务
2. 维护任务队列和状态
3. 分派任务给工作线程
4. 发射事件通知 UI 层
5. 支持任务取消和重试
"""

from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Callable
from datetime import datetime
import uuid
import logging

from sources import registry, DownloadResult
from core.models import Standard
from .service_base import BaseService, TaskStatus, TaskEvent

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """下载任务数据结构
    
    Attributes:
        id: 任务 ID（UUID）
        standard: 标准对象
        output_dir: 输出目录
        status: 任务状态
        priority: 优先级（0=最高）
        created_at: 创建时间
        started_at: 开始时间（可选）
        completed_at: 完成时间（可选）
        result: 下载结果（完成时）
        error: 错误信息（失败时）
        logs: 过程日志
    """
    standard: Standard
    output_dir: Path
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = field(default=TaskStatus.PENDING)
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[DownloadResult] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """验证任务数据"""
        if not isinstance(self.output_dir, Path):
            self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)


class DownloadService(BaseService):
    """下载服务
    
    使用示例：
    
    ```python
    service = DownloadService(max_workers=3)
    service.subscribe("completed", lambda evt: print(f"Download OK: {evt.result}"))
    service.subscribe("failed", lambda evt: print(f"Download Failed: {evt.error}"))
    
    task = service.submit(
        standard=std,
        output_dir=Path("downloads")
    )
    print(f"Task ID: {task.id}")
    
    # 查询状态
    status = service.get_status(task.id)
    print(f"Status: {status.status}")
    
    # 取消任务
    service.cancel(task.id)
    
    service.stop()
    ```
    """
    
    def __init__(self, max_workers: int = 3):
        super().__init__()
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, DownloadTask] = {}  # {task_id: DownloadTask}
        self._futures: Dict[str, Future] = {}      # {task_id: Future}
        self._lock = None  # 如果需要线程锁
    
    def start(self):
        """启动服务"""
        super().start()
        logger.info(f"DownloadService started with {self.max_workers} workers")
    
    def stop(self):
        """停止服务（等待所有任务完成）"""
        # 取消所有待执行任务
        for task_id in list(self._futures.keys()):
            self._futures[task_id].cancel()
        
        # 等待所有任务完成
        self._executor.shutdown(wait=True)
        super().stop()
        logger.info("DownloadService stopped")
    
    def submit(self, standard: Standard, output_dir: Path, priority: int = 0) -> DownloadTask:
        """提交下载任务
        
        Args:
            standard: 标准对象
            output_dir: 输出目录
            priority: 优先级（0=最高）
            
        Returns:
            DownloadTask 对象
        """
        task = DownloadTask(standard=standard, output_dir=output_dir, priority=priority)
        self._tasks[task.id] = task
        
        # 提交给线程池
        future = self._executor.submit(self._download_worker, task)
        self._futures[task.id] = future
        
        # 发射 submitted 事件（可选）
        self.emit(TaskEvent(
            task_id=task.id,
            event_type="submitted",
            status=TaskStatus.PENDING,
            message=f"下载任务已提交: {standard.display_label()}"
        ))
        
        logger.info(f"Task {task.id} submitted: {standard.std_no}")
        return task
    
    def get_status(self, task_id: str) -> Optional[DownloadTask]:
        """查询任务状态
        
        Args:
            task_id: 任务 ID
            
        Returns:
            DownloadTask 对象，或 None 如果不存在
        """
        return self._tasks.get(task_id)
    
    def cancel(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            True 如果成功取消，False 如果已在运行或已完成
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        # 如果任务已完成，无法取消
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        # 尝试取消 Future
        future = self._futures.get(task_id)
        if future and future.cancel():
            task.status = TaskStatus.CANCELLED
            self.emit(TaskEvent(
                task_id=task_id,
                event_type="cancelled",
                status=TaskStatus.CANCELLED,
                message="下载已取消"
            ))
            logger.info(f"Task {task_id} cancelled")
            return True
        
        return False
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务
        
        Returns:
            DownloadTask 列表
        """
        return list(self._tasks.values())
    
    def get_pending_tasks(self) -> List[DownloadTask]:
        """获取待执行任务"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
    
    def get_running_tasks(self) -> List[DownloadTask]:
        """获取运行中的任务"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]
    
    def get_completed_tasks(self) -> List[DownloadTask]:
        """获取已完成的任务"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]
    
    def get_failed_tasks(self) -> List[DownloadTask]:
        """获取失败的任务"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.FAILED]
    
    def clear_history(self, keep_days: int = 7):
        """清理历史任务记录
        
        Args:
            keep_days: 保留最近 N 天的任务记录
        """
        # 实现可选，暂时不做
        pass
    
    # ============ 私有方法 ============
    
    def _download_worker(self, task: DownloadTask):
        """后台工作线程函数
        
        Args:
            task: 下载任务
        """
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            # 发射 started 事件
            self.emit(TaskEvent(
                task_id=task.id,
                event_type="progress",
                status=TaskStatus.RUNNING,
                message=f"正在下载: {task.standard.display_label()}",
                progress=0
            ))
            
            logger.info(f"Task {task.id} started")
            
            # 按优先级顺序尝试下载
            sources = registry.identify(keyword=task.standard.std_no)
            
            for source_cls in sources:
                try:
                    source = source_cls()
                    result = source.download(task.standard, task.output_dir)
                    
                    if result.success:
                        task.result = result
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = datetime.now()
                        task.logs = result.logs
                        
                        # 发射 completed 事件
                        self.emit(TaskEvent(
                            task_id=task.id,
                            event_type="completed",
                            status=TaskStatus.COMPLETED,
                            message=f"下载完成: {result.file_path}",
                            result=result,
                            progress=100
                        ))
                        
                        logger.info(f"Task {task.id} completed successfully")
                        return
                    else:
                        task.logs.extend(result.logs)
                
                except Exception as e:
                    task.logs.append(f"Source {source_cls.source_name} error: {str(e)}")
                    logger.warning(f"Source {source_cls.source_name} failed: {e}")
            
            # 所有源都失败了
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = "All sources failed"
            
            # 发射 failed 事件
            self.emit(TaskEvent(
                task_id=task.id,
                event_type="failed",
                status=TaskStatus.FAILED,
                message=f"下载失败: 所有源都不可用",
                error=task.error,
                progress=0
            ))
            
            logger.error(f"Task {task.id} failed")
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            
            self.emit(TaskEvent(
                task_id=task.id,
                event_type="failed",
                status=TaskStatus.FAILED,
                message=f"下载异常: {str(e)}",
                error=str(e)
            ))
            
            logger.exception(f"Task {task.id} exception: {e}")
