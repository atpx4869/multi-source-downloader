# -*- coding: utf-8 -*-
"""
性能监控工具模块
"""
import time
import logging
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器 - 记录操作耗时"""

    def __init__(self):
        self.stats: Dict[str, Dict[str, Any]] = {}
        self._enabled = True

    def enable(self):
        """启用性能监控"""
        self._enabled = True

    def disable(self):
        """禁用性能监控"""
        self._enabled = False

    @contextmanager
    def measure(self, operation: str, source: str = ""):
        """
        测量操作耗时的上下文管理器

        用法：
            with monitor.measure("search", "GBW"):
                # 执行搜索操作
                pass
        """
        if not self._enabled:
            yield
            return

        start_time = time.time()
        error = None

        try:
            yield
        except Exception as e:
            error = e
            raise
        finally:
            elapsed = time.time() - start_time
            self._record(operation, source, elapsed, error is None)

    def _record(self, operation: str, source: str, elapsed: float, success: bool):
        """记录性能数据"""
        key = f"{source}:{operation}" if source else operation

        if key not in self.stats:
            self.stats[key] = {
                "count": 0,
                "total_time": 0.0,
                "min_time": float('inf'),
                "max_time": 0.0,
                "success_count": 0,
                "failure_count": 0
            }

        stats = self.stats[key]
        stats["count"] += 1
        stats["total_time"] += elapsed
        stats["min_time"] = min(stats["min_time"], elapsed)
        stats["max_time"] = max(stats["max_time"], elapsed)

        if success:
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1

        # 记录慢操作（超过 5 秒）
        if elapsed > 5.0:
            logger.warning(f"慢操作: {key} 耗时 {elapsed:.2f}s")

    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        获取性能统计

        Args:
            operation: 操作名称，如果为 None 则返回所有统计

        Returns:
            性能统计字典
        """
        if operation:
            return self.stats.get(operation, {})

        # 返回汇总统计
        result = {}
        for key, stats in self.stats.items():
            avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
            success_rate = stats["success_count"] / stats["count"] * 100 if stats["count"] > 0 else 0

            result[key] = {
                "count": stats["count"],
                "avg_time": round(avg_time, 3),
                "min_time": round(stats["min_time"], 3),
                "max_time": round(stats["max_time"], 3),
                "success_rate": round(success_rate, 1),
                "total_time": round(stats["total_time"], 2)
            }

        return result

    def reset(self):
        """重置所有统计数据"""
        self.stats.clear()

    def print_stats(self):
        """打印性能统计（用于调试）"""
        stats = self.get_stats()
        if not stats:
            print("无性能统计数据")
            return

        print("\n" + "=" * 80)
        print("性能统计报告")
        print("=" * 80)

        for key, data in sorted(stats.items()):
            print(f"\n{key}:")
            print(f"  调用次数: {data['count']}")
            print(f"  平均耗时: {data['avg_time']}s")
            print(f"  最小耗时: {data['min_time']}s")
            print(f"  最大耗时: {data['max_time']}s")
            print(f"  成功率: {data['success_rate']}%")
            print(f"  总耗时: {data['total_time']}s")

        print("=" * 80 + "\n")


# 全局性能监控器实例
_global_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    return _global_monitor


def measure_time(operation: str, source: str = ""):
    """
    装饰器：测量函数执行时间

    用法：
        @measure_time("search", "GBW")
        def search_gbw(keyword):
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with _global_monitor.measure(operation, source):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class ConnectionPoolManager:
    """连接池管理器 - 优化 HTTP 连接复用"""

    def __init__(self, pool_connections: int = 10, pool_maxsize: int = 20):
        """
        初始化连接池管理器

        Args:
            pool_connections: 连接池数量
            pool_maxsize: 每个连接池的最大连接数
        """
        self.pool_connections = pool_connections
        self.pool_maxsize = pool_maxsize

    def create_session(self,
                      timeout: Optional[int] = None,
                      max_retries: int = 3,
                      backoff_factor: float = 0.3) -> 'requests.Session':
        """
        创建优化的 requests.Session

        Args:
            timeout: 默认超时时间
            max_retries: 最大重试次数
            backoff_factor: 退避因子

        Returns:
            配置好的 Session 对象
        """
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )

        # 配置连接池
        adapter = HTTPAdapter(
            pool_connections=self.pool_connections,
            pool_maxsize=self.pool_maxsize,
            max_retries=retry_strategy
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 禁用系统代理
        session.trust_env = False
        session.proxies = {"http": None, "https": None}

        # 设置默认超时
        if timeout:
            # 为 session 添加默认超时
            original_request = session.request

            def request_with_timeout(*args, **kwargs):
                if 'timeout' not in kwargs:
                    kwargs['timeout'] = timeout
                return original_request(*args, **kwargs)

            session.request = request_with_timeout

        return session


# 全局连接池管理器实例
_global_pool_manager = ConnectionPoolManager()


def get_connection_pool_manager() -> ConnectionPoolManager:
    """获取全局连接池管理器实例"""
    return _global_pool_manager
