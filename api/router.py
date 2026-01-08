# -*- coding: utf-8 -*-
"""
API Router - API 路由和编排
"""
from typing import Dict, List, Optional, Callable
from api.models import (
    SourceType, StandardInfo, SearchResponse, 
    DownloadResponse, DownloadStatus, HealthResponse, SourceHealth
)
from api.base import BaseSourceAPI
from api.by_api import BYSourceAPI
from api.zby_api import ZBYSourceAPI
from api.gbw_api import GBWSourceAPI


# 优先级：优先使用可用性更好的源
PRIORITY_ORDER = [SourceType.GBW, SourceType.BY, SourceType.ZBY]


class APIRouter:
    """API 路由器 - 管理和编排多个源"""
    
    def __init__(self, output_dir: str = "downloads", enable_sources: Optional[List[str]] = None):
        """
        初始化 API 路由器
        
        Args:
            output_dir: 下载输出目录
            enable_sources: 启用的源列表 (默认全部)
        """
        self.output_dir = output_dir
        self.apis: Dict[SourceType, BaseSourceAPI] = {}
        
        # 初始化各源的 API
        apis_to_init = [
            (SourceType.BY, BYSourceAPI()),
            (SourceType.ZBY, ZBYSourceAPI(output_dir)),
            (SourceType.GBW, GBWSourceAPI()),
        ]
        
        for source_type, api in apis_to_init:
            if enable_sources is None or source_type.value in enable_sources:
                self.apis[source_type] = api
    
    def get_api(self, source: SourceType) -> Optional[BaseSourceAPI]:
        """获取指定源的 API"""
        return self.apis.get(source)
    
    def get_enabled_sources(self) -> List[SourceType]:
        """获取已启用的源"""
        return sorted(self.apis.keys(), key=lambda s: PRIORITY_ORDER.index(s))
    
    def search_single(
        self, 
        source: SourceType, 
        query: str, 
        limit: int = 100
    ) -> SearchResponse:
        """
        在单个源中搜索
        
        Args:
            source: 源类型
            query: 搜索词
            limit: 最多返回结果数
            
        Returns:
            SearchResponse: 搜索响应
        """
        api = self.get_api(source)
        if not api:
            response = SearchResponse(source=source, query=query, count=0)
            response.error = f"源 {source.value} 未启用"
            return response
        
        return api.search(query, limit)
    
    def search_all(
        self, 
        query: str, 
        limit: int = 100
    ) -> Dict[SourceType, SearchResponse]:
        """
        在所有源中搜索
        
        Args:
            query: 搜索词
            limit: 每个源最多返回结果数
            
        Returns:
            Dict[SourceType, SearchResponse]: 各源的搜索结果
        """
        results = {}
        for source in self.get_enabled_sources():
            api = self.get_api(source)
            if api:
                results[source] = api.search(query, limit)
        
        return results
    
    def download(
        self,
        source: SourceType,
        std_no: str,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> DownloadResponse:
        """
        从指定源下载标准
        
        Args:
            source: 源类型
            std_no: 标准编号
            output_dir: 输出目录（默认使用初始化时的目录）
            progress_callback: 进度回调函数
            
        Returns:
            DownloadResponse: 下载响应
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        api = self.get_api(source)
        if not api:
            response = DownloadResponse(
                source=source,
                std_no=std_no,
                status=DownloadStatus.ERROR
            )
            response.error = f"源 {source.value} 未启用"
            return response
        
        return api.download(std_no, output_dir, progress_callback)
    
    def download_first_available(
        self,
        std_no: str,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> DownloadResponse:
        """
        从第一个可用的源下载标准
        
        Args:
            std_no: 标准编号
            output_dir: 输出目录
            progress_callback: 进度回调函数
            
        Returns:
            DownloadResponse: 下载响应
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        # 按优先级尝试各源
        for source in self.get_enabled_sources():
            api = self.get_api(source)
            if not api:
                continue
            
            response = api.download(std_no, output_dir, progress_callback)
            if response.status == DownloadStatus.SUCCESS:
                return response
        
        # 所有源都失败
        response = DownloadResponse(
            source=SourceType.BY,  # 默认值
            std_no=std_no,
            status=DownloadStatus.NOT_FOUND
        )
        response.error = "未找到可用的源或下载失败"
        return response
    
    def check_health(self) -> HealthResponse:
        """
        检查所有源的健康状态
        
        Returns:
            HealthResponse: 健康检查响应
        """
        import time
        
        health_response = HealthResponse()
        health_response.timestamp = time.time()
        
        for source in self.get_enabled_sources():
            api = self.get_api(source)
            if api:
                health = api.check_health()
                health_response.sources.append(health)
        
        health_response.all_healthy = all(
            h.available for h in health_response.sources
        )
        
        return health_response
    
    def __repr__(self):
        sources = [s.value for s in self.get_enabled_sources()]
        return f"APIRouter({', '.join(sources)})"
