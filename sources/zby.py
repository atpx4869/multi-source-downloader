# -*- coding: utf-8 -*-
"""
Lightweight ZBY adapter with HTTP-first fallback and debug artifact mirroring.

This module avoids importing Playwright at module-import time so it is safe
to include in frozen executables. If Playwright is needed it will be loaded
only at runtime by explicit callers.
"""
from pathlib import Path
from typing import List
import re
import tempfile
import shutil
import os

DEFAULT_BASE_URL = "https://bz.zhenggui.vip"

from core.models import Standard, natural_key


try:
    from standard_downloader import StandardDownloader  # type: ignore
except Exception:
    StandardDownloader = None


def _mirror_debug_file_static(p: Path) -> None:
    try:
        p = Path(p)
        if not p.exists():
            return
        tm = Path(tempfile.gettempdir())
        try:
            tm.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(p), str(tm / p.name))
        except Exception:
            pass
        try:
            desk = Path(os.path.expanduser('~')) / 'Desktop'
            desk.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(p), str(desk / p.name))
        except Exception:
            pass
    except Exception:
        pass


class ZBYSource:
    name = "ZBY"
    priority = 3

    def __init__(self, output_dir: Path | str = "downloads"):
        od = Path(output_dir)
        try:
            if (isinstance(output_dir, str) and output_dir == "downloads") or (isinstance(output_dir, Path) and not Path(output_dir).is_absolute()):
                repo_root = Path(__file__).resolve().parents[1]
                od = repo_root / "downloads"
        except Exception:
            od = Path(output_dir)
        self.output_dir = Path(od)

        try:
            import sys as _sys
            frozen = getattr(_sys, 'frozen', False)
        except Exception:
            frozen = False

        self.client = None
        self.allow_playwright = False if frozen else True
        self.base_url = DEFAULT_BASE_URL

        if not frozen and StandardDownloader is not None:
            try:
                self.client = StandardDownloader(output_dir=self.output_dir)
                self.base_url = getattr(self.client, 'base_url', DEFAULT_BASE_URL)
            except Exception:
                self.client = None
                self.base_url = DEFAULT_BASE_URL

    def _mirror_debug_file(self, p: Path) -> None:
        try:
            _mirror_debug_file_static(p)
        except Exception:
            pass

    def is_available(self, timeout: int = 6) -> bool:
        try:
            import sys as _sys
            frozen = getattr(_sys, 'frozen', False)
        except Exception:
            frozen = False

        try:
            if frozen:
                import requests
                r = requests.get(self.base_url, timeout=timeout)
                return 200 <= getattr(r, 'status_code', 0) < 400
            if self.client is not None and hasattr(self.client, 'is_available'):
                return bool(self.client.is_available())
            return True
        except Exception:
            return False

    def search(self, keyword: str, **kwargs) -> List[Standard]:
        items: List[Standard] = []

        # First try client implementation (if available)
        if self.client is not None:
            try:
                rows = self.client.search(keyword, **kwargs)
                if rows:
                    return rows
            except Exception:
                pass

        # HTTP fallback
        try:
            http_items = self._http_search(keyword, **kwargs)
            if http_items:
                return http_items
        except Exception:
            pass

        # Playwright fallback (only when allowed)
        if self.allow_playwright:
            try:
                from .zby_playwright import ZBYSource as PWZBYSource  # type: ignore
                pw = PWZBYSource(self.output_dir)
                return pw.search(keyword, **kwargs)
            except Exception:
                pass

        return items

    def _http_search(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
        items: List[Standard] = []
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retries = Retry(total=2, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504))
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('https://', adapter)
            session.mount('http://', adapter)

            # Try JSON API first via helper
            try:
                from .zby_http import search_via_api
                rows = search_via_api(keyword, page=page, page_size=page_size, session=session)
                if rows:
                    for row in rows:
                        try:
                            std_no = (row.get('standardNumDeal') or row.get('standardNum') or '').strip()
                            name = (row.get('standardName') or '').strip()
                            has_pdf = bool(int(row.get('hasPdf', 0))) if row.get('hasPdf') is not None else False
                            # standardStatus is provided as numeric code by the backend; map to human-readable labels
                            from .status_map import map_status
                            status = map_status(row.get('standardStatus'))
                            meta = row
                            items.append(Standard(std_no=std_no, name=name, publish=str(row.get('standardPubTime') or ''), implement='', status=status, has_pdf=has_pdf, source_meta=meta, sources=['ZBY']))
                        except Exception:
                            pass
                    return items[:int(page_size)]
            except Exception:
                pass

            # HTML fallback (existing behavior)
            urls = [f"{self.base_url}/standardList", f"{self.base_url}/search", f"{self.base_url}/api/search"]
            resp_text = ""
            for u in urls:
                try:
                    r = session.get(u, params={"searchText": keyword, "q": keyword}, headers=headers, timeout=6)
                    if r.status_code == 200 and r.text and len(r.text) > 200:
                        resp_text = r.text
                        break
                except Exception:
                    continue

            if not resp_text:
                return items

            blocks = re.findall(r'<h4.*?>(.*?)</h4>', resp_text, re.S)
            for title_html in blocks:
                title = re.sub(r'<.*?>', '', title_html).strip()
                if not title:
                    continue
                std_no = ''
                name = title
                m = re.match(r'^([A-Z0-9/\\-\\. ]+)\\s+(.*)$', title)
                if m:
                    std_no = m.group(1).strip()
                    name = m.group(2).strip()
                items.append(Standard(std_no=std_no, name=name, publish='', implement='', status='', has_pdf=False, source_meta={"title": title}, sources=['ZBY']))
            return items[:int(page_size)]
        except Exception:
            return items

    def download(self, item: Standard, outdir: Path) -> Path | None:
        outdir.mkdir(parents=True, exist_ok=True)
        if self.client is not None and hasattr(self.client, 'download_standard'):
            try:
                path = self.client.download_standard(item.source_meta)
                return Path(path) if path else None
            except Exception:
                return None
        return None


