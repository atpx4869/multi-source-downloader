# -*- coding: utf-8 -*-
"""
ZBY Source API - 正规宝 API 包装
"""
import time
import concurrent.futures
from typing import Optional, Callable
from api.base import BaseSourceAPI
from api.models import (
    SourceType, StandardInfo, SearchResponse, 
    DownloadResponse, DownloadStatus, SourceHealth
)


class ZBYSourceAPI(BaseSourceAPI):
    """ZBY 源 API"""
    
    source_type = SourceType.ZBY
    
    def __init__(self, output_dir: str = "downloads"):
        """初始化 ZBY API"""
        try:
            from sources.zby import ZBYSource
            self.source = ZBYSource(output_dir)
            self.init_error = None
        except Exception as e:
            self.source = None
            self.init_error = str(e)
    
    def search(self, query: str, limit: int = 100) -> SearchResponse:
        """搜索标准"""
        start_time = time.time()
        response = SearchResponse(
            source=SourceType.ZBY,
            query=query,
            count=0,
            elapsed_time=0.0
        )
        
        if not self.source:
            response.error = f"ZBY 源未初始化: {self.init_error}"
            return response

        def _do_search():
            return self.source.search(query)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                standards = executor.submit(_do_search).result(timeout=8)
            for std in standards[:limit]:
                source_meta = std.source_meta if isinstance(std.source_meta, dict) else {}
                info = StandardInfo(
                    std_no=std.std_no,
                    name=std.name,
                    source=SourceType.ZBY,
                    has_pdf=std.has_pdf,
                    publish_date=std.publish,
                    implement_date=std.implement,
                    status=std.status,
                    replace_std=std.replace_std,
                    source_meta=source_meta
                )
                response.standards.append(info)
            response.count = len(response.standards)
        except concurrent.futures.TimeoutError:
            response.error = "ZBY 搜索超时(8s)"
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
            source=SourceType.ZBY,
            std_no=std_no,
            status=DownloadStatus.IN_PROGRESS,
            elapsed_time=0.0
        )
        
        try:
            if not self.source:
                response.status = DownloadStatus.ERROR
                response.error = f"ZBY 源未初始化: {self.init_error}"
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
            source=SourceType.ZBY,
            available=False,
            response_time=0.0
        )
        
        start_time = time.time()
        try:
            if not self.source:
                health.error = f"ZBY 源未初始化: {self.init_error}"
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
