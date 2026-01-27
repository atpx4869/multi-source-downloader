# -*- coding: utf-8 -*-
"""
Base Source Protocol - 统一的数据源接口定义

定义了所有数据源必须遵守的协议，包括：
1. 数据结构：DownloadResult（统一的下载结果）
2. 接口：BaseSource（抽象基类）
3. 元数据：SourceMetadata（源描述）
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod


@dataclass
class DownloadResult:
    """统一的下载结果数据结构
    
    Attributes:
        success: 下载是否成功
        file_path: 下载文件的完整路径（成功时有值）
        error: 错误信息（失败时有值）
        logs: 下载过程日志列表（便于诊断）
    """
    success: bool
    file_path: Optional[Path] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """验证数据一致性"""
        if self.success and not self.file_path:
            raise ValueError("success=True 时必须提供 file_path")
        if not self.success and not self.error:
            self.error = "Unknown error"
    
    @classmethod
    def ok(cls, file_path: Path, logs: List[str] = None) -> "DownloadResult":
        """创建成功结果"""
        return cls(success=True, file_path=file_path, logs=logs or [])
    
    @classmethod
    def fail(cls, error: str, logs: List[str] = None) -> "DownloadResult":
        """创建失败结果"""
        return cls(success=False, error=error, logs=logs or [])


class BaseSource(ABC):
    """所有数据源必须继承的基类
    
    约定：
    1. 实现必须是无状态的（除了初始化参数）
    2. 所有网络操作必须有超时控制
    3. 不允许直接 print/log，使用 log_cb 回调
    4. 所有异常必须被正确处理并返回在 DownloadResult 中
    """
    
    # 源标识符（唯一）
    source_id: str = None
    
    # 源显示名称
    source_name: str = None
    
    # 优先级（1=最高，用于多源结果合并时的排序）
    priority: int = 999
    
    @classmethod
    def can_handle(cls, url: str = None, keyword: str = None) -> bool:
        """判断该源是否可以处理指定的 URL 或关键词
        
        Args:
            url: 可选的 URL
            keyword: 可选的搜索关键词
            
        Returns:
            True 表示该源可处理此请求
        """
        return True  # 默认都能处理
    
    @abstractmethod
    def search(self, keyword: str, page_size: int = 20) -> List["Standard"]:
        """搜索标准
        
        Args:
            keyword: 搜索关键词
            page_size: 返回结果数量
            
        Returns:
            Standard 对象列表
        """
        pass
    
    @abstractmethod
    def download(self, std: "Standard", outdir: Path) -> DownloadResult:
        """下载标准文档
        
        Args:
            std: Standard 对象
            outdir: 输出目录
            
        Returns:
            DownloadResult 对象
            
        约定：
        - 必须返回 DownloadResult，不能返回 None/False/Path
        - 所有错误（网络、解析、文件 IO）都必须被捕获
        - logs 字段应记录关键步骤（便于调试）
        - 不允许抛出异常给上层（除了设计错误）
        """
        pass


# Type hint 用 strings 避免循环导入
Standard = Dict[str, Any]
