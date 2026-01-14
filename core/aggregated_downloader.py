# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
import time
import sys

from core.models import Standard, natural_key

# 下载优先级（按源）：BY > GBW > ZBY
PRIORITY = ["BY", "GBW", "ZBY"]


class SourceHealth:
    """源健康状态信息"""
    def __init__(self, name: str):
        self.name = name
        self.available = False
        self.error = ""
        self.last_check = 0.0
        self.response_time = 0.0
    
    def __repr__(self):
        status = "✅ 可用" if self.available else f"❌ 不可用: {self.error}"
        time_str = f" ({self.response_time:.2f}s)" if self.response_time > 0 else ""
        return f"{self.name}: {status}{time_str}"


class AggregatedDownloader:
    def __init__(self, output_dir: str = "downloads", enable_sources: Optional[List[str]] = None):
        self.output_dir = Path(output_dir)
        self.sources: List[object] = []
        self.health_cache: Dict[str, SourceHealth] = {}
        # 延迟导入各源以避免循环导入问题
        mapping = {
            "GBW": ("sources.gbw", "GBWSource"),
            "BY": ("sources.by", "BYSource"),
            "ZBY": ("sources.zby", "ZBYSource"),
        }
        candidates: List[Tuple[str, object]] = []
        
        # Use centralized loader
        from core.loader import load_source_class
        
        for name, (modname, clsname) in mapping.items():
            cls, error = load_source_class(modname, clsname)
            if cls:
                candidates.append((name, cls))
                self.health_cache.pop(name, None)
            else:
                self.health_cache[name] = SourceHealth(name)
                self.health_cache[name].error = error or "Unknown import error"
                print(f"跳过源 {name}：{self.health_cache[name].error}")
        for name, cls in candidates:
            if enable_sources and name not in enable_sources:
                continue
            try:
                src = cls(self.output_dir) if name == "ZBY" else cls()
                self.sources.append(src)
                self.health_cache[name] = SourceHealth(name)
            except Exception as exc:
                print(f"跳过源 {name}：{exc}")
                self.health_cache[name] = SourceHealth(name)
                self.health_cache[name].error = str(exc)
        self.sources.sort(key=lambda s: getattr(s, "priority", 99))
    
    def check_source_health(self, force: bool = False) -> Dict[str, SourceHealth]:
        """检查所有源的连通性，返回健康状态字典"""
        for src in self.sources:
            name = src.name
            health = self.health_cache.get(name, SourceHealth(name))

            # 有缓存且未强制检查则跳过（缓存有效期 60s）
            if not force and health.last_check > 0 and (time.time() - health.last_check < 60):
                continue

            # 执行健康检查：优先调用源自身提供的检查方法 is_available()
            start = time.time()
            try:
                available = False
                # 优先使用源提供的检测接口
                if hasattr(src, 'is_available') and callable(getattr(src, 'is_available')):
                    try:
                        available = bool(src.is_available())
                    except Exception as e:
                        # 源内部检查可能抛错，记录并回退到通用检查
                        available = False
                        health.error = f"is_available error: {e}"

                # 若没有 is_available 或调用失败，使用更可靠的 GET 请求检测具体的服务端点
                if not available:
                    import requests

                    def try_get(url, timeout=6):
                        try:
                            r = requests.get(url, timeout=timeout, allow_redirects=True)
                            return r
                        except Exception:
                            return None

                    # 针对已知源使用更具体的检测 URL 和简单重试
                    candidates = []
                    if getattr(src, 'base_url', None):
                        # 优先检测源的 base_url 或其搜索接口
                        base = getattr(src, 'base_url')
                        if name == 'GBW':
                            candidates = [f"{base}/gb/search/gbQueryPage?searchText=test&pageNum=1&pageSize=1", base]
                        else:
                            candidates = [base]
                    else:
                        # 兜底到常规域名（可能不可用）
                        if name == 'GBW':
                            candidates = ['https://std.samr.gov.cn']
                        elif name == 'ZBY':
                            candidates = ['https://bz.zhenggui.vip']
                        else:
                            candidates = []

                    resp = None
                    # 简单重试策略：尝试最多 2 次每个候选 URL
                    for url in candidates:
                        for _ in range(2):
                            resp = try_get(url)
                            if resp is not None and resp.status_code >= 200 and resp.status_code < 500:
                                break
                        if resp is not None:
                            break

                    if resp is None:
                        available = False
                        if not health.error:
                            health.error = 'no response'
                    else:
                        # 将 2xx/3xx 视为可用，4xx/5xx 视为不可用
                        available = 200 <= resp.status_code < 400
                        if not available:
                            health.error = f'status {resp.status_code}'

                health.response_time = time.time() - start
                health.available = bool(available)
                if health.available and not health.error:
                    health.error = ''
            except Exception as exc:
                health.available = False
                health.error = str(exc)[:200]
                health.response_time = 0.0

            health.last_check = time.time()
            self.health_cache[name] = health
        
        return self.health_cache
    
    def get_available_sources(self) -> List[object]:
        """获取可用的源列表"""
        return [src for src in self.sources if self.health_cache.get(src.name, SourceHealth(src.name)).available]

    @staticmethod
    def _norm_std_no(std_no: str) -> str:
        # 统一去掉空白和常见分隔符，避免名称差异造成重复
        return re.sub(r"[\\s/\\-–—_:：]+", "", std_no or "").lower()

    def _merge_items(self, existing: Dict[str, Standard], items: List[Standard], src_name: str):
        """合并去重，确保 source_meta 始终为 {源名: meta} 结构；同一标准号只保留一条。"""
        for item in items:
            key = self._norm_std_no(item.std_no)
            
            # 获取原始 meta 数据
            original_meta = item.source_meta if isinstance(item.source_meta, dict) else {}
            
            # 构建该源的 meta 数据，确保包含 _has_pdf
            meta_data = original_meta.copy() if isinstance(original_meta, dict) else {}
            meta_data["_has_pdf"] = item.has_pdf  # 保存该源的 has_pdf 状态
            
            if key in existing:
                cur = existing[key]
                if src_name not in cur.sources:
                    cur.sources.append(src_name)
                # 任意源有 PDF 则显示有 PDF
                cur.has_pdf = cur.has_pdf or item.has_pdf
                # 名称保留更长的，避免空或简写
                if len(item.name or "") > len(cur.name or ""):
                    cur.name = item.name
                if item.publish and not cur.publish:
                    cur.publish = item.publish
                if item.implement and not cur.implement:
                    cur.implement = item.implement
                if item.status and not cur.status:
                    cur.status = item.status
                # 合并 meta，保留已存在的，同时更新本源的
                if not isinstance(cur.source_meta, dict):
                    cur.source_meta = {}
                cur.source_meta[src_name] = meta_data
            else:
                item.sources = list(dict.fromkeys(item.sources or [src_name]))
                # 确保新项的 source_meta 格式正确
                item.source_meta = {src_name: meta_data}
                # 初始时设置展示来源为空，后续可能在合并时调整
                item._display_source = src_name
                existing[key] = item

        # After merge, evaluate which source should be used for display
        try:
            for k, obj in existing.items():
                meta_map = obj.source_meta if isinstance(obj.source_meta, dict) else {}

                def score_source(sname: str):
                    smeta = meta_map.get(sname, {}) if isinstance(meta_map, dict) else {}
                    has_pdf = False
                    try:
                        has_pdf = bool(smeta.get("_has_pdf"))
                    except Exception:
                        has_pdf = False
                    prio = PRIORITY.index(sname) if sname in PRIORITY else 99
                    return (0 if has_pdf else 1, prio)

                # 选择最佳展示源：先看是否有PDF，再按 BY>GBW>ZBY
                best_src = None
                best_score = (1, 99)
                for sname in obj.sources or []:
                    sc = score_source(sname)
                    if sc < best_score:
                        best_score = sc
                        best_src = sname

                if best_src:
                    obj._display_source = best_src
                    # 将最佳源放在 sources 列表最前，保持唯一
                    srcs = list(dict.fromkeys(obj.sources or []))
                    if best_src in srcs:
                        srcs.remove(best_src)
                        srcs.insert(0, best_src)
                        obj.sources = srcs
                else:
                    obj._display_source = obj.sources[0] if obj.sources else None
        except Exception:
            pass

    def search(self, keyword: str, parallel: bool = True, **kwargs) -> List[Standard]:
        combined: Dict[str, Standard] = {}
        
        if not parallel:
            # 串行搜索（兼容旧版）
            for src in self.sources:
                try:
                    items = src.search(keyword, **kwargs)
                except TypeError:
                    items = src.search(keyword)
                except Exception as exc:
                    print(f"{src.name} 搜索失败：{exc}")
                    continue
                self._merge_items(combined, items, src.name)
        else:
            # 并行搜索（推荐，性能提升 3-5 倍）
            import concurrent.futures
            import threading
            
            lock = threading.Lock()
            
            def search_source(src):
                """单个源搜索任务"""
                try:
                    try:
                        items = src.search(keyword, **kwargs)
                    except TypeError:
                        items = src.search(keyword)
                    
                    # 线程安全地合并结果
                    with lock:
                        self._merge_items(combined, items, src.name)
                    
                    return src.name, len(items), None
                except Exception as exc:
                    return src.name, 0, str(exc)
            
            # 使用线程池并行搜索所有源
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.sources)) as executor:
                futures = [executor.submit(search_source, src) for src in self.sources]
                
                # 等待所有任务完成
                for future in concurrent.futures.as_completed(futures):
                    try:
                        name, count, error = future.result()
                        if error:
                            print(f"{name} 搜索失败：{error}")
                        else:
                            print(f"{name} 搜索完成：{count} 条")
                    except Exception as exc:
                        print(f"搜索任务异常：{exc}")
        
        results = list(combined.values())
        results.sort(key=lambda x: natural_key(x.std_no))
        return results

    def _clone_for_source(self, item: Standard, src_name: str) -> Standard:
        meta_map = item.source_meta if isinstance(item.source_meta, dict) else {src_name: item.source_meta}
        meta = meta_map.get(src_name, meta_map)
        return Standard(
            std_no=item.std_no,
            name=item.name,
            publish=item.publish,
            implement=item.implement,
            status=item.status,
            has_pdf=item.has_pdf,
            source_meta=meta,
            sources=[src_name],
        )

    def download(self, item: Standard, log_cb=None, prefer_order: Optional[List[str]] = None) -> tuple:
        """按优先级下载，逐个尝试直到成功。返回(路径或None, 日志列表)。

        prefer_order: 可选的优先级列表，例如 ["BY", "GBW", "ZBY"]，不传则使用全局 PRIORITY。
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logs: list[str] = []
        seen_item: set[str] = set()
        
        # 检查缓存和同名文件处理
        cached_path = self.output_dir / item.filename()
        if cached_path.exists():
            file_size = cached_path.stat().st_size
            if file_size > 0:
                # 文件存在且大小>0，使用缓存
                logs.append(f"✅ 缓存命中: {cached_path} (大小: {file_size} bytes)")
                return str(cached_path), logs
            else:
                # 文件存在但大小为0（可能是下载中断），删除后重新下载
                logs.append(f"⚠️  检测到不完整文件: {cached_path} (大小: 0 bytes)，删除后重新下载")
                try:
                    cached_path.unlink()
                except Exception as e:
                    logs.append(f"❌ 删除旧文件失败: {e}")
        
        def filtered_cb(line: str):
            if not isinstance(line, str):
                return
            
            # 涉及保密，脱敏处理：隐藏所有网址
            line = re.sub(r'https?://[^\s<>"]+', '[URL]', line)
            
            if line in seen_item:
                return
            seen_item.add(line)
            if log_cb:
                try:
                    log_cb(line)
                except Exception:
                    pass

        def emit(line: str):
            logs.append(line)
            filtered_cb(line)

        # 获取该标准在各源的 PDF 状态（用于显示）
        meta_map = item.source_meta if isinstance(item.source_meta, dict) else {}
        
        emit(f"DEBUG: Item sources: {item.sources}")

        # 构建下载尝试顺序：优先有PDF的源，再按优先级（默认 BY > GBW > ZBY，可由 prefer_order 覆盖）
        ordered_sources = []
        try:
            src_names_set = set(item.sources or [])

            order_list = prefer_order or PRIORITY

            def src_score(src):
                meta_map = item.source_meta if isinstance(item.source_meta, dict) else {}
                smeta = meta_map.get(src.name, {}) if isinstance(meta_map, dict) else {}
                has_pdf = bool(smeta.get("_has_pdf") or getattr(item, "has_pdf", False))
                prio = order_list.index(src.name) if src.name in order_list else 99
                return (0 if has_pdf else 1, prio)

            candidates = [src for src in self.sources if src.name in src_names_set]
            candidates.sort(key=src_score)
            ordered_sources = candidates
        except Exception:
            ordered_sources = [src for src in self.sources if src.name in (item.sources or [])]
        
        if not ordered_sources:
            emit("没有可用的下载源")
            return None, logs

        # 按优先级逐个尝试所有源（兜底机制）
        for src in ordered_sources:
            clone = self._clone_for_source(item, src.name)
            src_meta = meta_map.get(src.name, {})
            src_has_pdf = src_meta.get("_has_pdf", False) if isinstance(src_meta, dict) else False
            pdf_hint = "有PDF" if src_has_pdf else "无PDF标记"
            emit(f"{src.name}: 开始尝试 ({pdf_hint})")
            try:
                path = None
                extra_logs: list[str] = []
                
                # 单个源超时保护：每个源最多10秒（防止一个源卡住拖累整体）
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    def _download_from_source():
                        try:
                            result = src.download(clone, self.output_dir, log_cb=filtered_cb)
                        except TypeError:
                            result = src.download(clone, self.output_dir)
                        return result
                    
                    future = executor.submit(_download_from_source)
                    try:
                        result = future.result(timeout=10)  # 单个源最多10秒
                    except concurrent.futures.TimeoutError:
                        emit(f"{src.name}: 超时(10秒)，尝试下一个源")
                        continue
                
                if isinstance(result, tuple):
                    path, extra_logs = result
                else:
                    path = result
                # 如果调用方提供了 log_cb，extra_logs 通常已经在回调中输出；避免重复。
                if extra_logs and not log_cb:
                    for line in extra_logs:
                        emit(line)
                if path:
                    # 检查是新下载还是覆盖了旧文件
                    if isinstance(path, str):
                        path_obj = Path(path)
                    else:
                        path_obj = path
                    
                    if path_obj.exists():
                        file_size = path_obj.stat().st_size
                        emit(f"{src.name}: 成功 -> {path} (大小: {file_size} bytes)")
                    else:
                        emit(f"{src.name}: 成功 -> {path}")
                    return str(path), logs
                else:
                    emit(f"{src.name}: 未获取到文件，尝试下一个源")
            except Exception as exc:
                emit(f"{src.name}: 失败 -> {exc}，尝试下一个源")
        emit("所有来源均未成功")
        return None, logs
