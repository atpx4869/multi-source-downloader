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
_OCR_PREWARMED = False


def prewarm_ocr():
    """预热 OCR 模型，避免第一次下载时加载过慢"""
    global _ppll_ocr_instance
    global _OCR_PREWARMED
    if _OCR_PREWARMED:
        return
    if not USE_PPLL_OCR:
        _OCR_PREWARMED = True
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
    finally:
        _OCR_PREWARMED = True


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
        if text:
            return text[:4] if len(text) >= 4 else ""
            
        # 2. 如果失败，尝试增强后的图片
        candidates = _enhance_image_bytes(img_bytes)
        for buf in candidates:
            if buf == img_bytes: continue 
            text = _normalize_text(ocr.classification(buf, conf=0.15, iou=0.45))
            if text:
                return text[:4] if len(text) >= 4 else ""
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


def download_with_ocr(
    hcno: str,
    outfile: Path,
    max_attempts: int = 8,
    logger=None,
    session: requests.Session = None,
    *,
    verbose: bool = False,
) -> bool:
    def _emit(msg: str):
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

    def log(msg: str):
        """始终输出的重要日志（精简模式也会显示）。"""
        _emit(msg)

    def vlog(msg: str):
        """仅在 verbose=True 时输出的细节日志。"""
        if verbose:
            _emit(msg)

    if session is None:
        session = requests.Session()
        session.trust_env = False  # 忽略系统代理
    
    # 预热 OCR（精简模式下不刷预热耗时；verbose 时保留）
    t_pre = time.time()
    was_prewarmed = _OCR_PREWARMED
    prewarm_ocr()
    if verbose and (not was_prewarmed):
        vlog(f"OCR 预热耗时: {time.time()-t_pre:.2f}s")
    
    # 尝试两种类型：download (正式版) 和 online (预览版)
    # 对于“即将实施”的标准，通常只有 online 可用
    for gbw_type in ['download', 'online']:
        show_url = f"{BASE}/bzgk/gb/showGb?type={gbw_type}&hcno={hcno}"
        vlog(f"GBW: 尝试类型 {gbw_type}...")
        
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
            
            vlog(f"访问展示页耗时: {time.time()-t_show:.2f}s")
        except Exception as e:
            log(f"访问展示页失败: {e}")
            continue

        # 如果同时启用，总次数增加以保证百度有尝试机会
        total_limit = max_attempts
        if USE_PPLL_OCR and USE_BAIDU_OCR:
            total_limit = max_attempts + 4 # 默认 8 + 4 = 12 次

        # 统计与诊断：用于判断是 OCR 准确率低还是流程/会话问题
        stats = {
            "attempts": 0,
            "captcha_html": 0,
            "ocr_empty": 0,
            "ocr_non4": 0,
            "ocr_4": 0,
            "verify_error": 0,
            "verify_success": 0,
            "verify_exc": 0,
            "methods": {"PPLL": 0, "BAIDU": 0},
        }
        ppll_empty_streak = 0
        baidu_early_used = 0
        for attempt in range(1, total_limit + 1):
            stats["attempts"] += 1
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
                    log(f"GBW: 获取验证码返回了 HTML，可能类型 {gbw_type} 不支持下载")
                    stats["captcha_html"] += 1
                    break
                vlog(f"[Attempt {attempt}] 获取验证码耗时: {time.time()-t_cap:.2f}s")
            except Exception as e:
                vlog(f"[Attempt {attempt}] 获取验证码失败: {e}")
                continue

            # 同一张验证码上，按顺序尝试多种 OCR（减少“重复取验证码 + 日志刷屏”，提高成功概率）
            ocr_candidates = []  # List[Tuple[str, str]] -> (method, code)

            # 1) 优先本地 OCR（前 8 次优先走本地，避免全程走百度导致延迟）
            if USE_PPLL_OCR and attempt <= 8:
                c = ppll_ocr(img_bytes)
                ocr_candidates.append(("PPLL", c))
                if not c:
                    ppll_empty_streak += 1
                else:
                    ppll_empty_streak = 0

            # 2) 百度 OCR：
            #    - 本地 OCR 连续为空时尽早穿插
            #    - 或者在第 9+ 次（原策略）
            #    - 注意：这里是“候选”，只有需要时才会真的走校验
            if USE_BAIDU_OCR:
                if (not USE_PPLL_OCR) or (attempt > 8):
                    ocr_candidates.append(("BAIDU", None))
                elif ppll_empty_streak >= 3 and baidu_early_used < 2:
                    ocr_candidates.append(("BAIDU", None))
                    baidu_early_used += 1

            # 逐个方法尝试；若 PPLL 产出 4 位但校验 error，也会尝试 BAIDU（同一张图）
            tried_methods = set()
            had_verify_error = False
            for method, code in ocr_candidates:
                if method in tried_methods:
                    continue
                tried_methods.add(method)
                if code is None:
                    # 延迟执行：只有走到这里才真正调用百度
                    if method == "BAIDU":
                        code = baidu_ocr(img_bytes)

                # 容错：OCR 偶尔会多出字符，先截断到 4 位再校验（错了服务器会返回 error）
                if code and len(code) > 4:
                    code = code[:4]

                if not code:
                    stats["ocr_empty"] += 1
                    vlog(f"[Attempt {attempt}] OCR({method}) 无输出")
                    continue
                if len(code) != 4:
                    stats["ocr_non4"] += 1
                    vlog(f"[Attempt {attempt}] OCR({method}) 非4位: {code}")
                    continue

                stats["ocr_4"] += 1
                stats["methods"][method] = stats["methods"].get(method, 0) + 1
                vlog(f"[Attempt {attempt}] OCR({method}): {code}")

                try:
                    resp_text = verify_code(session, code, show_url)
                    vlog(f"[Attempt {attempt}] 校验返回: {resp_text}")
                except Exception as exc:
                    stats["verify_exc"] += 1
                    vlog(f"[Attempt {attempt}] 校验请求失败: {exc}")
                    continue

                norm = resp_text.lower()
                if norm in ("true", "success", "ok", "1") or "成功" in resp_text:
                    stats["verify_success"] += 1
                    log(f"GBW: 验证码识别成功")
                    try:
                        download_file(session, hcno, show_url, outfile, gbw_type=gbw_type)
                        log(f"下载完成 ({gbw_type}): {outfile.name}")
                        vlog(
                            f"GBW OCR统计({gbw_type}): 尝试={stats['attempts']} 4位输出={stats['ocr_4']} 校验error={stats['verify_error']} 成功={stats['verify_success']} | "
                            f"PPLL={stats['methods'].get('PPLL',0)} BAIDU={stats['methods'].get('BAIDU',0)}"
                        )
                        return True
                    except Exception as exc:
                        log(f"下载失败 ({gbw_type}): {exc}")
                        # 如果下载失败，可能是这个类型确实不支持下载，尝试下一个类型
                        break
                else:
                    stats["verify_error"] += 1
                    had_verify_error = True

                    # 如果本地 OCR 给了 4 位但校验失败，并且还没试过百度，则补一次百度（同一张图）
                    if method == "PPLL" and USE_BAIDU_OCR and "BAIDU" not in tried_methods:
                        continue

            # 日志节流：如果这一轮有校验失败，不再额外刷太多行
            if verbose and had_verify_error and (attempt % 5 == 0):
                vlog(f"[Attempt {attempt}] 连续校验失败累计: {stats['verify_error']}")

        # 失败时输出一次汇总，帮助判断“识别率低”还是“流程问题”（成功路径不刷屏）
        if stats.get("verify_success", 0) == 0:
            log(
                f"GBW OCR统计({gbw_type}): 尝试={stats['attempts']} HTML验证码={stats['captcha_html']} 空输出={stats['ocr_empty']} 非4位={stats['ocr_non4']} 4位输出={stats['ocr_4']} "
                f"校验error={stats['verify_error']} 校验异常={stats['verify_exc']} 成功={stats['verify_success']} | "
                f"PPLL={stats['methods'].get('PPLL',0)} BAIDU={stats['methods'].get('BAIDU',0)}"
            )
            
    log("所有类型尝试完毕，均未成功。")
    return False
