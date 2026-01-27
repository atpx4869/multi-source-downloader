# -*- coding: utf-8 -*-
"""
Lightweight ZBY adapter with HTTP-first fallback and debug artifact mirroring.

This module avoids importing Playwright at module-import time so it is safe
to include in frozen executables. If Playwright is needed it will be loaded
only at runtime by explicit callers.
"""
from pathlib import Path
from typing import Dict, List, Union, Optional
import re
import tempfile
import shutil
import os
import urllib3

# 抑制 urllib3 的 SSL 验证警告（我们故意禁用 SSL 验证以兼容国内网站）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from requests import Response

DEFAULT_BASE_URL = "https://bz.zhenggui.vip"

from core.models import Standard
from .base import BaseSource, DownloadResult
from .registry import registry

# 导入超时配置
try:
    from core.timeout_config import get_timeout
except ImportError:
    def get_timeout(source: str, operation: str) -> int:
        return 10


# Prefer local shim; fall back to dotted import for compatibility
try:
    from .standard_downloader import StandardDownloader  # type: ignore
except Exception:
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


@registry.register
class ZBYSource(BaseSource):
    source_id = "zby"
    source_name = "正规标准网"
    priority = 3

    name = "ZBY"

    # 使用统一的超时配置
    SEARCH_TIMEOUT = get_timeout("ZBY", "search")
    DOWNLOAD_TIMEOUT = get_timeout("ZBY", "download")
    API_TIMEOUT = get_timeout("ZBY", "api")

    def __init__(self, output_dir: Union[Path, str] = "downloads") -> None:
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
        self.allow_playwright: bool = False if frozen else True
        self.base_url: str = DEFAULT_BASE_URL
        self.api_base_url = None

        if not frozen and StandardDownloader is not None:
            try:
                self.client = StandardDownloader(output_dir=self.output_dir)
                self.base_url = getattr(self.client, 'base_url', DEFAULT_BASE_URL)
            except Exception:
                self.client = None
                self.base_url: str = DEFAULT_BASE_URL

        # 尝试从前端 config.yaml 读取真实 API 基址（无需额外依赖）
        try:
            self.api_base_url: str = self._load_api_base_url_from_config(timeout=4)
        except Exception:
            self.api_base_url = None

    def _load_api_base_url_from_config(self, timeout: int = 4) -> str:
        """从 https://bz.zhenggui.vip/config.yaml 读取 BZY_BASE_URL。

        config.yaml 内容很简单，这里用正则解析，避免引入 PyYAML。
        """
        try:
            import requests
        except Exception:
            return ""
        try:
            url = f"{DEFAULT_BASE_URL}/config.yaml"
            s = requests.Session()
            s.trust_env = False
            r: Response = s.get(url, timeout=timeout, proxies={"http": None, "https": None})
            if getattr(r, 'status_code', 0) != 200:
                return ""
            text = r.text or ""
            m = re.search(r"BZY_BASE_URL:\s*['\"]([^'\"]+)['\"]" , text)
            if not m:
                return ""
            return (m.group(1) or "").strip()
        except Exception:
            return ""

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
                # 创建 session，禁用代理和 SSL 验证（对于国内站点）
                session = requests.Session()
                session.trust_env = False
                session.proxies = {"http": None, "https": None}
                
                # 添加必要的 headers，避免被阻止
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://bz.zhenggui.vip",
                    "Origin": "https://bz.zhenggui.vip"
                }
                
                # 尝试连接 ZBY 首页，禁用 SSL 验证避免证书问题
                try:
                    r: Response = session.get(
                        self.base_url, 
                        timeout=timeout, 
                        headers=headers,
                        verify=False  # 禁用 SSL 验证（国内站点常见问题）
                    )
                    return 200 <= getattr(r, 'status_code', 0) < 400
                except Exception as e:
                    # 备用方案：尝试连接 API 端点
                    try:
                        api_url = "https://login.bz.zhenggui.vip/bzy-api/org/std/search"
                        r: Response = session.get(
                            api_url,
                            timeout=timeout,
                            headers=headers,
                            verify=False
                        )
                        return 200 <= getattr(r, 'status_code', 0) < 400
                    except Exception:
                        return False
            if self.client is not None and hasattr(self.client, 'is_available'):
                return bool(self.client.is_available())
            return True
        except Exception:
            return False

    def search(self, keyword: str, **kwargs) -> List[Standard]:
        items = []
        
        # 搜索时禁用Playwright，快速失败策略
        old_allow_playwright = self.allow_playwright
        self.allow_playwright = False

        try:
            # 1. 优先尝试快速 HTTP JSON API（超时8秒，快速失败）
            try:
                http_items = self._http_search_api(keyword, **kwargs)
                if http_items:
                    return http_items
            except Exception:
                pass

            # 2. 最后尝试 HTML 爬取（纯HTTP，不用client和Playwright）
            try:
                html_items = self._http_search_html_fallback(keyword, **kwargs)
                if html_items:
                    return html_items
            except Exception:
                pass

            return items
        finally:
            # 恢复原来的设置
            self.allow_playwright = old_allow_playwright

    def _http_search_api(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
        """尝试 JSON API，如果结果为空则自动降级到 HTML 爬虫（对行业标准更友好）。"""
        items = []
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            session.trust_env = False  # 忽略系统代理
            # 搜索时允许 1 次重试，快速失败策略
            retries = Retry(total=1, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504))
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('https://', adapter)
            session.mount('http://', adapter)

            from .zby_http import search_via_api
            
            # 提取标准类型前缀（GB/T, QB/T 等）用于精确匹配
            prefix_match = re.match(r'([A-Z]+/?[A-Z]*)\s*', keyword.upper())
            expected_prefix = prefix_match.group(1).replace('/', '').replace(' ', '') if prefix_match else ''
            
            # 尝试多种关键词组合（渐进式）
            keywords_to_try = [keyword]
            # 1. 去掉斜杠和空格
            if '/' in keyword or ' ' in keyword:
                keywords_to_try.append(keyword.replace('/', '').replace(' ', ''))
            # 2. 去掉年份 (GB/T 1234-2024 -> GB/T 1234)
            if '-' in keyword:
                keywords_to_try.append(keyword.split('-')[0].strip())
            # 3. 仅保留数字 (GB/T 1234 -> 1234) - 仅当输入是GB标准时才使用
            # 避免 QB/T 1950 被搜索成纯数字 1950 导致误匹配 GB 1950
            if expected_prefix.startswith('GB') or expected_prefix.startswith('GJB'):
                num_match = re.search(r'(\d+)', keyword)
                if num_match:
                    keywords_to_try.append(num_match.group(1))
            
            print(f"[ZBY DEBUG] 尝试搜索关键词: {keywords_to_try}")
            
            # 去重并保持顺序
            keywords_to_try = list(dict.fromkeys(keywords_to_try))
            
            rows = []
            for kw in keywords_to_try:
                try:
                    print(f"[ZBY DEBUG] 正在尝试关键词: '{kw}'")
                    rows = search_via_api(kw, page=page, page_size=page_size, session=session, timeout=8)
                    print(f"[ZBY DEBUG] 关键词 '{kw}' 返回 {len(rows)} 条原始结果")
                    if rows:
                        # 过滤结果，确保标准类型和编号都匹配
                        filtered_rows = []
                        clean_keyword = re.sub(r'[^A-Z0-9]', '', keyword.upper())
                        print(f"[ZBY DEBUG] 清理后的关键词: '{clean_keyword}', 期望前缀: '{expected_prefix}'")
                        for r in rows:
                            r_no = re.sub(r'[^A-Z0-9]', '', (r.get('standardNumDeal') or '').upper())
                            # 提取结果的标准类型前缀
                            r_prefix_match = re.match(r'([A-Z]+)', r_no)
                            r_prefix = r_prefix_match.group(1) if r_prefix_match else ''
                            
                            # 严格匹配：标准类型必须一致
                            if expected_prefix and r_prefix:
                                if not r_prefix.startswith(expected_prefix):
                                    continue  # 标准类型不匹配，跳过
                            
                            # 标准号匹配（模糊匹配）
                            if clean_keyword in r_no or r_no in clean_keyword:
                                filtered_rows.append(r)
                        print(f"[ZBY DEBUG] 过滤后剩余 {len(filtered_rows)} 条结果")
                        if filtered_rows:
                            rows = filtered_rows
                            break  # 有匹配结果，不再尝试其他关键词
                except Exception:
                    continue  # 当前关键词失败，尝试下一个
            
            if rows:
                print(f"[ZBY DEBUG] 开始转换 {len(rows)} 条结果为Standard对象")
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
                        
                        # standardStatus 状态码映射
                        status_code = row.get('standardStatus')
                        status_map = {
                            '0': '即将实施',
                            '1': '现行',
                            '2': '废止',
                            '3': '有更新版本',
                            '4': '现行',  # 4也表示现行
                            0: '即将实施',
                            1: '现行',
                            2: '废止',
                            3: '有更新版本',
                            4: '现行',
                        }
                        status = status_map.get(status_code, str(status_code) if status_code is not None else '')
                        
                        # 修正状态逻辑：如果状态为"即将实施"但实施日期在过去，则修正为"现行"
                        impl = (row.get('standardUsefulDate') or row.get('standardUsefulTime') or row.get('standardUseDate') or row.get('implement') or '')
                        if status == '即将实施' and impl:
                            try:
                                from datetime import datetime
                                impl_date = str(impl)[:10]
                                if impl_date and impl_date < datetime.now().strftime('%Y-%m-%d'):
                                    status = '现行'
                            except:
                                pass
                        
                        # 提取替代标准信息
                        replace_std = ''
                        # 尝试从各种可能的字段中提取替代标准
                        for key in ['standardReplaceStandard', 'replaceStandard', 'standardReplace', 'replaceBy', 'replacedBy', 'instead', 'supersede']:
                            if key in row and row[key]:
                                replace_std = str(row[key]).strip()
                                break
                        
                        # 如果 API 没有返回替代标准，尝试从补充数据库查询
                        if not replace_std:
                            try:
                                from core.replacement_db import get_replacement_standard
                                replace_std = get_replacement_standard(std_no)
                            except:
                                pass
                        
                        meta = row
                        # Normalize publish/implement fields from possible API keys
                        pub = (row.get('standardPubTime') or row.get('publish') or '')
                        # impl 已在状态修正时提取，复用
                        items.append(Standard(std_no=std_no, name=name, publish_date=str(pub)[:10], implement_date=str(impl)[:10], status=status, replace_std=replace_std, has_pdf=has_pdf, source_meta=meta, sources=['ZBY']))
                    except Exception as e:
                        print(f"[ZBY DEBUG] 转换失败: {e}")
                        pass
                print(f"[ZBY DEBUG] 成功转换 {len(items)} 条Standard对象")
                return items[:int(page_size)]
            
            # API 返回空：尝试 HTML 爬虫（对行业标准如 QB/T 更友好）
            if not rows:
                html_items = self._http_search_html_fallback(keyword, page=page, page_size=page_size, **kwargs)
                if html_items:
                    return html_items
        except Exception:
            pass
        
        return items

    def _http_search_html_fallback(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
        """最后的 HTML 爬取降级方案，仅在其他所有源都失败时才使用。"""
        items = []
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            session.trust_env = False  # 忽略系统代理
            # HTML fallback 也允许 1 次重试，快速失败
            retries = Retry(total=1, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504))
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('https://', adapter)
            session.mount('http://', adapter)

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": str(self.base_url),
            }
            urls = [f"{self.base_url}/standardList", f"{self.base_url}/search", f"{self.base_url}/api/search"]
            resp_text = ""
            for u in urls:
                try:
                    # 显式禁用代理和 SSL 验证，超时8秒
                    r: Response = session.get(u, params={"searchText": keyword, "q": keyword}, headers=headers, timeout=8, proxies={"http": None, "https": None}, verify=False)
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
                items.append(Standard(std_no=std_no, name=name, publish_date='', implement_date='', status='', has_pdf=False, source_meta={"title": title}, sources=['ZBY']))
            return items[:int(page_size)]
        except Exception:
            pass
        
        return items

    def download(self, item: Standard, outdir: Path) -> DownloadResult:
        """按新协议下载标准文档
        
        Args:
            item: Standard 对象
            outdir: 输出目录
            
        Returns:
            DownloadResult 对象
        """
        logs = []
        try:
            result = self._download_impl(item, outdir, log_cb=lambda msg: logs.append(msg))
            if result:
                if isinstance(result, tuple):
                    file_path, logged = result
                    if file_path:
                        return DownloadResult.ok(Path(file_path) if not isinstance(file_path, Path) else file_path, logs)
                else:
                    if result:
                        return DownloadResult.ok(Path(result) if not isinstance(result, Path) else result, logs)
            
            error_msg = logs[-1] if logs else "ZBY: Unknown error"
            return DownloadResult.fail(error_msg, logs)
        except Exception as e:
            return DownloadResult.fail(f"ZBY download exception: {str(e)}", logs)
    
    def _download_impl(self, item: Standard, outdir: Path, log_cb=None):
        """[原实现] 下载标准。签名兼容两种调用方式：
        - download(item, outdir, log_cb=callable)  -> (Path|None, list[str])
        - download(item, outdir) -> Optional[Path]
        返回 (path, logs) 或直接 path/None（兼容旧实现）。
        """
        outdir.mkdir(parents=True, exist_ok=True)
        logs = []
        def emit(msg: str) -> None:
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

        # 若 meta 过于精简（仅有 title/has_pdf），尝试用 HTTP 搜索补充 standardId 等字段，便于后续下载
        try:
            meta = item.source_meta if isinstance(item.source_meta, dict) else {}
            has_id = any(k in meta for k in ("standardId", "id", "standardid"))
            if not has_id:
                kw = item.std_no or item.name
                if kw:
                    http_items = []
                    try:
                        http_items = self._http_search_api(kw, page_size=3)
                        if not http_items:
                            http_items = self._http_search_html_fallback(kw, page_size=3)
                    except Exception:
                        http_items = []
                    for hi in http_items:
                        m2 = hi.source_meta if isinstance(hi.source_meta, dict) else {}
                        if any(k in m2 for k in ("standardId", "id", "standardid")):
                            item = hi
                            break
        except Exception:
            pass

        # Prefer client implementation when available
        if self.client is not None and hasattr(self.client, 'download_standard'):
            try:
                path = self.client.download_standard(item.source_meta)
                p = Path(path) if path else None
                if p:
                    if callable(log_cb):
                        return p, logs
                    return p
                # client 存在但返回空：不要在这里终止，继续走 HTTP/Playwright 回退
                emit("ZBY: client.download_standard 返回空，尝试 HTTP 回退")
            except Exception as e:
                emit(f"ZBY: client.download_standard 异常: {e}")

        # 新增：若 meta 中有 standardId，尝试直接调用 standardDetail 页面获取文档
        try:
            meta = item.source_meta if isinstance(item.source_meta, dict) else {}
            std_id = meta.get("standardId") or meta.get("id") or meta.get("standardid")
            if std_id:
                emit(f"ZBY: 尝试通过 standardId ({std_id}) 直接获取文档...")
                http_try = self._download_via_standard_id(std_id, item, outdir, emit)
                if http_try is not None:
                    return http_try
        except Exception as e:
            emit(f"ZBY: standardId 直接获取失败: {e}")

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
                pw: ZBYSource = PWZBYSource(output_dir=outdir)
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

    def _download_via_standard_id(self, std_id: str, item: Standard, output_dir: Path, emit: callable):
        """通过 standardId 直接访问 standardDetail 页面，提取文档 URL 并下载。
        
        该方法尝试从 https://bz.zhenggui.vip/standardDetail?standardId={id} 页面
        提取文档下载链接或资源 UUID。
        """
        try:
            import requests
        except Exception:
            return None
        
        try:
            session = requests.Session()
            session.trust_env = False
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": self.base_url,
            })
            
            # 访问 standardDetail 页面
            detail_url = f"{self.base_url}/standardDetail?standardId={std_id}&docStatus=0"
            emit(f"ZBY: 访问详情页: standardId={std_id}")
            
            try:
                r = session.get(detail_url, timeout=10, proxies={"http": None, "https": None})
                if r.status_code != 200:
                    return None
                html = r.text or ""
            except Exception as e:
                emit(f"ZBY: 访问详情页失败: {e}")
                return None
            
            # 尝试从 HTML 中提取多种可能的 UUID/下载链接
            # 1) 直接匹配 immdoc/{uuid}/doc
            m = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', html)
            if m:
                uuid = m.group(1)
                emit(f"ZBY: 从详情页提取到 UUID: {uuid[:8]}...")
                cookies = [{'name': c.name, 'value': c.value} for c in session.cookies]
                return self._download_images(uuid, item.filename(), output_dir, cookies, emit)
            
            # 2) 尝试匹配任何 UUID 格式
            uuids = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', html)
            for uuid in uuids:
                emit(f"ZBY: 尝试提取到的 UUID: {uuid[:8]}...")
                cookies = [{'name': c.name, 'value': c.value} for c in session.cookies]
                res = self._download_images(uuid, item.filename(), output_dir, cookies, emit)
                if res:
                    return res
            
            # 3) 尝试从 HTML 中搜索 PDF 直链
            pdf_links = re.findall(r'(https?://[^\s"<>]+\.pdf)', html, re.IGNORECASE)
            for pdf_url in pdf_links:
                try:
                    emit(f"ZBY: 尝试直接下载 PDF 链接...")
                    r = session.get(pdf_url, timeout=20, stream=True, proxies={"http": None, "https": None})
                    if r.status_code == 200:
                        output_path = output_dir / item.filename()
                        output_dir.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            for chunk in r.iter_content(8192):
                                if chunk:
                                    f.write(chunk)
                        emit(f"ZBY: PDF 下载成功")
                        if callable(emit):
                            return output_path, []
                        return output_path
                except Exception:
                    continue
            
            emit(f"ZBY: 从详情页无法提取到文档资源")
            return None
            
        except Exception as e:
            emit(f"ZBY: standardId 下载异常: {e}")
            return None

    def _download_images(self, uuid: str, filename: str, output_dir: Path, cookies: list, emit: callable):
        """通过资源 UUID 下载分页图片并合成 PDF。

        该逻辑不依赖 Playwright，仅需 requests + img2pdf。
        """
        try:
            import requests
        except Exception:
            emit("ZBY: requests 不可用，无法下载")
            return None

        try:
            import img2pdf
        except Exception:
            emit("ZBY: 缺少 img2pdf，无法合成 PDF")
            return None

        try:
            uuid = (uuid or "").strip()
            if not uuid:
                return None
            emit(f"ZBY: 获取到UUID: {uuid[:8]}..., 开始下载")

            temp_dir = output_dir / "zby_temp"
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception:
                pass
            temp_dir.mkdir(parents=True, exist_ok=True)

            # cookies: list[{'name':..., 'value':...}] -> dict
            cookies_dict = {}
            try:
                for c in (cookies or []):
                    if isinstance(c, dict) and c.get('name'):
                        cookies_dict[str(c.get('name'))] = str(c.get('value') or '')
            except Exception:
                cookies_dict = {}

            session = requests.Session()
            session.trust_env = False

            imgs = []
            page_num = 1
            while True:
                try:
                    url = f"https://resource.zhenggui.vip/immdoc/{uuid}/doc/I/{page_num}"
                    r = session.get(url, cookies=cookies_dict, timeout=15, proxies={"http": None, "https": None})
                    if getattr(r, 'status_code', 0) != 200 or not getattr(r, 'content', b''):
                        break
                    img_path = temp_dir / f"{page_num:04d}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(r.content)
                    imgs.append(str(img_path))
                    if page_num % 5 == 0:
                        emit(f"ZBY: 已下载 {page_num} 页")
                    page_num += 1
                except Exception as e:
                    emit(f"ZBY: 第 {page_num} 页下载失败: {e}")
                    break

            if imgs:
                emit(f"ZBY: 共 {len(imgs)} 页，正在合成PDF...")
                output_path = output_dir / filename
                with open(output_path, "wb") as f:
                    f.write(img2pdf.convert(imgs))
                emit("ZBY: PDF生成成功")
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
                return output_path, []

            emit("ZBY: 未下载到任何页面")
            return None
        except Exception as e:
            emit(f"ZBY: _download_images 异常: {e}")
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

        # 0) 优先尝试通过官方 API（从 config.yaml 读取到的 BZY_BASE_URL）拿到预览/资源信息
        try:
            api_base = (self.api_base_url or "").strip()
            if api_base:
                std_id = meta.get('standardId') or meta.get('id')
                if std_id:
                    emit("ZBY: 尝试通过 API 获取预览资源...")
                    api_attempts = 0
                    api_status_counts = {}
                    api_sample = ""
                    api_candidates = [
                        "std/detail",
                        "std/getDetail",
                        "std/detailInfo",
                        "std/getStdDetail",
                        "std/preview",
                        "std/previewInfo",
                        "std/getPreview",
                        "std/getAliyunPreview",
                        "std/getDocInfo",
                        "std/resource",
                        "std/getResource",
                    ]
                    bodies = [
                        {"params": {"standardId": std_id}, "token": "", "userId": "", "orgId": "", "time": ""},
                        {"params": {"model": {"standardId": std_id}}, "token": "", "userId": "", "orgId": "", "time": ""},
                        {"standardId": std_id},
                        {"id": std_id},
                    ]

                    def _scan_for_uuid(obj) -> str:
                        try:
                            import json as _json
                            s = _json.dumps(obj, ensure_ascii=False)
                        except Exception:
                            s = str(obj)
                        # 1) 优先匹配 immdoc/{uuid}/doc
                        m = re.search(r"immdoc/([a-zA-Z0-9-]+)/doc", s)
                        if m:
                            return m.group(1)
                        # 2) 再匹配标准 UUID 形式
                        m = re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", s, re.I)
                        return m.group(0) if m else ""

                    headers: dict[str, str] = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Referer": DEFAULT_BASE_URL,
                        "Origin": DEFAULT_BASE_URL,
                        "Content-Type": "application/json;charset=UTF-8",
                    }
                    for ep in api_candidates:
                        api_url = api_base.rstrip('/') + '/' + ep.lstrip('/')
                        for body in bodies:
                            try:
                                api_attempts += 1
                                rr: Response = session.post(api_url, json=body, headers=headers, timeout=10, proxies={"http": None, "https": None})
                                status = int(getattr(rr, 'status_code', 0) or 0)
                                api_status_counts[status] = api_status_counts.get(status, 0) + 1
                                if status >= 400:
                                    if not api_sample:
                                        text = (getattr(rr, 'text', '') or '').strip().replace('\n', ' ')
                                        api_sample = f"HTTP {status} {ep} {text[:160]}".strip()
                                    continue
                                ct = (rr.headers.get('Content-Type') or '').lower()
                                if 'json' not in ct and not (rr.text and rr.text.strip().startswith('{')):
                                    continue
                                j = rr.json()
                                uuid = _scan_for_uuid(j)
                                if uuid:
                                    emit(f"ZBY: 从 API 获取到资源 UUID: {uuid[:8]}...")
                                    return self._download_images(uuid, item.filename(), output_dir, [], emit)
                                if not api_sample and isinstance(j, dict):
                                    code = j.get('code') if 'code' in j else j.get('status')
                                    msg = j.get('msg') if 'msg' in j else j.get('message')
                                    if code is not None or msg:
                                        api_sample = f"code={code} msg={str(msg)[:160]}".strip()
                            except Exception:
                                continue

                    if api_attempts:
                        try:
                            status_summary = '/'.join([f"{k}:{api_status_counts[k]}" for k in sorted(api_status_counts.keys())])
                        except Exception:
                            status_summary = str(api_status_counts)
                        sample_txt = f"，示例: {api_sample}" if api_sample else ""
                        emit(f"ZBY: API 未命中 UUID（base=[URL]，尝试{api_attempts}次，HTTP={status_summary}{sample_txt}）")
        except Exception:
            pass
        
        # 1. 尝试通过 standardId 直接访问详情页（SPA 可能只返回壳，但仍保留作为兜底）
        std_id = meta.get('standardId') or meta.get('id')
        if std_id:
            detail_urls = [
                f"{self.base_url}/standard/detail/{std_id}",
                f"{self.base_url}/#/standard/detail/{std_id}",
            ]
            for du in detail_urls:
                try:
                    emit(f"ZBY: 检查详情页...")
                    r: Response = session.get(du, timeout=8, proxies={"http": None, "https": None})
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
                            r: Response = requests.get(url, timeout=20, stream=True, proxies={"http": None, "https": None})
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
                        r: Response = session.get(u, params={"searchText": kw, "q": kw, "keyword": kw}, timeout=10, proxies={"http": None, "https": None})
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
                                rd: Response = session.get(detail_url, timeout=8, proxies={"http": None, "https": None})
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


