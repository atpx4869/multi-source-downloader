# -*- coding: utf-8 -*-
"""
ZBY adapter - prefer user-provided implementation if available, else fall back to Playwright backup.
This module exposes `ZBYSource` class compatible with AggregatedDownloader.
"""
from pathlib import Path
from typing import List

from core.models import Standard, natural_key, sanitize_filename


try:
    # Try to use user's StandardDownloader-based implementation (if available in environment)
    from standard_downloader import StandardDownloader  # type: ignore

    class ZBYSource:
        name = "ZBY"
        priority = 3

        def __init__(self, output_dir: Path | str = "downloads"):
            self.output_dir = Path(output_dir)
            self.client = StandardDownloader(output_dir=self.output_dir)

        def is_available(self, timeout: int = 6) -> bool:
            """检测 ZBY 源是否可用：优先使用 client 提供的检测方法或尝试访问 base_url 属性。"""
            try:
                if hasattr(self.client, 'is_available') and callable(getattr(self.client, 'is_available')):
                    return bool(self.client.is_available())
                # 如果 client 提供 base_url，则尝试请求
                if hasattr(self.client, 'base_url'):
                    import requests
                    r = requests.get(getattr(self.client, 'base_url'), timeout=timeout)
                    return 200 <= getattr(r, 'status_code', 0) < 400
                return True
            except Exception:
                return False

        def search(self, keyword: str, **kwargs) -> List[Standard]:
                # Try using user-provided client first
                try:
                    data = self.client.search(keyword, **kwargs)
                except Exception:
                    data = None

                rows = []
                items: List[Standard] = []

                # support two possible client.search return formats:
                # - dict with 'rows' key (legacy StandardDownloader)
                # - list of dicts or already a list of Standard-like dicts
                if isinstance(data, dict):
                    rows = data.get("rows") or []
                elif isinstance(data, list):
                    rows = data

                # convert rows (dicts) into Standard objects when necessary
                for r in rows:
                    if isinstance(r, Standard):
                        items.append(r)
                    else:
                        items.append(
                            Standard(
                                std_no=(r.get("standardNum") or r.get("std_no") or "").strip(),
                                name=(r.get("standardName") or r.get("name") or "").strip(),
                                publish=(r.get("standardPubTime") or r.get("publish") or "")[:10],
                                implement=(r.get("standardUsefulDate") or r.get("implement") or "")[:10],
                                status=str(r.get("standardStatus") or r.get("status") or ""),
                                has_pdf=bool(r.get("hasPdf") or r.get("has_pdf") or False),
                                source_meta=r,
                                sources=["ZBY"],
                            )
                        )

                # If client returned no rows, try fallback to Playwright implementation
                if not items:
                    try:
                        from .zby_playwright import ZBYSource as PWZBYSource  # type: ignore
                        pw = PWZBYSource(self.output_dir)
                        pw_items = pw.search(keyword, **kwargs)
                        if pw_items:
                            items = pw_items
                    except Exception:
                        # ignore fallback errors and return empty list
                        pass

                items.sort(key=lambda x: natural_key(x.std_no))
                return items

        def download(self, item: Standard, outdir: Path) -> Path | None:
            outdir.mkdir(parents=True, exist_ok=True)
            try:
                self.client.output_dir = Path(outdir)
            except Exception:
                pass
            pdf_path = self.client.download_standard(item.source_meta)
            return Path(pdf_path) if pdf_path else None

except Exception:
    # Fall back to Playwright-based implementation
    from .zby_playwright import ZBYSource  # type: ignore


