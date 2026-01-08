# -*- coding: utf-8 -*-
"""
API 客户端 - 支持本地和远程两种模式
"""
import requests
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import json

from api.router import APIRouter
from api.models import SearchResponse, DownloadResponse, SourceType, HealthResponse
from core.api_config import APIMode, get_api_config


class APIClient:
    """统一的 API 客户端 - 支持本地和远程两种模式"""
    
    def __init__(self, config=None):
        """
        初始化 API 客户端
        
        Args:
            config: APIConfig 实例，默认使用全局配置
        """
        self.config = config or get_api_config()
        
        # 本地模式：直接使用 APIRouter
        if self.config.is_local_mode():
            self.local_router = APIRouter(
                output_dir=self.config.local_output_dir,
                enable_sources=self.config.enable_sources
            )
            self.local_router = None  # 延迟初始化（避免重复创建浏览器进程）
        else:
            self.local_router = None
    
    def _get_local_router(self) -> APIRouter:
        """延迟初始化本地 Router（仅在需要时创建）"""
        if self.local_router is None:
            self.local_router = APIRouter(
                output_dir=self.config.local_output_dir,
                enable_sources=self.config.enable_sources
            )
        return self.local_router
    
    def search(self, query: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        搜索标准
        
        Args:
            query: 搜索词
            limit: 限制条数（默认使用配置）
            
        Returns:
            搜索结果字典 {source: results_list}
        """
        if limit is None:
            limit = self.config.search_limit
        
        if self.config.is_local_mode():
            router = self._get_local_router()
            result = router.search_all(query, limit=limit)
            
            # 将 SearchResponse 对象转换为字典
            output = {}
            for source_type, response in result.items():
                if response.items:
                    output[source_type.value] = [item.to_dict() for item in response.items]
                else:
                    output[source_type.value] = []
            return output
        else:
            return self._remote_search(query, limit)
    
    def download(self, source: str, std_no: str, output_dir: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
        """
        下载标准文档
        
        Args:
            source: 源名称 (by, zby, gbw)
            std_no: 标准号
            output_dir: 输出目录（默认使用配置）
            
        Returns:
            (文件路径, 日志列表)
        """
        if output_dir is None:
            output_dir = self.config.local_output_dir
        
        if self.config.is_local_mode():
            router = self._get_local_router()
            try:
                source_type = SourceType(source.lower())
            except ValueError:
                return None, [f"❌ 不支持的源: {source}"]
            
            response = router.download(source_type, std_no, output_dir)
            logs = response.logs if response.logs else []
            return response.file_path, logs
        else:
            return self._remote_download(source, std_no, output_dir)
    
    def health_check(self) -> Dict[str, Any]:
        """
        检查 API 健康状态
        
        Returns:
            健康检查结果字典
        """
        if self.config.is_local_mode():
            router = self._get_local_router()
            response = router.check_health()
            return {
                "status": "ok" if response.healthy else "partial",
                "available": len(response.sources),
                "total": len(response.sources),
                "sources": {s.name.value: s.to_dict() for s in response.sources}
            }
        else:
            return self._remote_health_check()
    
    def _remote_search(self, query: str, limit: int) -> Dict[str, Any]:
        """远程 API 搜索"""
        try:
            url = f"{self.config.remote_base_url}/search"
            params = {"query": query, "limit": limit}
            response = requests.get(
                url, params=params,
                timeout=self.config.remote_timeout,
                verify=self.config.verify_ssl
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            return {"error": f"远程搜索失败: {str(e)}"}
    
    def _remote_download(self, source: str, std_no: str, output_dir: str) -> Tuple[Optional[str], List[str]]:
        """远程 API 下载"""
        try:
            url = f"{self.config.remote_base_url}/download"
            data = {
                "source": source.lower(),
                "std_no": std_no,
                "output_dir": output_dir
            }
            response = requests.post(
                url, json=data,
                timeout=self.config.remote_timeout,
                verify=self.config.verify_ssl
            )
            response.raise_for_status()
            result = response.json().get("data", {})
            return result.get("file_path"), result.get("logs", [])
        except Exception as e:
            return None, [f"❌ 远程下载失败: {str(e)}"]
    
    def _remote_health_check(self) -> Dict[str, Any]:
        """远程 API 健康检查"""
        try:
            url = f"{self.config.remote_base_url}/health"
            response = requests.get(
                url, timeout=self.config.remote_timeout,
                verify=self.config.verify_ssl
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            return {"status": "error", "error": str(e)}


# 全局 API 客户端实例
_api_client: Optional[APIClient] = None


def get_api_client(config=None) -> APIClient:
    """获取全局 API 客户端实例"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient(config)
    return _api_client


def reset_api_client(config=None) -> APIClient:
    """重置 API 客户端"""
    global _api_client
    _api_client = APIClient(config)
    return _api_client
