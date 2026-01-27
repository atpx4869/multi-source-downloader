# -*- coding: utf-8 -*-
"""
Legacy models module - 向后兼容层

此文件已废弃，所有内容已迁移到 core/unified_models.py
为了向后兼容，这里提供别名导入
"""

# 导入统一模型和工具函数
from core.unified_models import (
    UnifiedStandard as Standard,  # 主要模型别名
    natural_key,                   # 排序工具
    sanitize_filename,             # 文件名清理工具
)

# 为了完全向后兼容，也导出 UnifiedStandard
from core.unified_models import UnifiedStandard

__all__ = [
    'Standard',
    'UnifiedStandard',
    'natural_key',
    'sanitize_filename',
]
