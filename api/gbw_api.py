# -*- coding: utf-8 -*-
"""
GBW Source API - GB/T 网 API 包装
"""
import time
from typing import Optional, Callable
from api.base import BaseSourceAPI
from api.models import (
    SourceType, StandardInfo, SearchResponse, 
    DownloadResponse, DownloadStatus, SourceHealth
)


class GBWSourceAPI(BaseSourceAPI):
    """GBW 源 API"""
    
    source_type = SourceType.GBW
    
    def __init__(self):
        """初始化 GBW API"""
        try:
            from sources.gbw import GBWSource
            self.source = GBWSource()
            self.init_error = None
        except Exception as e:
            self.source = None
            self.init_error = str(e)
    
    def search(self, query: str, limit: int = 100) -> SearchResponse:
        """搜索标准"""
        start_time = time.time()
        response = SearchResponse(
            source=SourceType.GBW,
            query=query,
            count=0,
            elapsed_time=0.0
        )
        
        try:
            if not self.source:
                response.error = f"GBW 源未初始化: {self.init_error}"
                return response
            
            # 调用源的搜索方法
            standards = self.source.search(query)
            
            # 转换为统一格式
            for std in standards[:limit]:
                info = StandardInfo(
                    std_no=std.std_no,
                    name=std.name,
                    source=SourceType.GBW,
                    has_pdf=std.has_pdf,
                    publish_date=std.publish,
                    implement_date=std.implement,
                    status=std.status,
                    source_meta=std.source_meta if isinstance(std.source_meta, dict) else {}
                )
                response.standards.append(info)
            
            response.count = len(response.standards)
            response.elapsed_time = time.time() - start_time
            
        except Exception as e:
            response.error = str(e)
            response.elapsed_time = time.time() - start_time
        
        return response
    
    def download(
        self,
        std_no: str,
        output_dir: str = "downloads",
        progress_callback: Optional[Callable] = None
    ) -> DownloadResponse:
        """下载标准"""
        start_time = time.time()
        response = DownloadResponse(
            source=SourceType.GBW,
            std_no=std_no,
            status=DownloadStatus.IN_PROGRESS,
            elapsed_time=0.0
        )
        
        try:
            if not self.source:
                response.status = DownloadStatus.ERROR
                response.error = f"GBW 源未初始化: {self.init_error}"
                return response
            
            # 定义日志回调
            logs = []
            def emit(msg: str):
                logs.append(msg)
                if progress_callback:
                    progress_callback(msg)
            
            # 调用源的下载方法
            filepath, download_logs = self.source.download(std_no, output_dir, emit)
            
            if filepath:
                from pathlib import Path
                p = Path(filepath)
                response.status = DownloadStatus.SUCCESS
                response.filepath = str(filepath)
                response.filename = p.name
                response.file_size = p.stat().st_size if p.exists() else 0
                response.logs = logs + download_logs
            else:
                response.status = DownloadStatus.FAILED
                response.error = "下载失败"
                response.logs = logs + download_logs
        
        except Exception as e:
            response.status = DownloadStatus.ERROR
            response.error = str(e)
        
        response.elapsed_time = time.time() - start_time
        return response
    
    def check_health(self) -> SourceHealth:
        """检查源健康状态"""
        health = SourceHealth(
            source=SourceType.GBW,
            available=False,
            response_time=0.0
        )
        
        start_time = time.time()
        try:
            if not self.source:
                health.error = f"GBW 源未初始化: {self.init_error}"
                return health
            
            # 尝试简单的搜索来检查连通性
            result = self.source.search("GB")
            health.available = True
            health.response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            health.last_check = time.time()
            
        except Exception as e:
            health.error = str(e)
            health.response_time = (time.time() - start_time) * 1000
            health.last_check = time.time()
        
        return health
