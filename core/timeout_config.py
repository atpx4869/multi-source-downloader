# -*- coding: utf-8 -*-
"""
统一的超时配置

为所有数据源和操作类型定义合理的超时时间，避免搜索/下载卡死。
"""

# 数据源超时配置（秒）
TIMEOUT_CONFIG = {
    "BY": {
        "search": 5,       # 内网访问，应该很快
        "download": 5,     # 内网下载，快速
        "detail": 3,       # 详情页获取
    },
    "GBW": {
        "search": 10,      # 外网访问，可能较慢
        "download": 30,    # 外网下载 + OCR 处理需要时间
        "detail": 5,       # 详情页获取
        "pdf_check": 5,    # PDF 可用性检查
    },
    "ZBY": {
        "search": 10,      # 外网访问，可能较慢
        "download": 20,    # 外网下载
        "detail": 8,       # 详情页获取
        "api": 8,          # API 调用
    },
}

# 并行操作超时配置（秒）
PARALLEL_TIMEOUT = {
    "search_total": 15,      # 并行搜索总超时（应该 >= max(单源搜索超时)）
    "download_total": 60,    # 并行下载总超时（应该 >= max(单源下载超时)）
}

# 默认超时（秒）
DEFAULT_TIMEOUT = 10


def get_timeout(source: str, operation: str) -> int:
    """
    获取指定数据源和操作的超时时间

    Args:
        source: 数据源名称（BY, GBW, ZBY）
        operation: 操作类型（search, download, detail, etc.）

    Returns:
        超时时间（秒）
    """
    if source in TIMEOUT_CONFIG:
        return TIMEOUT_CONFIG[source].get(operation, DEFAULT_TIMEOUT)
    return DEFAULT_TIMEOUT


def get_parallel_timeout(operation: str) -> int:
    """
    获取并行操作的总超时时间

    Args:
        operation: 操作类型（search_total, download_total）

    Returns:
        超时时间（秒）
    """
    return PARALLEL_TIMEOUT.get(operation, DEFAULT_TIMEOUT * 2)


# 重试配置
RETRY_CONFIG = {
    "max_retries": 2,           # 最大重试次数
    "backoff_factor": 0.5,      # 指数退避因子（秒）
    "retry_on_timeout": True,   # 超时时是否重试
    "retry_on_5xx": True,       # 5xx 错误时是否重试
}


def should_retry(error: Exception, attempt: int) -> bool:
    """
    判断是否应该重试

    Args:
        error: 异常对象
        attempt: 当前尝试次数（从 0 开始）

    Returns:
        是否应该重试
    """
    if attempt >= RETRY_CONFIG["max_retries"]:
        return False

    # 检查是否是可重试的错误类型
    import requests

    if isinstance(error, requests.exceptions.Timeout):
        return RETRY_CONFIG["retry_on_timeout"]

    if isinstance(error, requests.exceptions.ConnectionError):
        return True

    if isinstance(error, requests.exceptions.HTTPError):
        if error.response and error.response.status_code >= 500:
            return RETRY_CONFIG["retry_on_5xx"]

    return False


def get_retry_delay(attempt: int) -> float:
    """
    获取重试延迟时间（指数退避）

    Args:
        attempt: 当前尝试次数（从 0 开始）

    Returns:
        延迟时间（秒）
    """
    return RETRY_CONFIG["backoff_factor"] * (2 ** attempt)
