# -*- coding: utf-8 -*-
"""
API Package - 统一 API 接口

这个包提供了三个标准源（BY、ZBY、GBW）的统一 API 接口，
方便后续为桌面应用或 Web 服务集成。

用法：
    from api import APIRouter
    
    router = APIRouter()
    
    # 搜索
    results = router.search_all("GB/T 3324")
    
    # 下载
    response = router.download(SourceType.ZBY, "GB/T 3324-2024")
    
    # 健康检查
    health = router.check_health()
"""

from api.models import (
    SourceType, DownloadStatus,
    StandardInfo, SearchResponse,
    DownloadResponse, DownloadProgress,
    SourceHealth, HealthResponse
)
from api.base import BaseSourceAPI
from api.by_api import BYSourceAPI
from api.zby_api import ZBYSourceAPI
from api.gbw_api import GBWSourceAPI
from api.router import APIRouter

__all__ = [
    # 模型
    'SourceType',
    'DownloadStatus',
    'StandardInfo',
    'SearchResponse',
    'DownloadResponse',
    'DownloadProgress',
    'SourceHealth',
    'HealthResponse',
    
    # 接口和实现
    'BaseSourceAPI',
    'BYSourceAPI',
    'ZBYSourceAPI',
    'GBWSourceAPI',
    'APIRouter',
]

__version__ = "1.0.0"
