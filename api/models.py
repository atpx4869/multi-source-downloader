# -*- coding: utf-8 -*-
"""
Unified API Response Models - 统一的 API 响应模型

已迁移到使用 UnifiedStandard
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from enum import Enum

# 导入统一模型
from core.unified_models import UnifiedStandard


class SourceType(str, Enum):
    """源类型"""
    BY = "BY"      # 标院内网系统
    ZBY = "ZBY"    # 正规宝
    GBW = "GBW"    # GB/T 网


class DownloadStatus(str, Enum):
    """下载状态"""
    SUCCESS = "success"        # 成功
    FAILED = "failed"          # 失败
    IN_PROGRESS = "progress"   # 进行中
    NOT_FOUND = "not_found"    # 未找到
    ERROR = "error"            # 错误


# 为了向后兼容，保留 StandardInfo 作为 UnifiedStandard 的别名
StandardInfo = UnifiedStandard


@dataclass
class SearchResponse:
    """搜索响应"""
    source: SourceType                           # 源
    query: str                                   # 搜索词
    count: int                                   # 找到的标准数量
    items: List[UnifiedStandard] = field(default_factory=list)  # 搜索结果（使用统一模型）
    error: Optional[str] = None                  # 错误信息
    elapsed_time: float = 0.0                    # 耗时（秒）

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'source': self.source.value,
            'query': self.query,
            'count': self.count,
            'items': [s.to_dict() for s in self.items],
            'error': self.error,
            'elapsed_time': self.elapsed_time
        }


@dataclass
class DownloadProgress:
    """下载进度"""
    total_pages: int = 0                        # 总页数
    current_page: int = 0                       # 当前页数
    current_file_size: int = 0                  # 当前文件大小（字节）

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


@dataclass
class DownloadResponse:
    """下载响应"""
    source: SourceType                           # 源
    std_no: str                                  # 标准编号
    status: DownloadStatus                       # 状态
    file_path: Optional[str] = None              # 本地文件路径
    filename: Optional[str] = None               # 文件名
    file_size: int = 0                           # 文件大小（字节）
    error: Optional[str] = None                  # 错误信息
    logs: List[str] = field(default_factory=list)  # 日志消息
    progress: Optional[DownloadProgress] = None  # 进度信息
    elapsed_time: float = 0.0                    # 耗时（秒）

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'source': self.source.value,
            'std_no': self.std_no,
            'status': self.status.value,
            'file_path': self.file_path,
            'filename': self.filename,
            'file_size': self.file_size,
            'error': self.error,
            'logs': self.logs,
            'progress': self.progress.to_dict() if self.progress else None,
            'elapsed_time': self.elapsed_time
        }


@dataclass
class SourceHealth:
    """源健康状态"""
    name: SourceType                             # 源
    available: bool                              # 是否可用
    response_time: float = 0.0                   # 响应时间（毫秒）
    error: Optional[str] = None                  # 错误信息
    last_check: float = 0.0                      # 最后检查时间戳

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'name': self.name.value,
            'available': self.available,
            'response_time': self.response_time,
            'error': self.error,
            'last_check': self.last_check
        }


@dataclass
class HealthResponse:
    """健康检查响应"""
    sources: List[SourceHealth] = field(default_factory=list)
    healthy: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'sources': [s.to_dict() for s in self.sources],
            'healthy': self.healthy,
            'timestamp': self.timestamp
        }
