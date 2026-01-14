# -*- coding: utf-8 -*-
"""
已知的标准替代关系补充数据库
用于补充 ZBY 和 GBW API 中缺失的替代标准信息
"""
import re
from functools import lru_cache

# 预编译正则表达式
_NORMALIZE_PATTERN = re.compile(r'[\s\-–—_/]')

# 格式：{旧标准号（规范化）: 新标准号}
# 这些是已知会被替代的标准关系
KNOWN_REPLACEMENTS = {
    # GB 28008 系列
    "GB280081995": "GB 28008-2011",  # GB 28008-1995 被 GB 28008-2011 替代
    "GB280082011": "GB 28008-2024",  # GB 28008-2011 被 GB 28008-2024 替代
    
    # 可以在此添加更多已知的替代关系
    # 格式：旧版本 -> 新版本
}

@lru_cache(maxsize=512)
def _normalize_for_replacement(std_no: str) -> str:
    """规范化标准号以查询替代关系（带缓存）"""
    if not std_no:
        return ""
    return _NORMALIZE_PATTERN.sub('', std_no).upper()


@lru_cache(maxsize=512)
def get_replacement_standard(std_no: str) -> str:
    """
    获取标准的替代标准（带缓存）
    
    Args:
        std_no: 标准号（如 GB 28008-2011）
    
    Returns:
        替代标准号，如果没有则返回空字符串
    """
    if not std_no:
        return ""
    
    # 规范化标准号
    normalized = _normalize_for_replacement(std_no)
    
    # 查找已知的替代关系
    return KNOWN_REPLACEMENTS.get(normalized, "")
