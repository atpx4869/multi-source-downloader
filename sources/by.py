# -*- coding: utf-8 -*-
"""
BY Source - 标院内网标准管理系统 (http://172.16.100.72:8080)
"""
import re
import requests
from pathlib import Path
from typing import List, Callable, Optional, Dict, Any

from core.models import Standard


# BY 内网系统配置
BASE = "http://172.16.100.72:8080"
LOGIN_URL = f"{BASE}/login.aspx"
DEPT_ID = "fc4186fba640402188b91e6bd0d491a6"  # 建材产品检测研究所
USERNAME = "leiming"  # 雷明
PASSWORD = "888888"
TIMEOUT = 10  # 网络请求超时秒
MAX_PAGES = 5  # 每次检索最多抓取的分页数，防止阻塞


def _extract_hidden(html: str, name: str) -> str:
    """提取 ASP.NET 隐藏字段值"""
    m = re.search(rf'name="{name}"[^>]+value="([^"]+)"', html)
    if not m:
        raise ValueError(f"{name} not found")
    return m.group(1)


def _login(session: requests.Session) -> bool:
    """登录标院内网系统"""
    try:
        # Step 1: GET login page
        r1 = session.get(LOGIN_URL, timeout=TIMEOUT)
        r1.raise_for_status()
        vs1 = _extract_hidden(r1.text, "__VIEWSTATE")
        ev1 = _extract_hidden(r1.text, "__EVENTVALIDATION")

        # Step 2: postback to load users for the department
        post_dept = {
            "__EVENTTARGET": "ddlDept",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": vs1,
            "__EVENTVALIDATION": ev1,
            "ddlDept": DEPT_ID,
        }
        r2 = session.post(LOGIN_URL, data=post_dept, timeout=TIMEOUT)
        r2.raise_for_status()
        vs2 = _extract_hidden(r2.text, "__VIEWSTATE")
        ev2 = _extract_hidden(r2.text, "__EVENTVALIDATION")

        # Step 3: submit credentials
        login_body = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": vs2,
            "__EVENTVALIDATION": ev2,
            "ddlDept": DEPT_ID,
            "ddlUserName": USERNAME,
            "txtLogidPwd": PASSWORD,
            "btnLogin": "登录",
        }
        r3 = session.post(LOGIN_URL, data=login_body, allow_redirects=False, timeout=TIMEOUT)
        if r3.status_code != 302 or "Location" not in r3.headers:
            return False

        # follow landing page to finalize session
        landing = r3.headers["Location"]
        if landing and not landing.lower().startswith("http"):
            landing = BASE + landing
        session.get(landing, timeout=TIMEOUT)
        return True
    except Exception:
        return False


def _search_by(session: requests.Session, keyword: str) -> List[Dict]:
    """检索标准，返回包含元数据和下载信息的字典列表"""
    def parse_page(html: str) -> List[Dict]:
        blocks = re.findall(r'<table class="mt20".*?rpStand_HidSIId_\d".*?</table>', html, flags=re.S)
        page_results = []
        for idx, block in enumerate(blocks, start=1):
            def grab(pattern, default=""):
                m = re.search(pattern, block, flags=re.S)
                return m.group(1).strip() if m else default

            std_no = grab(r'class=" c333 f16">\s*([^<]+)')
            std_name = grab(r'<p class="c333 mt5">\s*([^<]+)')
            status = grab(r"标准状态：<span class='[^']*'>([^<]+)")
            publish = grab(r'发布日期：([0-9-]+)')
            implement = grab(r'实施日期：([0-9-]+)')
            siid = grab(r'id="rpStand_HidSIId_\d" value="([^"]+)"')
            pdf_path = grab(r'id="rpStand_hdfB000_\d" value="([^"]+)"')

            page_results.append({
                "idx": idx,
                "std_no": std_no,
                "std_name": std_name,
                "status": status,
                "publish": publish,
                "implement": implement,
                "siid": siid,
                "pdf_path": pdf_path,
            })
        return page_results

    def parse_total_pages(html: str) -> int:
        m = re.search(r'当前页：<font[^>]*><b>\d+/(\d+)</b>', html)
        if m:
            return int(m.group(1))
        return 1

    url = f"{BASE}/Customer/StandSerarch/StandInfoList.aspx?A100={keyword}&A298="
    results: List[Dict] = []

    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        html = resp.text
        results.extend(parse_page(html))
        total_pages = parse_total_pages(html)
        pages_to_fetch = min(total_pages, MAX_PAGES)
        viewstate = _extract_hidden(html, "__VIEWSTATE")
        eventvalidation = _extract_hidden(html, "__EVENTVALIDATION")

        # 若有多页，模拟 __doPostBack(AspNetPager1, page)
        for page_idx in range(2, pages_to_fetch + 1):
            data = {
                "__EVENTTARGET": "AspNetPager1",
                "__EVENTARGUMENT": str(page_idx),
                "__VIEWSTATE": viewstate,
                "__EVENTVALIDATION": eventvalidation,
                "inputA100": keyword,
                "inputA298": "",
            }
            resp = session.post(url, data=data, timeout=TIMEOUT)
            resp.raise_for_status()
            html = resp.text
            results.extend(parse_page(html))
            viewstate = _extract_hidden(html, "__VIEWSTATE")
            eventvalidation = _extract_hidden(html, "__EVENTVALIDATION")
    except Exception:
        pass

    return results


def _download_standard(session: requests.Session, siid: str, outfile: Path) -> bool:
    """通过详情页下载标准 PDF"""
    try:
        detail_url = f"{BASE}/Manager/StandManager/StandDetail.aspx?SIId={siid}"
        detail_resp = session.get(detail_url, timeout=TIMEOUT)
        detail_resp.raise_for_status()
        pdf_path = _extract_hidden(detail_resp.text, "hidB000")
        pdf_path = pdf_path.lstrip("~")
        download_url = BASE + pdf_path if pdf_path.startswith("/") else f"{BASE}/{pdf_path}"

        with session.get(download_url, stream=True, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            with open(outfile, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return outfile.exists()
    except Exception:
        return False


class BYSource:
    """BY (标院内网) Data Source"""
    
    def __init__(self):
        self.name = "BY"
        self.priority = 2
        self.session = requests.Session()
        self.session.trust_env = False  # 忽略系统代理
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self._logged_in = False
        self._available = None  # None = 未检测, True/False = 检测结果
    
    def _ensure_login(self) -> bool:
        """确保已登录"""
        if self._logged_in:
            return True
        self._logged_in = _login(self.session)
        return self._logged_in
    
    def is_available(self) -> bool:
        """检测内网是否可访问"""
        if self._available is not None:
            return self._available
        try:
            resp = requests.head(BASE, timeout=3)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available
    
    def search(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
        """Search standards from BY internal system"""
        items = []
        
        # 检查内网是否可访问
        if not self.is_available():
            return items
        
        # 确保已登录
        if not self._ensure_login():
            return items
        
        try:
            results = _search_by(self.session, keyword)
            
            for r in results:
                std = Standard(
                    std_no=r.get("std_no", ""),
                    name=r.get("std_name", ""),
                    publish=r.get("publish", ""),
                    implement=r.get("implement", ""),
                    status=r.get("status", ""),
                    has_pdf=True,  # BY 源检索到的均有正文
                    source_meta=r,
                    sources=["BY"]
                )
                items.append(std)
        except Exception:
            pass
        
        return items
    
    def download(self, item: Standard, output_dir: Path, log_cb: Callable[[str], None] = None) -> tuple:
        """Download from BY source"""
        logs = []
        
        def emit(msg: str):
            logs.append(msg)
            if log_cb:
                log_cb(msg)
        
        # 检查内网是否可访问
        if not self.is_available():
            emit("BY: 内网不可访问")
            return None, logs
        
        # 确保已登录
        if not self._ensure_login():
            emit("BY: 登录失败")
            return None, logs
        
        r = item.source_meta or {}
        output_dir.mkdir(parents=True, exist_ok=True)
        outfile = output_dir / item.filename()
        
        # 优先使用直接 PDF 路径
        pdf_path = r.get("pdf_path")
        if pdf_path:
            emit(f"BY: 直接下载 {item.std_no}...")
            try:
                path = pdf_path.lstrip("~")
                url = BASE + path if path.startswith("/") else f"{BASE}/{path}"
                with self.session.get(url, stream=True, timeout=TIMEOUT) as resp:
                    resp.raise_for_status()
                    with outfile.open("wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                if outfile.exists():
                    emit(f"BY: 下载完成 {outfile.name}")
                    return outfile, logs
            except Exception as e:
                emit(f"BY: 直接下载失败 - {e}")
        
        # 备用方案：通过详情页下载
        siid = r.get("siid")
        if siid:
            emit(f"BY: 通过详情页下载 {item.std_no}...")
            if _download_standard(self.session, siid, outfile):
                emit(f"BY: 下载完成 {outfile.name}")
                return outfile, logs
            else:
                emit("BY: 详情页下载失败")
        
        emit("BY: 无可用下载路径")
        return None, logs

