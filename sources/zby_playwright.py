# -*- coding: utf-8 -*-
"""
ZBY Source - Playwright-based implementation
"""
import os
import re
import time
import shutil
import requests
import img2pdf
from pathlib import Path
from typing import List, Callable, Optional, Union

from core.models import Standard


class ZBYSource:
	"""ZBY (智标云) Data Source - requires playwright for full functionality"""
    
	def __init__(self, output_dir: Optional[Path] = None):
		self.name = "ZBY"
		self.priority = 3
		self.output_dir = output_dir or Path("downloads")
		self.base_url = "https://bz.zhenggui.vip"
		self.session = requests.Session()
		self.session.headers.update({
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
			"Referer": "https://bz.zhenggui.vip/"
		})
		self._playwright_available = False
		try:
			from playwright.sync_api import sync_playwright
			self._playwright_available = True
		except ImportError:
			pass

	def is_available(self, timeout: int = 6) -> bool:
		"""快速检测 ZBY 服务是否可达（用于健康检查）。"""
		try:
			if not getattr(self, 'base_url', None):
				return False
			r = self.session.get(self.base_url, timeout=timeout)
			return 200 <= getattr(r, 'status_code', 0) < 400
		except Exception:
			return False

	def search(self, keyword: str, page: int = 1, page_size: int = 20, **kwargs) -> List[Standard]:
		items = []
		if not self._playwright_available:
			return items
		try:
			from playwright.sync_api import sync_playwright
			with sync_playwright() as p:
				browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
				context = browser.new_context()
				page_obj = context.new_page()
				page_obj.goto(self.base_url, timeout=45000)
				try:
					page_obj.wait_for_load_state("networkidle", timeout=30000)
				except:
					pass
				time.sleep(1)
				search_input = page_obj.query_selector("input.ant-input")
				if not search_input:
					search_input = page_obj.query_selector("input[placeholder*='搜索']")
				if not search_input:
					search_input = page_obj.query_selector("input")
				if search_input:
					search_input.fill(keyword)
					search_input.press("Enter")
				else:
					page_obj.goto(f"{self.base_url}/#/search?keyWords={keyword}", timeout=30000)
				# wait longer for list to appear
				try:
					page_obj.wait_for_selector(".stdList", timeout=30000)
				except:
					# try a fallback short sleep
					time.sleep(2)
				time.sleep(1)
				pages_needed = (page_size + 9) // 10
				current_page_num = 1
				while len(items) < page_size:
					elements = page_obj.query_selector_all(".stdList")
					for el in elements:
						if len(items) >= page_size:
							break
						item = self._extract_item_from_element(el)
						if item and not any(i.std_no == item.std_no for i in items):
							items.append(item)
					if len(items) >= page_size or current_page_num >= pages_needed:
						break
					next_btn = page_obj.query_selector(".ant-pagination-next:not(.ant-pagination-disabled)")
					if not next_btn:
						break
					next_btn.click()
					current_page_num += 1
					try:
						page_obj.wait_for_selector(".ant-spin-spinning", state="hidden", timeout=3000)
					except:
						time.sleep(1)
					time.sleep(0.5)
				browser.close()
		except Exception as e:
			print(f"ZBY search error: {e}")
		return items

	def _extract_item_from_element(self, el) -> Optional[Standard]:
		try:
			title_el = el.query_selector("h4")
			title = title_el.inner_text().replace("\n", " ").strip() if title_el else ""
			if not title:
				return None
			std_no = ""
			name = title
			match = re.match(r'^([A-Z]+(?:/[A-Z]+)?\s*[\d\.\-]+(?:-\d{4})?)\s+(.*)$', title)
			if match:
				std_no = match.group(1).strip()
				name = match.group(2).strip()
			else:
				code_match = re.match(r'^([A-Z]+(?:/[A-Z]+)?)\s+([\d\.\-]+(?:-\d{4})?)\s+(.*)$', title)
				if code_match:
					std_no = f"{code_match.group(1)} {code_match.group(2)}"
					name = code_match.group(3)
			status_el = el.query_selector(".ant-tag")
			status = status_el.inner_text().strip() if status_el else ""
			bottom_el = el.query_selector(".bottom")
			bottom = bottom_el.inner_text().replace("\n", " ") if bottom_el else ""
			pub_date = ""
			imp_date = ""
			if "发布日期：" in bottom:
				parts = bottom.split("发布日期：")
				if len(parts) > 1:
					date_parts = parts[1].split("实施日期：")
					pub_date = date_parts[0].strip().replace("— —", "").strip()
					if len(date_parts) > 1:
						imp_date = date_parts[1].strip().replace("— —", "").strip()
			pdf_icon = el.query_selector("img.pdf")
			src = pdf_icon.get_attribute("src") if pdf_icon else ""
			has_pdf = "listPdf_ing.png" in src
			return Standard(
				std_no=std_no,
				name=name,
				publish=pub_date,
				implement=imp_date,
				status=status,
				has_pdf=has_pdf,
				source_meta={"title": title, "has_pdf": has_pdf},
				sources=["ZBY"]
			)
		except Exception:
			return None

	def download(self, item: Standard, output_dir: Path, log_cb: Callable[[str], None] = None) -> tuple:
		logs = []
		def emit(msg: str):
			logs.append(msg)
			if log_cb:
				log_cb(msg)
		if not self._playwright_available:
			emit("ZBY: Playwright 未安装，无法下载")
			return None, logs
		try:
			from playwright.sync_api import sync_playwright
			meta = item.source_meta
			title = meta.get("title", "") if isinstance(meta, dict) else ""
			if not title:
				title = f"{item.std_no} {item.name}".strip()
			emit(f"ZBY: 搜索 {title[:40]}...")
			with sync_playwright() as p:
				browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
				context = browser.new_context()
				page = context.new_page()
				# 尝试最多三次以提高成功率并延长超时
				tried = 0
				success = False
				last_resp_status = None
				while tried < 3 and not success:
					tried += 1
					try:
						resp = page.goto(f"{self.base_url}/standardList?searchText={title}&activeTitle=true", timeout=45000)
						try:
							last_resp_status = resp.status if resp is not None else None
						except Exception:
							last_resp_status = None
						try:
							page.wait_for_selector(".stdList", timeout=30000)
						except:
							# small fallback
							time.sleep(2)
						success = True
					except Exception:
						emit(f"ZBY: 页面加载超时 (尝试 {tried}) resp_status={last_resp_status}")
						time.sleep(1)
						# 继续下一次尝试
				if not success:
					browser.close()
					return None, logs
				target = page.query_selector(".stdList")
				found = {"uuid": None}
				# 首先尝试从列表项里找到详情页链接并直接打开，避免新页面事件的不稳定性
				try:
					link = None
					if target:
						a_el = target.query_selector("a")
						if a_el:
							link = a_el.get_attribute('href')
					if link:
						if link.startswith('/'):
							detail_url = f"{self.base_url}{link}"
						elif link.startswith('http'):
							detail_url = link
						else:
							detail_url = f"{self.base_url}/{link}"
						try:
							detail_page = context.new_page()
							detail_page.on('request', lambda r: (found.update({'uuid': re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', r.url).group(1)}) if re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', r.url) else None))
							r = detail_page.goto(detail_url, timeout=45000)
							try:
								detail_page.wait_for_selector('#aliyunPreview', timeout=30000)
							except:
								pass
							cookies = context.cookies()
							detail_page.close()
						except Exception:
							# 暂时忽略打开详情页时的异常，继续后续回退逻辑
							pass
				except Exception:
					# 作为回退，还是尝试基于请求监听的老逻辑
					try:
						def handle_req(r):
							if "/doc/I/" in r.url and "immdoc" in r.url:
								m = re.search(r'immdoc/([a-zA-Z0-9-]+)/doc', r.url)
								if m:
									found["uuid"] = m.group(1)
						with context.expect_page() as new_pg:
							h4 = target.query_selector("h4")
							if h4:
								h4.click(modifiers=["Control"])
						detail_page = new_pg.value
						detail_page.on("request", handle_req)
						try:
							detail_page.wait_for_load_state(timeout=20000)
							detail_page.wait_for_selector("#aliyunPreview", timeout=20000)
							time.sleep(2)
						except Exception:
							emit("ZBY: 详情页加载或预览选择器超时")
							cookies = context.cookies()
						detail_page.close()
					except Exception:
						cookies = context.cookies()
				browser.close()
				if found["uuid"]:
					return self._download_images(found["uuid"], item.filename(), output_dir, cookies, emit)
				else:
					emit("ZBY: 未找到文档资源，该标准可能无电子版")
					return None, logs
		except Exception as e:
			emit(f"ZBY: Download error: {e}")
			return None, logs

	def _download_images(self, uuid: str, filename: str, output_dir: Path, cookies: list, emit: Callable):
		logs = []
		emit(f"ZBY: 获取到UUID: {uuid[:8]}..., 开始下载")
		temp_dir = output_dir / "zby_temp"
		if temp_dir.exists():
			shutil.rmtree(temp_dir)
		temp_dir.mkdir(parents=True, exist_ok=True)
		cookies_dict = {c['name']: c['value'] for c in cookies}
		imgs = []
		page_num = 1
		while True:
			try:
				url = f"https://resource.zhenggui.vip/immdoc/{uuid}/doc/I/{page_num}"
				r = self.session.get(url, cookies=cookies_dict, timeout=15)
				if r.status_code != 200:
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
			emit(f"ZBY: PDF生成成功")
			try:
				shutil.rmtree(temp_dir)
			except:
				pass
			return output_path, logs
		else:
			emit("ZBY: 未下载到任何页面")
			return None, logs
