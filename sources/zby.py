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
                # 显式禁用代理，避免系统代理干扰
                r = requests.get(self.base_url, timeout=timeout, proxies={"http": None, "https": None})
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
                
                # 尝试多种关键词组合
                keywords_to_try = [keyword]
                # 1. 去掉斜杠和空格
                if '/' in keyword or ' ' in keyword:
                    keywords_to_try.append(keyword.replace('/', '').replace(' ', ''))
                # 2. 去掉年份 (GB/T 1234-2024 -> GB/T 1234)
                if '-' in keyword:
                    keywords_to_try.append(keyword.split('-')[0].strip())
                # 3. 仅保留数字 (GB/T 1234 -> 1234)
                num_match = re.search(r'(\d+)', keyword)
                if num_match:
                    keywords_to_try.append(num_match.group(1))
                
                # 去重并保持顺序
                keywords_to_try = list(dict.fromkeys(keywords_to_try))
                
                rows = []
                for kw in keywords_to_try:
                    try:
                        rows = search_via_api(kw, page=page, page_size=page_size, session=session)
                        if rows:
                            # 过滤结果，确保标准号匹配（模糊匹配）
                            filtered_rows = []
                            clean_keyword = re.sub(r'[^A-Z0-9]', '', keyword.upper())
                            for r in rows:
                                r_no = re.sub(r'[^A-Z0-9]', '', (r.get('standardNumDeal') or '').upper())
                                if clean_keyword in r_no or r_no in clean_keyword:
                                    filtered_rows.append(r)
                            if filtered_rows:
                                rows = filtered_rows
                                break
                    except Exception:
                        continue
                
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
                            
                            # hasPdf 为 0 并不代表不能下载，可能可以预览
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
                    # 显式禁用代理
                    r = session.get(u, params={"searchText": keyword, "q": keyword}, headers=headers, timeout=6, proxies={"http": None, "https": None})
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
            if not msg:
                return
            # 涉及保密，脱敏处理：隐藏所有网址
            msg = re.sub(r'https?://[^\s<>"]+', '[URL]', msg)
            
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
        session.trust_env = False  # 禁用系统代理
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": self.base_url,
        })

        meta = item.source_meta if isinstance(item.source_meta, dict) else {}
        
        # 0. 尝试通过 standardId 直接访问详情页
        std_id = meta.get('standardId') or meta.get('id')
        if std_id:
            detail_urls = [
                f"{self.base_url}/standard/detail/{std_id}",
                f"{self.base_url}/#/standard/detail/{std_id}",
            ]
            for du in detail_urls:
                try:
                    emit(f"ZBY: 检查详情页...")
                    r = session.get(du, timeout=8, proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        # 尝试从 HTML 中提取 UUID
                        m = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', r.text)
                        if m:
                            uuid = m.group(1)
                            emit(f"ZBY: 从详情页发现资源 UUID: {uuid[:8]}...")
                            cookies = [{ 'name': c.name, 'value': c.value } for c in session.cookies]
                            return self._download_images(uuid, item.filename(), output_dir, cookies, emit)
                        
                        # 尝试从 HTML 中提取任何看起来像 UUID 的字符串
                        uuids = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', r.text)
                        for uid in uuids:
                            emit(f"ZBY: 尝试提取到的 UUID: {uid[:8]}...")
                            res = self._download_images(uid, item.filename(), output_dir, [], emit)
                            if res: return res
                except Exception:
                    continue

        # 1. 先检查 meta 中是否存在直接可用的 pdf/文件列表（json api 可能返回）
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
                            # 显式禁用代理
                            r = requests.get(url, timeout=20, stream=True, proxies={"http": None, "https": None})
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

        # 如果已经尝试过详情页且失败了，且我们有明确的 ID，那么搜索页通常也不会有更多信息
        # 除非是想通过搜索页的 HTML 结构碰运气。这里减少搜索次数。
        if std_id:
            search_keywords = [item.std_no] # 仅尝试标准号
        else:
            title = meta.get('title') or f"{item.std_no} {item.name}".strip()
            search_keywords = [title, item.std_no]
        
        urls = [f"{self.base_url}/standardList"] # 仅尝试一个搜索接口
        
        try:
            for kw in search_keywords:
                if not kw: continue
                for u in urls:
                    try:
                        emit(f"ZBY: 尝试搜索关键词: {kw}")
                        # 显式禁用代理
                        r = session.get(u, params={"searchText": kw, "q": kw, "keyword": kw}, timeout=10, proxies={"http": None, "https": None})
                        text = getattr(r, 'text', '') or ''
                        
                        # 1. 查找 immdoc 链接
                        m = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', text)
                        if m:
                            uuid = m.group(1)
                            emit(f"ZBY: 发现资源 UUID: {uuid[:8]}...")
                            cookies = [{ 'name': c.name, 'value': c.value } for c in session.cookies]
                            return self._download_images(uuid, item.filename(), output_dir, cookies, emit)
                        
                        # 2. 查找详情页链接并跟进
                        # 匹配模式如 /standard/detail/566393 或 #/standard/detail/566393
                        detail_ids = re.findall(r'detail/(\d+)', text)
                        for did in detail_ids[:5]: # 只尝试前5个
                            detail_url = f"{self.base_url}/standard/detail/{did}"
                            try:
                                emit(f"ZBY: 尝试跟进详情页...")
                                rd = session.get(detail_url, timeout=8, proxies={"http": None, "https": None})
                                td = getattr(rd, 'text', '') or ''
                                m2 = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', td)
                                if m2:
                                    uuid = m2.group(1)
                                    emit(f"ZBY: 从详情页发现资源 UUID: {uuid[:8]}...")
                                    cookies = [{ 'name': c.name, 'value': c.value } for c in session.cookies]
                                    return self._download_images(uuid, item.filename(), output_dir, cookies, emit)
                            except Exception:
                                continue
                    except Exception:
                        continue
        except Exception:
            return None

        return None


