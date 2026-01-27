# -*- coding: utf-8 -*-
"""
GBW Source - 国家标准信息公共服务平台 (std.samr.gov.cn)
"""
import re
import requests
import urllib3
from pathlib import Path
from typing import List, Callable

# 抑制 urllib3 的 SSL 验证警告（我们故意禁用 SSL 验证以兼容国内网站）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.models import Standard
from .gbw_download import get_hcno, download_with_ocr, sanitize_filename, prewarm_ocr
from .http_search import call_api, find_rows
from .base import BaseSource, DownloadResult
from .registry import registry

# 导入超时配置
try:
    from core.timeout_config import get_timeout
except ImportError:
    def get_timeout(source: str, operation: str) -> int:
        return 10

# Pre-compile regex patterns
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')
_STD_CODE_SLASH_RE = re.compile(r'([A-Z])\s*/\s*([A-Z])')


@registry.register
class GBWSource(BaseSource):
    """GBW (国标委) Data Source"""

    # 源标识和元数据
    name = "GBW"

    # 使用统一的超时配置
    SEARCH_TIMEOUT = get_timeout("GBW", "search")
    DOWNLOAD_TIMEOUT = get_timeout("GBW", "download")
    DETAIL_TIMEOUT = get_timeout("GBW", "detail")
    PDF_CHECK_TIMEOUT = get_timeout("GBW", "pdf_check")
    source_id = "gbw"
    source_name = "国家标准信息公共服务平台"
    priority = 1
    
    # 类变量：所有实例共享的PDF检测缓存（避免重复访问详情页）
    _pdf_check_cache = {}  # {item_id: has_pdf}
    
    def __init__(self):
        self.name = "GBW"
        self.base_url = "https://std.samr.gov.cn"
        self.session = requests.Session()
        self.session.trust_env = False  # 忽略系统代理设置
        self.session.proxies = {"http": None, "https": None} # 显式禁用代理
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    
    def _clean_text(self, text: str) -> str:
        """Clean XML tags from text, preserving inner content"""
        if not text:
            return ""
        # Remove tags but keep inner text
        cleaned = _HTML_TAG_RE.sub('', text)
        return cleaned.strip()
    
    def _parse_std_code(self, raw_code: str) -> str:
        """Parse standard code like '<sacinfo>GB</sacinfo>/<sacinfo>T</sacinfo> <sacinfo>46541-2025</sacinfo>' -> 'GB/T 46541-2025'"""
        if not raw_code:
            return ""
        
        # 直接移除所有 HTML 标签并清理空白
        cleaned = _HTML_TAG_RE.sub('', raw_code)
        # 将多个空格合并为一个，并处理常见的格式问题
        cleaned = _WHITESPACE_RE.sub(' ', cleaned).strip()
        
        # 针对 GB/T 这种中间可能有斜杠但被拆分的情况进行修正
        # 例如 "GB / T" -> "GB/T"
        cleaned = _STD_CODE_SLASH_RE.sub(r'\1/\2', cleaned)
        
        return cleaned
    
    def _check_pdf_available(self, item_id: str, hcno: str = "") -> bool:
        """
        三层PDF可用性检测（分级判定模式）
        
        第一层：缓存检查 - 避免重复访问详情页
        第二层：启发式判定 - 根据不同按钮类型分级判定
        第三层：保守降级 - 无法确定时返回False
        
        按钮类型判定（可靠性递减）：
        1. ck_btn + xz_btn  → True（新版标准，可信度最高 ✅✅✅）
        2. openpdf          → True（中等可信度 ⚠️⚠️）
        3. data-value HCNO  → True（中等可信度 ⚠️⚠️）
        4. 版权限制提示     → False（黑名单 ❌）
        5. 都没有           → False（保守判定 ⚠️）
        """
        if not item_id:
            return False
        
        # 第一层：缓存检查（类变量，所有实例共享）
        cache_key = hcno if hcno else item_id
        if cache_key in GBWSource._pdf_check_cache:
            return GBWSource._pdf_check_cache[cache_key]
        
        try:
            # 如果没有传入HCNO，先从旧版详情页获取（但用较短的超时）
            if not hcno:
                try:
                    hcno = self._get_hcno(item_id)
                except Exception:
                    hcno = None  # 获取HCNO失败就跳过
            
            # 构建URL优先级列表（优先使用HCNO访问新版API）
            url_attempts = []
            if hcno:
                # 优先：新版API（更准确，包含版权信息）
                url_attempts.append((f"https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno={hcno}", "newGbInfo"))
            # 备选：旧版详情页
            url_attempts.extend([
                (f"https://std.samr.gov.cn/gb/search/gbDetailed?id={item_id}", "gbDetailed"),
                (f"https://openstd.samr.gov.cn/gb/search/gbDetailed?id={item_id}", "gbDetailed"),
            ])
            
            text = None
            for url, url_type in url_attempts:
                try:
                    # 搜索时用较短的超时
                    resp = self.session.get(url, timeout=self.PDF_CHECK_TIMEOUT, proxies={"http": None, "https": None})
                    if resp.status_code == 200:
                        resp.encoding = 'utf-8'
                        text = resp.text
                        break
                except Exception:
                    continue
            
            if not text:
                GBWSource._pdf_check_cache[cache_key] = False
                return False
            
            # 第二层：启发式判定
            
            # 黑名单检查：版权限制提示（最高优先级，一旦发现直接返回False）
            no_read_keywords = [
                "本系统暂不提供在线阅读",
                "版权保护问题",
                "涉及版权保护",
                "暂不提供",
                "无预览权限",
                "不提供下载",
                "购买正式标准出版物",  # 新增：用户提供的页面中的关键词
                "联系中国标准出版社",    # 新增：明确要求购买
                "需要购买",
                "已下架",
                "您所查询的标准系统尚未收录",
                "将在发布后20个工作日内公开",
                "陆续完成公开",
                "标准废止"
            ]
            
            for keyword in no_read_keywords:
                if keyword in text:
                    GBWSource._pdf_check_cache[cache_key] = False
                    return False
                
                # 白名单检查：按可靠性递减
                
                # 等级1：ck_btn + xz_btn（新版GBW，可信度最高）
                # 这类按钮表示可以在线预览和下载，属于新版标准
                if 'ck_btn' in text or '在线预览' in text:
                    if 'xz_btn' in text or '下载标准' in text:
                        GBWSource._pdf_check_cache[cache_key] = True
                        return True
                
                # 等级2：openpdf（旧版GBW，但相对可信）
                # 这表示可以通过PDF查看器打开文档
                if 'openpdf' in text or 'pdfPreview' in text or 'pdfpreview' in text:
                    GBWSource._pdf_check_cache[cache_key] = True
                    return True
                
                # 等级3：data-value HCNO（有HCNO通常意味着可以访问）
                if 'data-value=' in text:
                    import re
                    hcno_match = re.search(r'data-value=["\']([A-F0-9]{32})["\']', text, re.IGNORECASE)
                    if hcno_match:
                        GBWSource._pdf_check_cache[cache_key] = True
                        return True
                
                # 等级4：只有在线预览按钮（不一定能下载）
                if 'ck_btn' in text or '在线预览' in text:
                    # 只有预览没有下载时，保守返回False
                    GBWSource._pdf_check_cache[cache_key] = False
                    return False
                
                # 都没找到：返回False（保守判定）
                GBWSource._pdf_check_cache[cache_key] = False
                return False
            
        except Exception:
            # 访问异常时，保守起见返回False
            GBWSource._pdf_check_cache[cache_key] = False
            return False
    
    def search(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
        """Search standards from GBW API"""
        items = []
        
        # 优化：只尝试原始关键词，快速失败，不重试
        rows = []
        try:
            search_url = f"{self.base_url}/gb/search/gbQueryPage"
            params = {
                "searchText": keyword,
                "pageNumber": page,
                "pageSize": page_size
            }
            # 搜索时允许 1 次重试（快速失败 + 容错）
            j = call_api(self.session, 'GET', search_url, params=params, timeout=self.SEARCH_TIMEOUT, retries=1, verify_ssl=False)
            rows = find_rows(j)
        except Exception:
            pass
        
        # 如果原始关键词没结果，尝试去除空格/斜杠的变种（但也不重试）
        if not rows:
            try:
                if '/' in keyword or ' ' in keyword:
                    kw_clean = keyword.replace('/', '').replace(' ', '')
                    params['searchText'] = kw_clean
                    j = call_api(self.session, 'GET', search_url, params=params, timeout=8, retries=1, verify_ssl=False)
                    rows = find_rows(j)
            except Exception:
                pass
                
        try:
            for row in rows:
                    # Parse standard code properly
                    std_code = self._parse_std_code(row.get("C_STD_CODE", ""))
                    std_name = self._clean_text(row.get("C_C_NAME", ""))
                    
                    # Check if PDF is available (现行/即将实施 状态，且缓存有记录)
                    status = row.get("STATE", "")
                    status_ok = "现行" in status or "即将实施" in status
                    
                    # 获取item_id和hcno（用于缓存查询）
                    item_id = row.get("id", "")
                    hcno = row.get("HCNO", "")
                    cache_key = hcno if hcno else item_id

                    # 搜索中的保守判定逻辑（修复乐观假设问题）：
                    # 1. 如果缓存已有结果，使用缓存值
                    # 2. 如果状态不是"现行"或"即将实施"，标记为无文本
                    # 3. 如果状态OK但缓存未命中，进行实时检查（避免误报）
                    if cache_key in GBWSource._pdf_check_cache:
                        has_pdf = GBWSource._pdf_check_cache[cache_key]
                    elif not status_ok:
                        has_pdf = False
                    else:
                        # 状态OK但缓存未命中 -> 进行实时检查（避免乐观假设）
                        # 这会增加搜索时间，但能避免误报
                        has_pdf = self._check_pdf_available(item_id, hcno)

                    
                    std = Standard(
                        std_no=std_code,
                        name=std_name,
                        publish_date=row.get("ISSUE_DATE", ""),
                        implement_date=row.get("ACT_DATE", ""),
                        status=status,
                        has_pdf=has_pdf,
                        source_meta={
                            "id": item_id,
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
        import time
        for retry in range(3):
            try:
                # 尝试两个可能的详情页域名
                for base in ["https://std.samr.gov.cn", "https://openstd.samr.gov.cn"]:
                    detail_url = f"{base}/gb/search/gbDetailed?id={item_id}"
                    # 显式禁用代理，使用配置的详情页超时
                    resp = self.session.get(detail_url, timeout=self.DETAIL_TIMEOUT, proxies={"http": None, "https": None}, verify=False)
                    if resp.status_code != 200:
                        continue
                    
                    # 尝试多种匹配模式
                    # 1. URL 参数模式
                    match = re.search(r'hcno=([A-F0-9]{32})', resp.text)
                    if match:
                        return match.group(1)
                    
                    # 2. data-value 属性模式 (常见于按钮)
                    match = re.search(r'data-value=["\']([A-F0-9]{32})["\']', resp.text)
                    if match:
                        return match.group(1)
                    
                    # 3. JavaScript 变量模式
                    match = re.search(r'hcno\s*[:=]\s*["\']([A-F0-9]{32})["\']', resp.text)
                    if match:
                        return match.group(1)
                    
                    # 4. 针对 openstd 的新版详情页
                    match = re.search(r'newGbInfo\?hcno=([A-F0-9]{32})', resp.text)
                    if match:
                        return match.group(1)
                    
                    # 5. 针对某些页面可能包含跳转链接
                    match = re.search(r'window\.location\.href\s*=\s*["\'].*?hcno=([A-F0-9]{32})', resp.text)
                    if match:
                        return match.group(1)

                # 如果还是没找到，尝试直接在 openstd 搜索该 ID
                search_url = f"https://openstd.samr.gov.cn/bzgk/gb/search/gbQueryPage?searchText={item_id}"
                resp = self.session.get(search_url, timeout=self.DETAIL_TIMEOUT, proxies={"http": None, "https": None}, verify=False)
                match = re.search(r'hcno=([A-F0-9]{32})', resp.text)
                if match:
                    return match.group(1)
                    
            except Exception as e:
                if retry < 2:
                    time.sleep(1)
                else:
                    print(f"GBW _get_hcno error: {e}")
        return ""
    
    def download(self, item: Standard, outdir: Path) -> DownloadResult:
        """按新协议下载标准文档
        
        Args:
            item: Standard 对象
            outdir: 输出目录
            
        Returns:
            DownloadResult 对象
        """
        # 适配旧实现
        logs = []
        try:
            result = self._download_impl(item, outdir, log_cb=lambda msg: logs.append(msg))
            if result:
                if isinstance(result, tuple):
                    file_path, logged = result
                    if file_path:
                        return DownloadResult.ok(Path(file_path), logs)
                else:
                    # 兼容直接返回路径的情况
                    if result:
                        return DownloadResult.ok(Path(result), logs)
            
            error_msg = logs[-1] if logs else "Unknown error"
            return DownloadResult.fail(error_msg, logs)
        except Exception as e:
            return DownloadResult.fail(f"GBW download exception: {str(e)}", logs)
    
    def _download_impl(self, item: Standard, output_dir: Path, log_cb: Callable[[str], None] = None) -> tuple:
        """[原实现] Download PDF from GBW - requires browser automation for captcha"""
        logs = []

        def emit(msg: str):
            logs.append(msg)
            if log_cb:
                log_cb(msg)

        emit("GBW: 开始下载...")
        # 尝试使用 requests 风格的下载实现（无需浏览器），优先执行
        try:
            meta = item.source_meta
            item_id = meta.get("id", "") if isinstance(meta, dict) else ""
            # 优先从 meta 获取 hcno，如果没有则通过详情页获取
            hcno = meta.get("hcno") if isinstance(meta, dict) else None
            if not hcno or len(hcno) != 32:
                hcno = self._get_hcno(item_id)
            
            if hcno:
                out_dir = output_dir or Path("downloads")
                out_dir.mkdir(parents=True, exist_ok=True)
                try:
                    filename = item.filename()
                except Exception:
                    filename = sanitize_filename(item.name or item.std_no) + '.pdf'
                out_path = out_dir / filename
                # 传入 session 以复用连接
                ok = download_with_ocr(hcno, out_path, logger=emit, session=self.session)
                if ok:
                    emit(f"GBW: requests 下载成功 -> {out_path}")
                    return out_path, logs
                emit("GBW: requests 下载未成功，回退到浏览器自动化方式")
        except Exception as e:
            emit(f"GBW: requests 下载尝试出错: {e}")

        emit("GBW: 尝试使用浏览器自动化处理验证码...")

        # Check Playwright availability
        try:
            from playwright.sync_api import sync_playwright
            playwright_available = True
        except Exception as e:
            emit(f"GBW: Playwright 导入失败: {e}")
            playwright_available = False

        # Check OCR availability
        ocr = None
        try:
            from ppllocr import OCR
            try:
                ocr = OCR()
                # 验证OCR对象是否有效（有callable的classification方法）
                if not callable(getattr(ocr, 'classification', None)):
                    ocr = None
            except Exception as e:
                emit(f"GBW: OCR 模型加载失败: {e}")
                ocr = None
        except Exception:
            emit("GBW: 未找到 ppllocr OCR 库，无法自动识别验证码")
            ocr = None

        if not playwright_available:
            emit("GBW: Playwright 未安装或导入失败，无法自动处理验证码")
            return None, logs

        try:
            meta = item.source_meta
            item_id = meta.get("id", "") if isinstance(meta, dict) else ""
            if not item_id:
                emit("GBW: 未找到标准ID")
                return None, logs

            detail_url = f"{self.base_url}/gb/search/gbDetailed?id={item_id}"

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()

                emit(f"GBW: 打开详情页面 {detail_url}")
                page.goto(detail_url)
                page.wait_for_load_state("networkidle")

                # 尝试定位验证码图片与输入框
                captcha_img = None
                try:
                    # 常见选择器：img[src*="captcha"], img#captcha
                    captcha_img = page.query_selector('img[src*="captcha"]')
                except Exception:
                    captcha_img = None

                if not captcha_img:
                    # 备用查找：查找包含 '验证码' 的标签附近的 img
                    try:
                        elems = page.query_selector_all("img")
                        for el in elems:
                            alt = el.get_attribute('alt') or ''
                            src = el.get_attribute('src') or ''
                            if '验证码' in alt or 'captcha' in src.lower() or 'validate' in src.lower():
                                captcha_img = el
                                break
                    except Exception:
                        captcha_img = None

                if not captcha_img:
                    emit("GBW: 页面上未检测到验证码图片，尝试直接抓取 HCNO")
                    # 如果没有验证码，尝试通过请求获取 hcno
                    cookies = {c['name']: c['value'] for c in context.cookies()}
                    browser.close()
                    # 使用已有 session cookies 获取页面内容
                    resp = self.session.get(detail_url, cookies=cookies, timeout=10)
                    match = re.search(r'hcno=([A-F0-9]{32})', resp.text)
                    if match:
                        hcno = match.group(1)
                        emit(f"GBW: 找到 HCNO: {hcno[:8]}...")
                        return None, logs
                    emit("GBW: 未能获取 HCNO")
                    return None, logs

                # 获取图片 URL
                src = captcha_img.get_attribute('src')
                if src.startswith('data:'):
                    # base64 image
                    import base64
                    header, b64 = src.split(',', 1)
                    img_bytes = base64.b64decode(b64)
                else:
                    # 通过 playwright 的 request 获取图片以携带相同上下文（cookie）
                    try:
                        # 获取绝对URL
                        img_url = src if src.startswith('http') else (self.base_url + src)
                        # 转换 context cookies 到 requests cookies
                        cookies = {c['name']: c['value'] for c in context.cookies()}
                        r = self.session.get(img_url, cookies=cookies, timeout=10)
                        img_bytes = r.content
                    except Exception as e:
                        emit(f"GBW: 下载验证码图片失败: {e}")
                        browser.close()
                        return None, logs

                emit("GBW: 已获取验证码图片，开始 OCR 识别")
                if ocr and callable(getattr(ocr, 'classification', None)):
                    try:
                        code = ocr.classification(img_bytes)
                        code = code.strip()
                        emit(f"GBW: OCR 识别结果: {code}")
                    except Exception as e:
                        emit(f"GBW: OCR 识别失败: {e}")
                        code = ''
                else:
                    code = ''

                if not code:
                    emit("GBW: 无法识别验证码，请在浏览器中手动处理")
                    browser.close()
                    return None, logs

                # 填写验证码并提交（尝试常见输入框和按钮）
                try:
                    # 尝试找到输入框
                    input_el = page.query_selector('input[type="text"]') or page.query_selector('input')
                    if input_el:
                        input_el.fill(code)
                    # 找到提交按钮
                    btn = page.query_selector('button[type="submit"]') or page.query_selector('button')
                    if btn:
                        btn.click()
                    else:
                        # 触发回车
                        input_el.press('Enter')
                except Exception:
                    pass

                # 等待页面刷新并获取 cookies
                try:
                    page.wait_for_load_state('networkidle', timeout=5000)
                except Exception:
                    pass

                cookies = {c['name']: c['value'] for c in context.cookies()}
                browser.close()

                # 使用 requests 获取页面，查找 hcno
                resp = self.session.get(detail_url, cookies=cookies, timeout=10)
                match = re.search(r'hcno=([A-F0-9]{32})', resp.text)
                if match:
                    hcno = match.group(1)
                    emit(f"GBW: 验证成功，获取 HCNO: {hcno[:8]}...")
                    # 尝试通过 HCNO 下载 PDF
                    emit("GBW: 尝试通过 HCNO 下载 PDF...")
                    # 首先在页面中搜索可能的 PDF 链接
                    pdf_link_match = re.search(r'href=["\']([^"\']+\.pdf)["\']', resp.text, re.IGNORECASE)
                    if pdf_link_match:
                        pdf_url = pdf_link_match.group(1)
                        if not pdf_url.startswith('http'):
                            pdf_url = self.base_url + pdf_url
                        emit(f"GBW: 在页面中找到 PDF 链接: {pdf_url}")
                        try:
                            r = self.session.get(pdf_url, cookies=cookies, timeout=15)
                            if r.status_code == 200 and r.headers.get('content-type','').lower().startswith('application/pdf') or (r.content[:4] == b'%PDF'):
                                out_path = output_dir / item.filename()
                                with open(out_path, 'wb') as f:
                                    f.write(r.content)
                                emit(f"GBW: PDF 下载成功 -> {out_path}")
                                return out_path, logs
                        except Exception as e:
                            emit(f"GBW: 下载 PDF 失败: {e}")

                    # 如果页面中无链接，尝试若干常见的下载端点
                    candidates = [
                        f"{self.base_url}/servlet/Download?HCNO={hcno}",
                        f"{self.base_url}/hcno/download?hcno={hcno}",
                        f"{self.base_url}/attachment/download?hcno={hcno}",
                        f"{self.base_url}/download?hcno={hcno}",
                        f"{self.base_url}/gb/search/gcDown?hcno={hcno}",
                    ]

                    for url in candidates:
                        try:
                            emit(f"GBW: 尝试 {url}")
                            r = self.session.get(url, cookies=cookies, timeout=15)
                            if r.status_code == 200:
                                ct = r.headers.get('content-type','').lower()
                                if 'application/pdf' in ct or r.content[:4] == b'%PDF':
                                    out_path = output_dir / item.filename()
                                    with open(out_path, 'wb') as f:
                                        f.write(r.content)
                                    emit(f"GBW: PDF 下载成功 -> {out_path}")
                                    return out_path, logs
                        except Exception as e:
                            emit(f"GBW: 请求 {url} 失败: {e}")

                    emit("GBW: 未能通过已知端点直接下载 PDF，可能需要额外逆向页面请求流程")
                    return None, logs
                else:
                    emit("GBW: 验证后仍未找到 HCNO，可能识别错误或页面流程不同")
                    return None, logs

        except Exception as e:
            emit(f"GBW: CAPTCHA 处理失败: {e}")
            return None, logs

    def is_available(self, timeout: int = 6) -> bool:
        """检查 GBW 服务是否可访问（用于快速健康检测）"""
        try:
            test_url = f"{self.base_url}/gb/search/gbQueryPage?searchText=test&pageNum=1&pageSize=1"
            resp = self.session.get(test_url, timeout=timeout, verify=False)  # 禁用 SSL 验证
            return 200 <= getattr(resp, 'status_code', 0) < 400
        except Exception:
            return False
