# -*- coding: utf-8 -*-
"""
Sources Package - 所有数据源的集中点
"""

# 导入基础设施
from .base import BaseSource, DownloadResult
from .registry import registry

# 导入所有数据源（它们会在导入时自动注册）
from . import gbw
from . import zby
from . import by

__all__ = [
    "BaseSource",
    "DownloadResult",
    "registry",
    "gbw",
    "zby",
    "by",
]
