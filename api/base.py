# -*- coding: utf-8 -*-
"""
Base API Interface - 基础 API 接口定义
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from api.models import (
    SourceType, StandardInfo, SearchResponse, 
    DownloadResponse, DownloadStatus, SourceHealth
)


class BaseSourceAPI(ABC):
    """基础源 API 接口"""
    
    source_type: SourceType
    
    @abstractmethod
    def search(self, query: str, limit: int = 100) -> SearchResponse:
        """
        搜索标准
        
        Args:
            query: 搜索词（标准编号或名称）
            limit: 最多返回结果数
            
        Returns:
            SearchResponse: 搜索响应
        """
        pass
    
    @abstractmethod
    def download(
        self, 
        std_no: str, 
        output_dir: str = "downloads",
        progress_callback: Optional[Callable] = None
    ) -> DownloadResponse:
        """
        下载标准 PDF
        
        Args:
            std_no: 标准编号
            output_dir: 输出目录
            progress_callback: 进度回调函数
            
        Returns:
            DownloadResponse: 下载响应
        """
        pass
    
    @abstractmethod
    def check_health(self) -> SourceHealth:
        """
        检查源的健康状态
        
        Returns:
            SourceHealth: 健康状态信息
        """
        pass
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.source_type.value})"
