# -*- coding: utf-8 -*-
"""
GBW download helper (requests-based) adapted from provided implementation.
Provides: clean_text, get_hcno(std_id), download_with_ocr(hcno, outfile, logger)
"""
import base64
import io
import re
import time
from pathlib import Path
from typing import List
import requests
from PIL import Image, ImageEnhance, ImageOps

SEARCH_URL = "https://std.samr.gov.cn/gb/search/gbQueryPage"
DETAIL_URL = "https://std.samr.gov.cn/gb/search/gbDetailed"
HEADERS = {"User-Agent": "Mozilla/5.0"}

OUTPUT_DIR = Path('.')
USE_CUSTOM_OCR = False
CUSTOM_OCR_URL = "https://ocr.524869.xyz:5555/captcha/base64"
USE_BAIDU_OCR = True
USE_DDDDOCR = False
USE_PPLL_OCR = True

BAIDU_OCR_AK = "64hxUIMiToJXovvmVFNCOoUQ"
BAIDU_OCR_SK = "ps6RGIKaBprXgKRC2LYmZJK8sMLMV4GE"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE = "http://c.gb688.cn"
CAPTCHA_URL = f"{BASE}/bzgk/gb/gc"
VERIFY_URL = f"{BASE}/bzgk/gb/verifyCode"
VIEW_URL = f"{BASE}/bzgk/gb/viewGb"
_baidu_token_cache = {"token": "", "expires_at": 0}
_ppll_ocr_instance = None


def prewarm_ocr():
    """预热 OCR 模型，避免第一次下载时加载过慢"""
    global _ppll_ocr_instance
    if not USE_PPLL_OCR:
        return
    
    # 提前检查 NumPy 版本。如果 >= 2.0，则跳过 PPLL OCR，防止 onnxruntime 导致 SystemError 崩溃
    try:
        import numpy as np
        if int(np.__version__.split('.')[0]) >= 2:
            # print("NumPy version >= 2.0 detected, skipping PPLL OCR to avoid crash.")
            return
    except Exception:
        pass

    # 提前检查 onnxruntime 是否可用
    try:
        import onnxruntime
    except (Exception, SystemError, ImportError):
        return

    try:
        from ppllocr import OCR
        if _ppll_ocr_instance is None:
            _ppll_ocr_instance = OCR()
            # 预热推理一次，让 ONNX Runtime 加载库
            dummy = Image.new('RGB', (100, 40), color=(255, 255, 255))
            buf = io.BytesIO()
            dummy.save(buf, format='JPEG')
            _ppll_ocr_instance.classification(buf.getvalue())
    except (Exception, SystemError, ImportError):
        pass


def _normalize_text(text: str) -> str:
    return "".join(ch for ch in (text or "").strip().upper() if ch.isalnum())


def clean_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"</?sacinfo>", "", value)


def get_baidu_token() -> str:
    if not USE_BAIDU_OCR:
        return ""
    if not (BAIDU_OCR_AK and BAIDU_OCR_SK):
        return ""
    now = time.time()
    if _baidu_token_cache["token"] and now < _baidu_token_cache["expires_at"] - 60:
        return _baidu_token_cache["token"]
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": BAIDU_OCR_AK,
        "client_secret": BAIDU_OCR_SK,
    }
    try:
        resp = requests.post(url, params=params, timeout=5, proxies={"http": None, "https": None})
        data = resp.json()
        token = data.get("access_token", "")
        expires_in = data.get("expires_in", 0)
        if token:
            _baidu_token_cache["token"] = token
            _baidu_token_cache["expires_at"] = now + int(expires_in)
            return token
    except Exception:
        return ""
    return ""


def _baidu_call(img_b64: str, token: str, endpoint: str) -> str:
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/{endpoint}?access_token={token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = requests.post(
            url,
            data={"image": img_b64, "language_type": "ENG"},
            headers=headers,
            timeout=5,
            proxies={"http": None, "https": None}
        )
        data = resp.json()
        words = data.get("words_result", [])
        for w in words:
            text = _normalize_text(w.get("words", ""))
            if text:
                return text
    except Exception:
        return ""
    return ""


def custom_ocr(img_bytes: bytes) -> str:
    if not USE_CUSTOM_OCR:
        return ""
    img_b64 = base64.b64encode(img_bytes).decode()
    tries = [
        ("json", {"image": img_b64}),
        ("json", {"base64": img_b64}),
        ("data", {"image": img_b64}),
        ("data", {"base64": img_b64}),
    ]
    for mode, payload in tries:
        try:
            if mode == "json":
                resp = requests.post(CUSTOM_OCR_URL, json=payload, timeout=5, verify=False, proxies={"http": None, "https": None})
            else:
                resp = requests.post(CUSTOM_OCR_URL, data=payload, timeout=5, verify=False, proxies={"http": None, "https": None})
            data = resp.json()
            for key in ("data", "text", "result", "code", "message"):
                if key in data and isinstance(data[key], str):
                    text = _normalize_text(data[key])
                    if text and 3 <= len(text) <= 4:
                        return text[:4]
            if isinstance(data, dict) and data.get("code") == 0 and "message" in data:
                text = _normalize_text(str(data["message"]))
                if text and 3 <= len(text) <= 4:
                    return text[:4]
        except Exception:
            continue
    return ""


def _enhance_image_bytes(img_bytes: bytes) -> List[bytes]:
    variants = [img_bytes]
    try:
        with Image.open(io.BytesIO(img_bytes)) as im:
            # 1. 灰度 + 锐化 + 对比度
            gray = ImageOps.grayscale(im)
            w, h = gray.size
            scale = 2 if max(w, h) < 200 else 1.5
            if scale != 1:
                gray = gray.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)
            
            v1 = ImageOps.autocontrast(gray)
            v1 = ImageEnhance.Contrast(v1).enhance(1.8)
            v1 = ImageEnhance.Sharpness(v1).enhance(1.5)
            buf1 = io.BytesIO()
            v1.save(buf1, format="PNG")
            variants.append(buf1.getvalue())
            
            # 2. 二值化处理 (针对某些背景复杂的验证码)
            v2 = gray.point(lambda x: 0 if x < 128 else 255, '1')
            buf2 = io.BytesIO()
            v2.save(buf2, format="PNG")
            variants.append(buf2.getvalue())
    except Exception:
        pass
    uniq = []
    seen = set()
    for b in variants:
        if b and b not in seen:
            uniq.append(b)
            seen.add(b)
    return uniq


def ppll_ocr(img_bytes: bytes) -> str:
    global _ppll_ocr_instance
    if not USE_PPLL_OCR:
        return ""
    
    # 提前检查 NumPy 版本
    try:
        import numpy as np
        if int(np.__version__.split('.')[0]) >= 2:
            return ""
    except Exception:
        pass
    
    # 提前检查 onnxruntime 是否可用
    try:
        import onnxruntime
    except (Exception, SystemError, ImportError):
        return ""

    try:
        from ppllocr import OCR  # type: ignore
    except (Exception, SystemError, ImportError):
        return ""
    try:
        if _ppll_ocr_instance is None:
            _ppll_ocr_instance = OCR()
        ocr = _ppll_ocr_instance
        
        # 1. 先尝试原始图片，使用标准置信度 (最快)
        text = _normalize_text(ocr.classification(img_bytes, conf=0.2, iou=0.45))
        if text and len(text) == 4:
            return text
            
        # 2. 如果失败，尝试增强后的图片
        candidates = _enhance_image_bytes(img_bytes)
        for buf in candidates:
            if buf == img_bytes: continue 
            text = _normalize_text(ocr.classification(buf, conf=0.15, iou=0.45))
            if text and len(text) == 4:
                return text
    except Exception:
        return ""
    return ""


def dddd_ocr(img_bytes: bytes) -> str:
    if not USE_DDDDOCR:
        return ""
    try:
        import ddddocr  # noqa

        ocr = ddddocr.DdddOcr(show_ad=False)
        raw = ocr.classification(img_bytes)
        text = _normalize_text(raw)
        return text[:4] if text else ""
    except BaseException:
        return ""


def baidu_ocr(img_bytes: bytes) -> str:
    if not USE_BAIDU_OCR:
        return ""
    token = get_baidu_token()
    if not token:
        return ""
    img_b64 = base64.b64encode(img_bytes).decode()
    text = _baidu_call(img_b64, token, "accurate_basic")
    if text and 3 <= len(text) <= 4:
        return text[:4]
    return ""


def search(keyword: str, page: int = 1, page_size: int = 20):
    params = {
        "searchText": keyword,
        "ics": "",
        "state": "",
        "ISSUE_DATE": "",
        "pageNumber": page,
        "pageSize": page_size,
    }
    url = f"{SEARCH_URL}?" + requests.utils.requote_uri("&".join(f"{k}={v}" for k, v in params.items()))
    # 显式禁用代理
    resp = requests.get(url, headers=HEADERS, timeout=15, proxies={"http": None, "https": None})
    data = resp.json()
    return data.get("rows", []), data.get("total", 0), url


def format_row(idx: int, item: dict) -> str:
    std_code = clean_text(item.get("C_STD_CODE", ""))
    name = clean_text(item.get("C_C_NAME", ""))
    issue_date = item.get("ISSUE_DATE", "")
    imple_date = item.get("ACT_DATE") or item.get("IMPLE_DATE") or ""
    state = item.get("STATE") or item.get("G_STATE") or ""
    return f"{idx}. {std_code or '-'} | {name or '-'} | 发布: {issue_date or '-'} | 实施: {imple_date or '-'} | 状态: {state or '-'}"


def get_hcno(std_id: str) -> str:
    t_start = time.time()
    detail_url = f"{DETAIL_URL}?id={std_id}"
    # 显式禁用代理
    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=15, proxies={"http": None, "https": None})
        patterns = [
            r"hcno=([A-Fa-f0-9]{32})",
            r'"hcno"\?"?:\\?"([A-Fa-f0-9]{32})',
        ]
        for p in patterns:
            m = re.search(p, resp.text, flags=re.IGNORECASE)
            if m:
                # print(f"DEBUG: get_hcno took {time.time()-t_start:.2f}s")
                return m.group(1)
    except Exception:
        pass
    return ""


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name)
    return cleaned.strip() or "download"


def fetch_captcha(session: requests.Session, show_url: str, out_file: Path) -> bytes:
    ts = int(time.time() * 1000)
    # 恢复为 http，但显式禁用代理
    candidates = [f"{CAPTCHA_URL}?_{ts}"]
    headers = {"User-Agent": UA, "Referer": show_url}
    last_err = None
    for url in candidates:
        try:
            # 显式禁用代理
            resp = session.get(url, headers=headers, timeout=15, proxies={"http": None, "https": None})
            resp.raise_for_status()
            out_file.write_bytes(resp.content)
            return resp.content
        except Exception as exc:
            last_err = exc
            continue
    raise RuntimeError(f"获取验证码失败，最后错误: {last_err}")


def verify_code(session: requests.Session, code: str, show_url: str) -> str:
    headers = {
        "User-Agent": UA,
        "Referer": show_url,
        "Origin": BASE,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    # 显式禁用代理
    resp = session.post(VERIFY_URL, data={"verifyCode": code}, headers=headers, timeout=10, proxies={"http": None, "https": None})
    resp.raise_for_status()
    return resp.text.strip()


def download_file(session: requests.Session, hcno: str, show_url: str, out_path: Path, gbw_type: str = None) -> None:
    url = f"{VIEW_URL}?hcno={hcno}"
    if gbw_type:
        url += f"&type={gbw_type}"
    headers = {"User-Agent": UA, "Referer": show_url}
    # 增加 chunk_size 到 128KB 提高下载速度
    with session.get(url, headers=headers, stream=True, timeout=60, proxies={"http": None, "https": None}) as r:
        r.raise_for_status()
        # 检查内容类型，如果是 HTML 说明下载失败（可能是验证码失效或权限问题）
        content_type = r.headers.get("Content-Type", "").lower()
        if "html" in content_type:
            raise RuntimeError("下载返回了 HTML 页面，可能是权限不足或验证码失效")
        
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=131072):
                if chunk:
                    f.write(chunk)


def download_with_ocr(hcno: str, outfile: Path, max_attempts: int = 8, logger=None, session: requests.Session = None) -> bool:
    def log(msg: str):
        if not msg:
            return
        # 涉及保密，脱敏处理：隐藏所有网址
        msg = re.sub(r'https?://[^\s<>"]+', '[URL]', msg)
        
        if logger:
            try:
                logger(msg)
                return
            except Exception:
                pass
        print(msg)

    if session is None:
        session = requests.Session()
        session.trust_env = False  # 忽略系统代理
    
    # 预热 OCR
    t_pre = time.time()
    prewarm_ocr()
    log(f"OCR 预热耗时: {time.time()-t_pre:.2f}s")
    
    # 尝试两种类型：download (正式版) 和 online (预览版)
    # 对于“即将实施”的标准，通常只有 online 可用
    for gbw_type in ['download', 'online']:
        show_url = f"{BASE}/bzgk/gb/showGb?type={gbw_type}&hcno={hcno}"
        log(f"GBW: 尝试类型 {gbw_type}...")
        
        # 访问展示页以获取初始 Cookie
        t_show = time.time()
        try:
            resp = session.get(show_url, headers={"User-Agent": UA, "Referer": "https://openstd.samr.gov.cn/"}, timeout=15, proxies={"http": None, "https": None})
            resp.raise_for_status()
            
            # 检查页面内容，看是否真的可用
            if "未找到" in resp.text or "不存在" in resp.text:
                log(f"GBW: 类型 {gbw_type} 不可用 (页面提示未找到或不存在)")
                continue
            
            if "无预览权限" in resp.text or "没有权限" in resp.text:
                log(f"GBW: 类型 {gbw_type} 不可用 (无预览权限)")
                continue
            
            log(f"访问展示页耗时: {time.time()-t_show:.2f}s")
        except Exception as e:
            log(f"访问展示页失败: {e}")
            continue

        # 如果同时启用，总次数增加以保证百度有尝试机会
        total_limit = max_attempts
        if USE_PPLL_OCR and USE_BAIDU_OCR:
            total_limit = max_attempts + 4 # 默认 8 + 4 = 12 次

        success = False
        for attempt in range(1, total_limit + 1):
            t_start = time.time()
            try:
                ts = int(time.time() * 1000)
                url = f"{CAPTCHA_URL}?_{ts}"
                headers = {"User-Agent": UA, "Referer": show_url}
                t_cap = time.time()
                resp = session.get(url, headers=headers, timeout=10, proxies={"http": None, "https": None})
                resp.raise_for_status()
                img_bytes = resp.content
                # 如果返回的是 HTML 而不是图片，说明可能被拦截或类型不对
                if b"<html" in img_bytes[:100].lower():
                    log(f"[Attempt {attempt}] 获取验证码返回了 HTML，可能类型 {gbw_type} 不支持下载")
                    break
                log(f"[Attempt {attempt}] 获取验证码耗时: {time.time()-t_cap:.2f}s")
            except Exception as e:
                log(f"[Attempt {attempt}] 获取验证码失败: {e}")
                continue
            
            code = ""
            if USE_PPLL_OCR and attempt <= 8:
                code = ppll_ocr(img_bytes)
            
            if not code and USE_BAIDU_OCR:
                if not USE_PPLL_OCR or attempt > 8:
                    code = baidu_ocr(img_bytes)
                
            if not code or len(code) != 4:
                log(f"[Attempt {attempt}] OCR 识别无效: {code}")
                continue
                
            log(f"[Attempt {attempt}] OCR: {code}")
            try:
                resp_text = verify_code(session, code, show_url)
                log(f"[Attempt {attempt}] 校验返回: {resp_text}")
            except Exception as exc:
                log(f"[Attempt {attempt}] 校验请求失败: {exc}")
                continue

            norm = resp_text.lower()
            if norm in ("true", "success", "ok", "1") or "成功" in resp_text:
                try:
                    download_file(session, hcno, show_url, outfile, gbw_type=gbw_type)
                    log(f"下载完成 ({gbw_type}): {outfile.name}")
                    return True
                except Exception as exc:
                    log(f"下载失败 ({gbw_type}): {exc}")
                    # 如果下载失败，可能是这个类型确实不支持下载，尝试下一个类型
                    break
        
        if success:
            return True
            
    log("所有类型尝试完毕，均未成功。")
    return False
