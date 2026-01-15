# -*- coding: utf-8 -*-
"""
Service Layer - 业务服务接口定义

服务层位于 UI 和数据源之间，负责：
1. 任务管理（创建、查询、取消）
2. 生命周期管理（状态转移）
3. 事件分发（progress, completed, failed）
4. 线程安全的并发操作
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"          # 等待中
    RUNNING = "running"          # 运行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消


@dataclass
class TaskEvent:
    """任务事件（供监听者订阅）
    
    Attributes:
        task_id: 任务 ID
        event_type: 事件类型（progress, completed, failed, cancelled）
        status: 任务当前状态
        message: 事件消息
        progress: 进度百分比（0-100，可选）
        error: 错误信息（失败时）
        result: 结果数据（完成时）
    """
    task_id: str
    event_type: str  # progress, completed, failed, cancelled
    status: TaskStatus
    message: str
    progress: Optional[int] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)


class IService(ABC):
    """服务接口
    
    所有服务都应继承此接口，实现统一的生命周期管理。
    """
    
    @abstractmethod
    def start(self):
        """启动服务（如果需要后台工作线程）"""
        pass
    
    @abstractmethod
    def stop(self):
        """停止服务"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        pass


class IEventEmitter(ABC):
    """事件发射器接口
    
    允许外部监听者订阅服务事件。
    """
    
    @abstractmethod
    def subscribe(self, event_type: str, callback: Callable[[TaskEvent], None]):
        """订阅事件
        
        Args:
            event_type: 事件类型（"progress", "completed", "failed", "cancelled"）
            callback: 回调函数
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: str, callback: Callable[[TaskEvent], None]):
        """取消订阅"""
        pass
    
    @abstractmethod
    def emit(self, event: TaskEvent):
        """发射事件"""
        pass


class BaseService(IService, IEventEmitter):
    """基础服务类
    
    提供通用的事件管理和生命周期管理。
    """
    
    def __init__(self):
        self._running = False
        self._listeners = {}  # {event_type: [callback1, callback2, ...]}
    
    def start(self):
        """启动服务"""
        self._running = True
    
    def stop(self):
        """停止服务"""
        self._running = False
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self._running
    
    def subscribe(self, event_type: str, callback: Callable[[TaskEvent], None]):
        """订阅事件"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable[[TaskEvent], None]):
        """取消订阅"""
        if event_type in self._listeners and callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)
    
    def emit(self, event: TaskEvent):
        """发射事件给所有订阅者"""
        if event.event_type in self._listeners:
            for callback in self._listeners[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    # 避免一个监听者的异常影响其他监听者
                    print(f"Event callback error: {e}")
