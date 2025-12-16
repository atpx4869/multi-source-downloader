# -*- coding: utf-8 -*-
"""
GBW Source - 国家标准信息公共服务平台 (std.samr.gov.cn)
"""
import re
import requests
from pathlib import Path
from typing import List, Callable

from core.models import Standard


class GBWSource:
    """GBW (国标委) Data Source"""
    
    def __init__(self):
        self.name = "GBW"
        self.priority = 1
        self.base_url = "https://std.samr.gov.cn"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    
    def _clean_text(self, text: str) -> str:
        """Clean XML tags from text, preserving inner content"""
        if not text:
            return ""
        # Remove tags but keep inner text
        cleaned = re.sub(r'<[^>]+>', '', text)
        return cleaned.strip()
    
    def _parse_std_code(self, raw_code: str) -> str:
        """Parse standard code like 'GB/T <sacinfo>33260.3-2018</sacinfo>' -> 'GB/T 33260.3-2018'"""
        if not raw_code:
            return ""
        # Extract prefix (GB/T, GB, etc.)
        prefix_match = re.match(r'^([A-Z]+(?:/[A-Z]+)?)\s*', raw_code)
        prefix = prefix_match.group(1) if prefix_match else ""
        
        # Extract number from sacinfo tag or directly
        sacinfo_match = re.search(r'<sacinfo>([^<]+)</sacinfo>', raw_code)
        if sacinfo_match:
            number = sacinfo_match.group(1)
        else:
            # Remove prefix and clean
            number = self._clean_text(raw_code)
            if prefix and number.startswith(prefix):
                number = number[len(prefix):].strip()
        
        return f"{prefix} {number}".strip() if prefix else number
    
    def search(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
        """Search standards from GBW API"""
        items = []
        try:
            search_url = f"{self.base_url}/gb/search/gbQueryPage"
            params = {
                "searchText": keyword,
                "pageNum": page,
                "pageSize": page_size
            }
            
            resp = self.session.get(search_url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("rows", [])
                
                for row in rows:
                    # Parse standard code properly
                    std_code = self._parse_std_code(row.get("C_STD_CODE", ""))
                    std_name = self._clean_text(row.get("C_C_NAME", ""))
                    
                    # Check if PDF is available (current or upcoming standards have PDF)
                    status = row.get("STATE", "")
                    has_pdf = "现行" in status or "即将实施" in status
                    
                    std = Standard(
                        std_no=std_code,
                        name=std_name,
                        publish=row.get("ISSUE_DATE", ""),
                        implement=row.get("ACT_DATE", ""),
                        status=status,
                        has_pdf=has_pdf,
                        source_meta={
                            "id": row.get("id", ""),
                            "hcno": row.get("HCNO", "")
                        },
                        sources=["GBW"]
                    )
                    items.append(std)
                    
        except Exception as e:
            print(f"GBW search error: {e}")
        
        return items
    
    def _get_hcno(self, item_id: str) -> str:
        """Get HCNO from detail page"""
        try:
            detail_url = f"{self.base_url}/gb/search/gbDetailed?id={item_id}"
            resp = self.session.get(detail_url, timeout=10)
            match = re.search(r'hcno=([A-F0-9]{32})', resp.text)
            if match:
                return match.group(1)
        except:
            pass
        return ""
    
    def download(self, item: Standard, output_dir: Path, log_cb: Callable[[str], None] = None) -> tuple[Path | None, list[str]]:
        """Download PDF from GBW - requires browser automation for captcha"""
        logs = []
        
        def emit(msg: str):
            logs.append(msg)
            if log_cb:
                log_cb(msg)
        
        try:
            meta = item.source_meta
            item_id = meta.get("id", "") if isinstance(meta, dict) else ""
            
            if not item_id:
                emit("GBW: 未找到标准ID")
                return None, logs
            
            # Get HCNO
            emit("GBW: 获取下载链接...")
            hcno = self._get_hcno(item_id)
            
            if not hcno:
                emit("GBW: 无法获取HCNO，该标准可能仅提供目录")
                return None, logs
            
            emit(f"GBW: 找到HCNO: {hcno[:8]}...")
            emit("GBW: 此源需要验证码，将尝试其他来源")
            
            # GBW download requires playwright and OCR for captcha
            return None, logs
            
        except Exception as e:
            emit(f"GBW: 下载错误: {e}")
            return None, logs

            if match:
                return match.group(1)
        except:
            pass
        return ""
    
    def download(self, item: Standard, output_dir: Path, log_cb: Callable[[str], None] = None) -> tuple[Path | None, list[str]]:
        """Download PDF from GBW - requires browser automation for captcha"""
        logs = []
        
        def emit(msg: str):
            logs.append(msg)
            if log_cb:
                log_cb(msg)
        
        emit("GBW: This source requires browser automation for captcha verification")
        emit("GBW: Please use ZBY source as fallback")
        
        # GBW download requires playwright and OCR for captcha
        # This is a simplified version that just indicates the limitation
        return None, logs
