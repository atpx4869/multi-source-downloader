# -*- coding: utf-8 -*-
"""
Search Service - 统一的搜索任务管理

职责：
1. 接收搜索请求
2. 并行查询多个数据源
3. 流式返回结果（边搜边返回）
4. 发射事件通知 UI 层
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Iterator, Callable
from datetime import datetime
import uuid
import logging

from sources import registry
from core.models import Standard
from .service_base import BaseService, TaskStatus, TaskEvent

logger = logging.getLogger(__name__)


@dataclass
class SearchTask:
    """搜索任务数据结构
    
    Attributes:
        id: 任务 ID
        keyword: 搜索关键词
        status: 任务状态
        created_at: 创建时间
        completed_at: 完成时间（可选）
        results: 搜索结果列表
        error: 错误信息（失败时）
    """
    keyword: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = field(default=TaskStatus.PENDING)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    results: List[Standard] = field(default_factory=list)
    error: Optional[str] = None


class SearchService(BaseService):
    """搜索服务
    
    使用示例：
    
    ```python
    service = SearchService(max_workers=3)
    service.subscribe("result", lambda evt: print(f"Found: {evt.message}"))
    service.subscribe("completed", lambda evt: print(f"Total: {evt.result}"))
    
    task = service.submit(keyword="GB 6675")
    
    # 实时获取结果
    for result in service.stream_results(task.id):
        print(f"{result.std_no}: {result.name}")
    
    service.stop()
    ```
    """
    
    def __init__(self, max_workers: int = 3):
        super().__init__()
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, SearchTask] = {}
    
    def start(self):
        """启动服务"""
        super().start()
        logger.info(f"SearchService started with {self.max_workers} workers")
    
    def stop(self):
        """停止服务"""
        self._executor.shutdown(wait=True)
        super().stop()
        logger.info("SearchService stopped")
    
    def submit(self, keyword: str) -> SearchTask:
        """提交搜索任务
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            SearchTask 对象
        """
        task = SearchTask(keyword=keyword)
        self._tasks[task.id] = task
        
        # 后台执行搜索
        self._executor.submit(self._search_worker, task)
        
        self.emit(TaskEvent(
            task_id=task.id,
            event_type="submitted",
            status=TaskStatus.PENDING,
            message=f"搜索任务已提交: {keyword}"
        ))
        
        logger.info(f"Search task {task.id} submitted: {keyword}")
        return task
    
    def get_status(self, task_id: str) -> Optional[SearchTask]:
        """查询任务状态"""
        return self._tasks.get(task_id)
    
    def stream_results(self, task_id: str) -> Iterator[Standard]:
        """流式获取搜索结果（阻塞直到任务完成）
        
        Args:
            task_id: 任务 ID
            
        Yields:
            Standard 对象
        """
        task = self._tasks.get(task_id)
        if not task:
            return
        
        # 等待任务完成
        while task.status == TaskStatus.PENDING or task.status == TaskStatus.RUNNING:
            import time
            time.sleep(0.1)
        
        # 返回结果
        for result in task.results:
            yield result
    
    def get_all_tasks(self) -> List[SearchTask]:
        """获取所有搜索任务"""
        return list(self._tasks.values())
    
    # ============ 私有方法 ============
    
    def _search_worker(self, task: SearchTask):
        """后台搜索工作线程
        
        Args:
            task: 搜索任务
        """
        try:
            task.status = TaskStatus.RUNNING
            
            self.emit(TaskEvent(
                task_id=task.id,
                event_type="progress",
                status=TaskStatus.RUNNING,
                message=f"正在搜索: {task.keyword}",
                progress=0
            ))
            
            logger.info(f"Search task {task.id} started for keyword: {task.keyword}")
            
            # 并行搜索所有数据源
            sources = registry.identify(keyword=task.keyword)
            futures = {}
            
            for source_cls in sources:
                future = self._executor.submit(self._search_one_source, source_cls, task.keyword)
                futures[future] = source_cls.source_name
            
            # 收集结果（边搜边返回）
            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    results = future.result(timeout=30)
                    task.results.extend(results)
                    
                    # 发射进度事件
                    self.emit(TaskEvent(
                        task_id=task.id,
                        event_type="progress",
                        status=TaskStatus.RUNNING,
                        message=f"{source_name}: 找到 {len(results)} 条结果",
                        progress=None
                    ))
                    
                    logger.info(f"Search {source_name}: {len(results)} results")
                
                except Exception as e:
                    logger.warning(f"Search source {source_name} failed: {e}")
            
            # 去重并排序
            self._deduplicate_results(task)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            self.emit(TaskEvent(
                task_id=task.id,
                event_type="completed",
                status=TaskStatus.COMPLETED,
                message=f"搜索完成: 共 {len(task.results)} 条结果",
                result=task.results,
                progress=100
            ))
            
            logger.info(f"Search task {task.id} completed with {len(task.results)} results")
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            
            self.emit(TaskEvent(
                task_id=task.id,
                event_type="failed",
                status=TaskStatus.FAILED,
                message=f"搜索失败: {str(e)}",
                error=str(e)
            ))
            
            logger.exception(f"Search task {task.id} exception: {e}")
    
    def _search_one_source(self, source_cls, keyword: str) -> List[Standard]:
        """搜索单个源
        
        Args:
            source_cls: 源类
            keyword: 搜索关键词
            
        Returns:
            Standard 列表
        """
        try:
            source = source_cls()
            return source.search(keyword)
        except Exception as e:
            logger.error(f"Error searching {source_cls.source_name}: {e}")
            return []
    
    def _deduplicate_results(self, task: SearchTask):
        """去重搜索结果
        
        按标准号去重，保留第一个结果
        """
        seen = {}  # {std_no: index}
        duplicates = []
        
        for idx, result in enumerate(task.results):
            key = result.std_no.upper().strip()
            if key in seen:
                duplicates.append(idx)
            else:
                seen[key] = idx
        
        # 移除重复项（从后向前，避免索引变化）
        for idx in sorted(duplicates, reverse=True):
            task.results.pop(idx)
