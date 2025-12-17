# -*- coding: utf-8 -*-
"""
ZBY adapter - prefer user-provided implementation if available, else fall back to Playwright backup.
This module exposes `ZBYSource` class compatible with AggregatedDownloader.
"""
from pathlib import Path
from typing import List
import re

DEFAULT_BASE_URL = "https://bz.zhenggui.vip"

from core.models import Standard, natural_key, sanitize_filename


try:
    # Try to use user's StandardDownloader-based implementation (if available in environment)
    from standard_downloader import StandardDownloader  # type: ignore

    class ZBYSource:
        name = "ZBY"
        priority = 3

        def __init__(self, output_dir: Path | str = "downloads"):
            # Ensure debug artifacts are written to the repository downloads folder
            # even when running from a PyInstaller temporary extraction directory.
            od = Path(output_dir)
            # If output_dir is relative (likely 'downloads'), map it to repo downloads
            try:
                if (isinstance(output_dir, str) and output_dir == "downloads") or (isinstance(output_dir, Path) and not Path(output_dir).is_absolute()):
                    # repository root is two levels up from this file (sources/)
                    repo_root = Path(__file__).resolve().parents[1]
                    od = repo_root / "downloads"
            except Exception:
                od = Path(output_dir)
                try:
                    # repository root is two levels up from this file (sources/)
                    repo_root = Path(__file__).resolve().parents[1]
                    od = repo_root / "downloads"
                except Exception:
                    od = Path(output_dir)
            self.output_dir = Path(od)
            self.client = StandardDownloader(output_dir=self.output_dir)
            # determine base_url from client if available
            self.base_url = getattr(self.client, 'base_url', DEFAULT_BASE_URL)

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
                except Exception as e:
                    data = None
                    # write debug trace for client.search failure
                    try:
                        out = self.output_dir / f"debug_zby_client_search_{int(__import__('time').time())}.txt"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with open(out, 'w', encoding='utf-8') as fh:
                            fh.write(f"client.search exception:\n{repr(e)}\n")
                    except Exception:
                        pass

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

                # If client returned no rows, try fallback strategies in order:
                # 1) HTTP-based scraping of the public search page (no Playwright)
                # 2) Playwright-based implementation (if available)
                if not items:
                    # 1) HTTP fallback
                    try:
                        http_items = self._http_search(keyword, **kwargs)
                        if http_items:
                            items = http_items
                    except Exception as e:
                        # log HTTP fallback exception
                        try:
                            out = self.output_dir / f"debug_zby_http_{int(__import__('time').time())}.txt"
                            out.parent.mkdir(parents=True, exist_ok=True)
                            with open(out, 'w', encoding='utf-8') as fh:
                                fh.write(f"http fallback exception:\n{repr(e)}\n")
                        except Exception:
                            pass

                if not items:
                    # 2) Playwright fallback
                    try:
                        from .zby_playwright import ZBYSource as PWZBYSource  # type: ignore
                        pw = PWZBYSource(self.output_dir)
                        pw_items = pw.search(keyword, **kwargs)
                        if pw_items:
                            items = pw_items
                    except Exception as e:
                        try:
                            out = self.output_dir / f"debug_zby_playwright_{int(__import__('time').time())}.txt"
                            out.parent.mkdir(parents=True, exist_ok=True)
                            with open(out, 'w', encoding='utf-8') as fh:
                                fh.write(f"playwright fallback exception:\n{repr(e)}\n")
                        except Exception:
                            pass

                items.sort(key=lambda x: natural_key(x.std_no))
                return items

        def _http_search(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
            """Lightweight requests-based scraper for ZBY search page.

            This avoids Playwright and parses the public HTML search results.
            It is intentionally tolerant and returns a list of `Standard`.
            """
            items: List[Standard] = []
            try:
                import requests
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": self.base_url,
                }
                # try two possible search endpoints used by site
                urls = [f"{self.base_url}/standardList?searchText={keyword}", f"{self.base_url}/#/search?keyWords={keyword}"]
                resp_text = ""
                for u in urls:
                    try:
                        r = requests.get(u, headers=headers, timeout=8)
                        if r.status_code == 200 and r.text:
                            resp_text = r.text
                            break
                    except Exception as e:
                        # write short debug for request failures
                        try:
                            out = self.output_dir / f"debug_zby_request_{int(__import__('time').time())}.txt"
                            out.parent.mkdir(parents=True, exist_ok=True)
                            with open(out, 'w', encoding='utf-8') as fh:
                                fh.write(f"request to {u} failed: {repr(e)}\n")
                        except Exception:
                            pass
                        continue

                if not resp_text:
                    # save an empty capture for debugging
                    try:
                        out_html = self.output_dir / f"debug_zby_empty_{int(__import__('time').time())}.html"
                        out_html.parent.mkdir(parents=True, exist_ok=True)
                        with open(out_html, 'w', encoding='utf-8') as fh:
                            fh.write('')
                    except Exception:
                        pass
                    return items

                # find blocks that look like result items (class stdList)
                blocks = re.findall(r'<div[^>]+class=["\']?[^"\'>]*stdList[^"\'>]*["\']?[^>]*>(.*?)</div>\s*</div>', resp_text, re.S)
                if not blocks:
                    # fallback: search for <h4> titles directly
                    blocks = re.findall(r'(<h4.*?>.*?</h4>.*?(?:<div class="bottom".*?>.*?</div>)?)', resp_text, re.S)

                for blk in blocks:
                    # extract title text
                    h4 = re.search(r'<h4.*?>(.*?)</h4>', blk, re.S)
                    title = re.sub(r'<.*?>', '', h4.group(1)).strip() if h4 else ''
                    if not title:
                        continue
                    # parse std_no and name similar to playwright extractor
                    std_no = ''
                    name = title
                    m = re.match(r'^([A-Z]+(?:/[A-Z]+)?\s*[\d\.\-]+(?:-\d{4})?)\s+(.*)$', title)
                    if m:
                        std_no = m.group(1).strip()
                        name = m.group(2).strip()
                    else:
                        m2 = re.match(r'^([A-Z]+(?:/[A-Z]+)?)\s+([\d\.\-]+(?:-\d{4})?)\s+(.*)$', title)
                        if m2:
                            std_no = f"{m2.group(1)} {m2.group(2)}"
                            name = m2.group(3).strip()

                    # status and dates
                    status = ''
                    bottom = ''
                    btm = re.search(r'<div[^>]+class=["\']?bottom["\']?[^>]*>(.*?)</div>', blk, re.S)
                    if btm:
                        bottom = re.sub(r'<.*?>', '', btm.group(1)).replace('\n', ' ').strip()
                    pub_date = ''
                    imp_date = ''
                    if '发布日期：' in bottom:
                        parts = bottom.split('发布日期：')
                        if len(parts) > 1:
                            date_parts = parts[1].split('实施日期：')
                            pub_date = date_parts[0].strip().replace('— —', '').strip()
                            if len(date_parts) > 1:
                                imp_date = date_parts[1].strip().replace('— —', '').strip()

                    # detect pdf icon
                    has_pdf = False
                    pdf_match = re.search(r'<img[^>]+class=["\']?pdf["\']?[^>]+src=["\']([^"\']+)["\']', blk)
                    if pdf_match and 'listPdf_ing.png' in pdf_match.group(1):
                        has_pdf = True

                    items.append(Standard(
                        std_no=std_no,
                        name=name,
                        publish=pub_date,
                        implement=imp_date,
                        status=status,
                        has_pdf=has_pdf,
                        source_meta={"title": title, "raw": blk},
                        sources=["ZBY"],
                    ))

                # limit to page_size
                # also save a sample HTML for inspection
                try:
                    sample = self.output_dir / f"debug_zby_sample_{int(__import__('time').time())}.html"
                    sample.parent.mkdir(parents=True, exist_ok=True)
                    with open(sample, 'w', encoding='utf-8') as fh:
                        fh.write(resp_text)
                except Exception:
                    pass
                return items[:int(page_size)]
            except Exception as e:
                try:
                    out = self.output_dir / f"debug_zby_exc_{int(__import__('time').time())}.txt"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with open(out, 'w', encoding='utf-8') as fh:
                        fh.write(f"http_search exception:\n{repr(e)}\n")
                except Exception:
                    pass
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


