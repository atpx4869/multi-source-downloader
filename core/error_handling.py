# -*- coding: utf-8 -*-
"""
统一的错误处理和日志记录

提供标准化的错误类型和日志格式，便于调试和监控。
"""
import logging
from typing import Optional
from enum import Enum


class ErrorSeverity(str, Enum):
    """错误严重程度"""
    DEBUG = "DEBUG"      # 调试信息
    INFO = "INFO"        # 一般信息
    WARNING = "WARNING"  # 警告（可恢复）
    ERROR = "ERROR"      # 错误（不可恢复）
    CRITICAL = "CRITICAL"  # 严重错误（系统级）


class DownloadError(Exception):
    """下载错误基类"""

    def __init__(
        self,
        source: str,
        reason: str,
        retryable: bool = True,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[dict] = None
    ):
        """
        Args:
            source: 数据源名称（BY, GBW, ZBY）
            reason: 错误原因描述
            retryable: 是否可重试
            severity: 错误严重程度
            details: 额外的错误详情（如 HTTP 状态码、异常堆栈等）
        """
        self.source = source
        self.reason = reason
        self.retryable = retryable
        self.severity = severity
        self.details = details or {}
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """格式化错误消息"""
        retry_str = "可重试" if self.retryable else "不可重试"
        msg = f"[{self.source}] {self.reason} ({retry_str})"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            msg += f" - {details_str}"
        return msg

    def __str__(self):
        return self.format_message()


class SearchError(DownloadError):
    """搜索错误"""
    pass


class NetworkError(DownloadError):
    """网络错误"""

    def __init__(self, source: str, reason: str, **kwargs):
        kwargs.setdefault("retryable", True)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        super().__init__(source, reason, **kwargs)


class TimeoutError(NetworkError):
    """超时错误"""

    def __init__(self, source: str, operation: str, timeout: int, **kwargs):
        reason = f"{operation} 超时 ({timeout}秒)"
        kwargs.setdefault("details", {})["timeout"] = timeout
        super().__init__(source, reason, **kwargs)


class AuthenticationError(DownloadError):
    """认证错误"""

    def __init__(self, source: str, reason: str = "认证失败", **kwargs):
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("severity", ErrorSeverity.ERROR)
        super().__init__(source, reason, **kwargs)


class NotFoundError(DownloadError):
    """资源未找到错误"""

    def __init__(self, source: str, resource: str, **kwargs):
        reason = f"资源未找到: {resource}"
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        super().__init__(source, reason, **kwargs)


class ValidationError(DownloadError):
    """数据验证错误"""

    def __init__(self, source: str, reason: str, **kwargs):
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("severity", ErrorSeverity.ERROR)
        super().__init__(source, reason, **kwargs)


def format_log(
    level: str,
    source: str,
    operation: str,
    message: str,
    **kwargs
) -> str:
    """
    格式化日志消息

    Args:
        level: 日志级别（INFO, WARN, ERROR）
        source: 数据源名称
        operation: 操作类型（search, download, etc.）
        message: 日志消息
        **kwargs: 额外的上下文信息

    Returns:
        格式化的日志字符串
    """
    log_parts = [f"[{level}]", f"[{source}]", f"[{operation}]", message]

    if kwargs:
        context_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        log_parts.append(f"({context_str})")

    return " ".join(log_parts)


def log_error(error: Exception, source: str, operation: str) -> str:
    """
    记录错误日志

    Args:
        error: 异常对象
        source: 数据源名称
        operation: 操作类型

    Returns:
        格式化的错误日志
    """
    if isinstance(error, DownloadError):
        return format_log(
            error.severity.value,
            error.source,
            operation,
            error.reason,
            retryable=error.retryable,
            **error.details
        )
    else:
        # 未知错误类型
        return format_log(
            "ERROR",
            source,
            operation,
            f"{type(error).__name__}: {str(error)}",
            retryable=True
        )


def log_success(source: str, operation: str, message: str, **kwargs) -> str:
    """记录成功日志"""
    return format_log("INFO", source, operation, message, **kwargs)


def log_warning(source: str, operation: str, message: str, **kwargs) -> str:
    """记录警告日志"""
    return format_log("WARN", source, operation, message, **kwargs)


# 便捷函数：从 requests 异常创建 DownloadError
def from_requests_error(error: Exception, source: str, operation: str) -> DownloadError:
    """
    从 requests 异常创建 DownloadError

    Args:
        error: requests 异常
        source: 数据源名称
        operation: 操作类型

    Returns:
        DownloadError 实例
    """
    import requests

    if isinstance(error, requests.exceptions.Timeout):
        return TimeoutError(source, operation, timeout=0)

    elif isinstance(error, requests.exceptions.ConnectionError):
        return NetworkError(source, "连接失败", details={"error": str(error)})

    elif isinstance(error, requests.exceptions.HTTPError):
        status_code = error.response.status_code if error.response else 0
        retryable = status_code >= 500  # 5xx 错误可重试

        return DownloadError(
            source,
            f"HTTP 错误: {status_code}",
            retryable=retryable,
            details={"status_code": status_code}
        )

    else:
        return DownloadError(
            source,
            f"未知错误: {type(error).__name__}",
            retryable=True,
            details={"error": str(error)}
        )
