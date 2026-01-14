# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
import re
import html as html_module


def natural_key(s: str):
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
class Standard:
    std_no: str
    name: str
    publish: str = ""
    implement: str = ""
    status: str = ""
    replace_std: str = ""  # 替代标准号
    has_pdf: bool = False
    source_meta: Dict = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)

    def display_label(self) -> str:
        return f"{self.std_no or '-'} {self.name or ''}".strip()

    def filename(self) -> str:
        return f"{sanitize_filename(self.display_label())}.pdf"
