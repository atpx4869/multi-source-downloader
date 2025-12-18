# -*- coding: utf-8 -*-
"""
Lightweight ZBY adapter with HTTP-first fallback and debug artifact mirroring.

This module avoids importing Playwright at module-import time so it is safe
to include in frozen executables. If Playwright is needed it will be loaded
only at runtime by explicit callers.
"""
from pathlib import Path
from typing import List, Union
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

    def __init__(self, output_dir: Union[Path, str] = "downloads"):
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
            session.trust_env = False  # 忽略系统代理
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
                            # Prefer standardNum (contains HTML) over standardNumDeal (stripped)
                            # but we must strip HTML tags from standardNum
                            raw_no = row.get('standardNum') or row.get('standardNumDeal') or ''
                            std_no = re.sub(r'<[^>]+>', '', raw_no).strip()
                            
                            name = (row.get('standardName') or '').strip()
                            # Also strip HTML from name just in case
                            name = re.sub(r'<[^>]+>', '', name).strip()
                            
                            has_pdf = bool(int(row.get('hasPdf', 0))) if row.get('hasPdf') is not None else False
                            # standardStatus is provided as numeric code by the backend; map to human-readable labels
                            from .status_map import map_status
                            status = map_status(row.get('standardStatus'))
                            meta = row
                            # Normalize publish/implement fields from possible API keys
                            pub = (row.get('standardPubTime') or row.get('publish') or '')
                            impl = (row.get('standardUsefulDate') or row.get('standardUsefulTime') or row.get('standardUseDate') or row.get('implement') or '')
                            items.append(Standard(std_no=std_no, name=name, publish=str(pub)[:10], implement=str(impl)[:10], status=status, has_pdf=has_pdf, source_meta=meta, sources=['ZBY']))
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

    def download(self, item: Standard, outdir: Path, log_cb=None):
        """下载标准。签名兼容两种调用方式：
        - download(item, outdir, log_cb=callable)  -> (Path|None, list[str])
        - download(item, outdir) -> Path|None
        返回 (path, logs) 或直接 path/None（兼容旧实现）。
        """
        outdir.mkdir(parents=True, exist_ok=True)
        logs = []
        def emit(msg: str):
            logs.append(msg)
            if callable(log_cb):
                try:
                    log_cb(msg)
                except Exception:
                    pass

        # Prefer client implementation when available
        if self.client is not None and hasattr(self.client, 'download_standard'):
            try:
                path = self.client.download_standard(item.source_meta)
                p = Path(path) if path else None
                if callable(log_cb):
                    return p, logs
                return p
            except Exception as e:
                emit(f"ZBY: client.download_standard 异常: {e}")

        # 一步：尝试通过 HTTP 直接从详情页提取资源 UUID 并下载（无需 Playwright）
        try:
            http_try = self._http_download_via_uuid(item, outdir, emit)
            if http_try is not None:
                return http_try
        except Exception as e:
            emit(f"ZBY: HTTP 回退提取 UUID 失败: {e}")

        if self.allow_playwright:
            try:
                from .zby_playwright import ZBYSource as PWZBYSource  # type: ignore
                pw = PWZBYSource(output_dir=outdir)
                try:
                    result = pw.download(item, outdir, log_cb=log_cb)
                except TypeError:
                    result = pw.download(item, outdir)
                # 确保返回格式一致
                if isinstance(result, tuple):
                    return result
                else:
                    if callable(log_cb):
                        return (Path(result) if result else None, logs)
                    return Path(result) if result else None
            except Exception as e:
                emit(f"ZBY: Playwright 回落失败: {e}")

        emit("ZBY: 无法下载（缺少 StandardDownloader 且 Playwright 不可用或失败）")
        if callable(log_cb):
            return None, logs
        return None

    def _http_download_via_uuid(self, item: Standard, output_dir: Path, emit: callable):
        """试图通过 HTTP 抓取详情页或搜索页 HTML，查找 immdoc/{uuid}/doc 链接并直接下载图片合成 PDF。"""
        try:
            import requests
        except Exception:
            return None

        emit("ZBY: 尝试 HTTP 回退提取资源 UUID...")
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": self.base_url,
        })

        meta = item.source_meta if isinstance(item.source_meta, dict) else {}
        # 先检查 meta 中是否存在直接可用的 pdf/文件列表（json api 可能返回）
        try:
            for list_key in ('pdfList', 'taskPdfList', 'fileList', 'files'):
                lst = meta.get(list_key)
                if not lst:
                    continue
                # 期望 lst 为可迭代的条目集合
                for entry in (lst if isinstance(lst, list) else [lst]):
                    url = None
                    if isinstance(entry, dict):
                        # 常见字段名
                        for k in ('url', 'fileUrl', 'downloadUrl', 'resourceUrl'):
                            if entry.get(k):
                                url = entry.get(k)
                                break
                        # 某些接口返回的是资源id或uuid字段
                        if not url:
                            for k in ('uuid', 'resourceId', 'docId', 'fileId'):
                                if entry.get(k):
                                    # 构造可能的 immdoc 链接
                                    url = f"https://resource.zhenggui.vip/immdoc/{entry.get(k)}/doc/I/1"
                                    break
                    elif isinstance(entry, str):
                        url = entry

                    if not url:
                        continue

                    # 若链接中包含 immdoc，尝试提取 uuid 并用现有 _download_images
                    m = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', url)
                    if m:
                        uuid = m.group(1)
                        cookies = []
                        emit(f"ZBY: 从 meta 发现可用资源 UUID: {uuid[:8]}...，尝试 HTTP 下载")
                        return self._download_images(uuid, item.filename(), output_dir, cookies, emit)

                    # 若为 PDF 文件链接，直接下载并保存
                    try:
                        if url.lower().endswith('.pdf') or 'download' in url or 'pdf' in url:
                            import requests
                            r = requests.get(url, timeout=20, stream=True)
                            if r.status_code == 200:
                                outp = output_dir / item.filename()
                                with open(outp, 'wb') as f:
                                    for chunk in r.iter_content(8192):
                                        if chunk:
                                            f.write(chunk)
                                emit(f"ZBY: 从 meta 下载到 PDF -> {outp}")
                                return outp, []
                    except Exception:
                        # 下载失败则继续尝试其他条目/方法
                        continue
        except Exception:
            pass
        title = meta.get('title') or f"{item.std_no} {item.name}".strip()
        urls = [f"{self.base_url}/standardList", f"{self.base_url}/search", f"{self.base_url}/api/search"]
        try:
            # 首先在搜索页 HTML 中查找 uuid
            for u in urls:
                try:
                    r = session.get(u, params={"searchText": title, "q": title}, timeout=8)
                    text = getattr(r, 'text', '') or ''
                    m = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', text)
                    if m:
                        uuid = m.group(1)
                        cookies = [{ 'name': c.name, 'value': c.value } for c in session.cookies]
                        return self._download_images(uuid, item.filename(), output_dir, cookies, emit)
                    # 否则尝试在页面中找到可能的详情页链接并请求
                    hrefs = re.findall(r'href=["\']([^"\']+)["\']', text)
                    for href in hrefs:
                        if href and ("/standard" in href or "#/" in href or "detail" in href):
                            if href.startswith('/'):
                                detail_url = f"{self.base_url}{href}"
                            elif href.startswith('http'):
                                detail_url = href
                            else:
                                detail_url = f"{self.base_url}/{href}"
                            try:
                                rd = session.get(detail_url, timeout=8)
                                td = getattr(rd, 'text', '') or ''
                                m2 = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', td)
                                if m2:
                                    uuid = m2.group(1)
                                    cookies = [{ 'name': c.name, 'value': c.value } for c in session.cookies]
                                    return self._download_images(uuid, item.filename(), output_dir, cookies, emit)
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception:
            return None

        return None


