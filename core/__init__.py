# -*- coding: utf-8 -*-
"""
Core 模块 - 数据模型、API 配置、聚合下载器、服务层
"""
from core.models import Standard, natural_key
from core.api_config import get_api_config, APIMode
from core.api_client import get_api_client
from core.aggregated_downloader import AggregatedDownloader
from core.service_base import BaseService, IService, IEventEmitter, TaskStatus, TaskEvent
from core.download_service import DownloadService, DownloadTask
from core.search_service import SearchService, SearchTask

__all__ = [
    'Standard',
    'natural_key',
    'get_api_config',
    'APIMode',
    'get_api_client',
    'AggregatedDownloader',
    # Service layer
    'BaseService',
    'IService',
    'IEventEmitter',
    'TaskStatus',
    'TaskEvent',
    'DownloadService',
    'DownloadTask',
    'SearchService',
    'SearchTask',
]
