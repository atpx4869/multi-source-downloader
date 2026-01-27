# -*- coding: utf-8 -*-
"""
统一数据模型 - 合并 core.models.Standard 和 api.models.StandardInfo
目标：消除模型碎片化，提供单一数据源
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum
import re
import html as html_module


class SourceType(str, Enum):
    """数据源类型"""
    BY = "BY"      # 标院内网系统
    ZBY = "ZBY"    # 正规宝
    GBW = "GBW"    # GB/T 网


class StandardStatus(str, Enum):
    """标准状态"""
    ACTIVE = "现行"           # 现行有效
    ABOLISHED = "废止"        # 已废止
    UPCOMING = "即将实施"     # 即将实施
    DRAFT = "征求意见"        # 征求意见稿
    UNKNOWN = ""             # 未知


def natural_key(s: str):
    """自然排序键（用于标准号排序）"""
    parts = re.split(r"(\d+)", s or "")
    return [int(p) if p.isdigit() else p for p in parts]


def sanitize_filename(name: str) -> str:
    """
    清理文件名：移除HTML标签、HTML实体、特殊字符等
    """
    if not name:
        return "download"

    # 1. 移除所有HTML标签 <...>
    safe = re.sub(r'<[^>]+>', '', name)

    # 2. 解码HTML实体 &#123; &nbsp; 等
    try:
        safe = html_module.unescape(safe)
    except Exception:
        pass

    # 3. 移除不能用于文件名的特殊字符 \ / : * ? " < > |
    safe = re.sub(r'[\\/:*?"<>|]', '_', safe)

    # 4. 多个下划线或空格合并为一个
    safe = re.sub(r'[\s_]+', ' ', safe)

    # 5. 移除开头和结尾的空格、下划线、点
    safe = safe.strip('. _')

    # 6. 最多保留100字符（防止文件名过长）
    if len(safe) > 100:
        safe = safe[:100].rstrip('. _')

    return safe or "download"


@dataclass
class UnifiedStandard:
    """
    统一标准数据模型

    合并了 core.models.Standard 和 api.models.StandardInfo 的所有功能
    设计原则：
    1. 向后兼容：保留旧字段名作为属性
    2. 类型安全：使用 Enum 类型
    3. 多源支持：支持从多个数据源聚合
    4. 完整方法：包含所有实用方法
    """
    # 核心字段
    std_no: str                                      # 标准编号 (GB/T 3324-2024)
    name: str                                        # 标准名称

    # 日期字段（统一命名）
    publish_date: str = ""                           # 发布日期
    implement_date: str = ""                         # 实施日期

    # 状态字段
    status: str = ""                                 # 状态 (现行/废止/即将实施)
    replace_std: str = ""                            # 替代标准号

    # PDF 可用性
    has_pdf: bool = False                            # 是否有PDF版本

    # 多源支持
    sources: List[str] = field(default_factory=list) # 数据来源列表 ["GBW", "BY"]
    source_meta: Dict[str, Any] = field(default_factory=dict)  # 源特定元数据 {源名: meta}

    # 内部字段
    _display_source: Optional[str] = None            # 用于显示的首选源

    # ==================== 向后兼容属性 ====================

    @property
    def publish(self) -> str:
        """向后兼容：旧代码使用 .publish"""
        return self.publish_date

    @publish.setter
    def publish(self, value: str):
        self.publish_date = value

    @property
    def implement(self) -> str:
        """向后兼容：旧代码使用 .implement"""
        return self.implement_date

    @implement.setter
    def implement(self, value: str):
        self.implement_date = value

    # ==================== 实用方法 ====================

    def display_label(self) -> str:
        """生成显示标签：标准号 + 名称"""
        return f"{self.std_no or '-'} {self.name or ''}".strip()

    def filename(self) -> str:
        """生成文件名：清理后的标准号和名称.pdf"""
        return f"{sanitize_filename(self.display_label())}.pdf"

    def get_primary_source(self) -> Optional[str]:
        """获取主要数据源（优先级最高的）"""
        if self._display_source:
            return self._display_source
        return self.sources[0] if self.sources else None

    def get_source_meta(self, source: str) -> Dict[str, Any]:
        """获取指定源的元数据"""
        if isinstance(self.source_meta, dict):
            return self.source_meta.get(source, {})
        return {}

    def has_source(self, source: str) -> bool:
        """检查是否包含指定数据源"""
        return source in self.sources

    # ==================== 序列化方法 ====================

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            'std_no': self.std_no,
            'name': self.name,
            'publish_date': self.publish_date,
            'implement_date': self.implement_date,
            'status': self.status,
            'replace_std': self.replace_std,
            'has_pdf': self.has_pdf,
            'sources': self.sources,
            'source_meta': self.source_meta,
            '_display_source': self._display_source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedStandard':
        """从字典创建实例"""
        # 处理字段名兼容性
        publish_date = data.get('publish_date') or data.get('publish', '')
        implement_date = data.get('implement_date') or data.get('implement', '')

        return cls(
            std_no=data.get('std_no', ''),
            name=data.get('name', ''),
            publish_date=publish_date,
            implement_date=implement_date,
            status=data.get('status', ''),
            replace_std=data.get('replace_std', ''),
            has_pdf=data.get('has_pdf', False),
            sources=data.get('sources', []),
            source_meta=data.get('source_meta', {}),
            _display_source=data.get('_display_source'),
        )

    # ==================== 兼容性转换 ====================

    @classmethod
    def from_legacy_standard(cls, old: Any) -> 'UnifiedStandard':
        """从旧的 core.models.Standard 转换"""
        return cls(
            std_no=old.std_no,
            name=old.name,
            publish_date=getattr(old, 'publish', ''),
            implement_date=getattr(old, 'implement', ''),
            status=getattr(old, 'status', ''),
            replace_std=getattr(old, 'replace_std', ''),
            has_pdf=getattr(old, 'has_pdf', False),
            sources=getattr(old, 'sources', []),
            source_meta=getattr(old, 'source_meta', {}),
            _display_source=getattr(old, '_display_source', None),
        )

    @classmethod
    def from_api_standard_info(cls, info: Any, source: str) -> 'UnifiedStandard':
        """从 api.models.StandardInfo 转换"""
        return cls(
            std_no=info.std_no,
            name=info.name,
            publish_date=getattr(info, 'publish_date', None) or '',
            implement_date=getattr(info, 'implement_date', None) or '',
            status=getattr(info, 'status', None) or '',
            replace_std=getattr(info, 'replace_std', None) or '',
            has_pdf=getattr(info, 'has_pdf', False),
            sources=[source],
            source_meta={source: getattr(info, 'source_meta', {})},
        )

    def to_legacy_standard(self) -> 'UnifiedStandard':
        """转换为旧的 core.models.Standard（用于渐进式迁移）

        注意：由于已经完成统一，现在直接返回自身
        """
        return self

    # ==================== 比较和排序 ====================

    def __lt__(self, other: 'UnifiedStandard') -> bool:
        """支持排序（按标准号自然排序）"""
        return natural_key(self.std_no) < natural_key(other.std_no)

    def __eq__(self, other: object) -> bool:
        """相等性比较（基于标准号）"""
        if not isinstance(other, UnifiedStandard):
            return False
        return self.std_no == other.std_no

    def __hash__(self) -> int:
        """支持作为字典键或集合元素"""
        return hash(self.std_no)

    def __repr__(self) -> str:
        """调试输出"""
        sources_str = ','.join(self.sources) if self.sources else 'None'
        return f"UnifiedStandard({self.std_no}, sources=[{sources_str}])"


# ==================== 便捷别名 ====================

# 为了最小化代码改动，提供别名
Standard = UnifiedStandard  # 可以直接替换 from core.models import Standard


# ==================== 批量转换工具 ====================

def convert_legacy_standards(old_standards: List[Any]) -> List[UnifiedStandard]:
    """批量转换旧模型列表"""
    return [UnifiedStandard.from_legacy_standard(s) for s in old_standards]


def convert_to_legacy_standards(unified_standards: List[UnifiedStandard]) -> List[Any]:
    """批量转换为旧模型列表（用于渐进式迁移）"""
    return [s.to_legacy_standard() for s in unified_standards]
