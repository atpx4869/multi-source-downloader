# -*- coding: utf-8 -*-
"""
源类加载器 - 动态导入各数据源的实现类
"""
from typing import Tuple, Optional, Type


def load_source_class(module_name: str, class_name: str) -> Tuple[Optional[Type], Optional[str]]:
    """
    动态加载源类
    
    Args:
        module_name: 模块名（如 'sources.gbw'）
        class_name: 类名（如 'GBWSource'）
        
    Returns:
        (类对象, 错误信息) - 加载成功返回 (cls, None)，失败返回 (None, error_msg)
    """
    try:
        # 动态导入模块
        module = __import__(module_name, fromlist=[class_name])
        
        # 获取类对象
        if not hasattr(module, class_name):
            return None, f"模块 {module_name} 中找不到类 {class_name}"
        
        cls = getattr(module, class_name)
        return cls, None
        
    except ImportError as e:
        return None, f"导入模块 {module_name} 失败: {str(e)}"
    except Exception as e:
        return None, f"加载 {module_name}.{class_name} 失败: {str(e)}"
