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
USE_CUSTOM_OCR = True
CUSTOM_OCR_URL = "https://ocr.524869.xyz:5555/captcha/base64"
USE_BAIDU_OCR = True
USE_DDDDOCR = False
USE_PPLL_OCR = True

BAIDU_OCR_AK = "64hxUIMiToJXovvmVFNCOoUQ"
BAIDU_OCR_SK = "ps6RGIKaBprXgKRC2LYmZJK8sMLMV4GE"

UA = "Mozilla/5.0"
BASE = "http://c.gb688.cn"
CAPTCHA_URL = f"{BASE}/bzgk/gb/gc"
VERIFY_URL = f"{BASE}/bzgk/gb/verifyCode"
VIEW_URL = f"{BASE}/bzgk/gb/viewGb"
_baidu_token_cache = {"token": "", "expires_at": 0}


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
            gray = ImageOps.grayscale(im)
            w, h = gray.size
            scale = 2 if max(w, h) < 200 else 1.5
            if scale != 1:
                gray = gray.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)
            gray = ImageOps.autocontrast(gray)
            gray = ImageEnhance.Contrast(gray).enhance(1.8)
            gray = ImageEnhance.Sharpness(gray).enhance(1.2)
            buf = io.BytesIO()
            gray.save(buf, format="PNG")
            variants.append(buf.getvalue())
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
    if not USE_PPLL_OCR:
        return ""
    try:
        from ppllocr import OCR  # type: ignore
    except Exception:
        return ""
    try:
        ocr = OCR()
        candidates = _enhance_image_bytes(img_bytes)
        for buf in candidates:
            for conf in (0.25, 0.18, 0.12):
                text = _normalize_text(ocr.classification(buf, conf=conf, iou=0.45))
                if text and 3 <= len(text) <= 4:
                    return text[:4]
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
    code = ppll_ocr(img_bytes)
    if code and len(code) == 4:
        return code
    code = custom_ocr(img_bytes)
    if code and len(code) == 4:
        return code
    token = get_baidu_token()
    if not token:
        return ""
    img_b64 = base64.b64encode(img_bytes).decode()
    text = _baidu_call(img_b64, token, "accurate_basic")
    if text and 3 <= len(text) <= 4:
        return text[:4]
    code = dddd_ocr(img_bytes)
    if code and len(code) == 4:
        return code
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
    resp = requests.get(url, headers=HEADERS, timeout=15)
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
    detail_url = f"{DETAIL_URL}?id={std_id}"
    resp = requests.get(detail_url, headers=HEADERS, timeout=15)
    patterns = [
        r"hcno=([A-Fa-f0-9]{32})",
        r'"hcno"\?"?:\\?"([A-Fa-f0-9]{32})',
    ]
    for p in patterns:
        m = re.search(p, resp.text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
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


def download_file(session: requests.Session, hcno: str, show_url: str, out_path: Path) -> None:
    url = f"{VIEW_URL}?hcno={hcno}"
    headers = {"User-Agent": UA, "Referer": show_url}
    with session.get(url, headers=headers, stream=True, timeout=60, proxies={"http": None, "https": None}) as r:
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def download_with_ocr(hcno: str, outfile: Path, max_attempts: int = 8, logger=None) -> bool:
    def log(msg: str):
        if logger:
            try:
                logger(msg)
                return
            except Exception:
                pass
        print(msg)

    show_url = f"{BASE}/bzgk/gb/showGb?type=download&hcno={hcno}"
    session = requests.Session()
    session.trust_env = False  # 忽略系统代理
    session.get(show_url, headers={"User-Agent": UA, "Referer": "https://openstd.samr.gov.cn/"}, timeout=15, proxies={"http": None, "https": None})
    captcha_path = Path("captcha.jpg")

    for attempt in range(1, max_attempts + 1):
        try:
            img_bytes = fetch_captcha(session, show_url, captcha_path)
        except Exception as e:
            log(f"[Attempt {attempt}] 获取验证码失败: {e}")
            continue
        code = baidu_ocr(img_bytes) if USE_BAIDU_OCR else ""
        log(f"[Attempt {attempt}] OCR: {code}")
        if not code or len(code) != 4:
            continue
        try:
            resp_text = verify_code(session, code, show_url)
            log(f"[Attempt {attempt}] 校验返回: {resp_text}")
        except Exception as exc:
            log(f"[Attempt {attempt}] 校验请求失败: {exc}")
            continue

        norm = resp_text.lower()
        if norm in ("true", "success", "ok", "1") or "成功" in resp_text:
            try:
                download_file(session, hcno, show_url, outfile)
                log(f"下载完成: {outfile.resolve()}")
                return True
            except Exception as exc:
                log(f"下载失败: {exc}")
                return False
    log("多次尝试仍未通过验证码。")
    return False
