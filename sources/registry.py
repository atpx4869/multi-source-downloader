# -*- coding: utf-8 -*-
"""
Source Registry - 统一的数据源注册表

作用：
1. 集中管理所有可用的数据源
2. 提供源的识别和加载逻辑
3. 消除业务代码中的 if/elif 分支
4. 便于新增数据源（只需注册，无需改业务代码）
"""

from typing import List, Type, Optional, Dict
from .base import BaseSource


class SourceRegistry:
    """源注册表
    
    使用方式：
    
    @registry.register
    class MySource(BaseSource):
        source_id = "my_source"
        ...
    """
    
    def __init__(self):
        self._sources: Dict[str, Type[BaseSource]] = {}
        self._priority_order: List[str] = []
    
    def register(self, source_cls: Type[BaseSource]) -> Type[BaseSource]:
        """注册一个数据源
        
        Args:
            source_cls: BaseSource 的子类
            
        Returns:
            原 source_cls（支持装饰器用法）
        """
        if not hasattr(source_cls, 'source_id') or not source_cls.source_id:
            raise ValueError(f"{source_cls.__name__} 必须定义 source_id")
        
        source_id = source_cls.source_id
        if source_id in self._sources:
            raise ValueError(f"源 {source_id} 已注册，不能重复注册")
        
        self._sources[source_id] = source_cls
        
        # 按优先级排序
        self._priority_order = sorted(
            self._sources.keys(),
            key=lambda sid: self._sources[sid].priority
        )
        
        return source_cls
    
    def get(self, source_id: str) -> Optional[Type[BaseSource]]:
        """获取指定 ID 的源类
        
        Args:
            source_id: 源标识符
            
        Returns:
            源类，如果不存在返回 None
        """
        return self._sources.get(source_id)
    
    def get_instance(self, source_id: str) -> Optional[BaseSource]:
        """获取指定 ID 的源实例
        
        Args:
            source_id: 源标识符
            
        Returns:
            源实例，如果不存在返回 None
        """
        source_cls = self.get(source_id)
        if source_cls:
            return source_cls()
        return None
    
    def get_all(self) -> List[Type[BaseSource]]:
        """获取所有注册的源类（按优先级排序）
        
        Returns:
            源类列表
        """
        return [self._sources[sid] for sid in self._priority_order]
    
    def get_all_instances(self) -> List[BaseSource]:
        """获取所有注册的源实例（按优先级排序）
        
        Returns:
            源实例列表
        """
        return [source_cls() for source_cls in self.get_all()]
    
    def identify(self, url: str = None, keyword: str = None) -> List[Type[BaseSource]]:
        """识别可以处理指定 URL/关键词的源列表（优先级排序）
        
        Args:
            url: 可选的 URL
            keyword: 可选的搜索关键词
            
        Returns:
            可处理该请求的源类列表（按优先级从高到低）
        """
        candidates = []
        for source_cls in self.get_all():
            if source_cls.can_handle(url=url, keyword=keyword):
                candidates.append(source_cls)
        return candidates
    
    def list_sources(self) -> List[Dict[str, str]]:
        """列出所有已注册的源信息（用于 UI 显示）
        
        Returns:
            [{"id": "...", "name": "...", "priority": ...}, ...]
        """
        result = []
        for source_cls in self.get_all():
            result.append({
                "id": source_cls.source_id,
                "name": source_cls.source_name or source_cls.source_id,
                "priority": source_cls.priority,
            })
        return result
    
    def __repr__(self):
        sources_info = ", ".join([
            f"{cls.source_id}(priority={cls.priority})"
            for cls in self.get_all()
        ])
        return f"SourceRegistry({sources_info})"


# 全局注册表实例
registry = SourceRegistry()
