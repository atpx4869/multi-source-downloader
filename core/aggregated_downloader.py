# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
import time
import sys

from core.models import Standard, natural_key

PRIORITY = ["GBW", "BY", "ZBY"]


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
        for name, (modname, clsname) in mapping.items():
            try:
                mod = __import__(modname, fromlist=[clsname])
                cls = getattr(mod, clsname)
                candidates.append((name, cls))
            except Exception as exc:
                # 记录到 health_cache，继续其他源
                self.health_cache[name] = SourceHealth(name)
                self.health_cache[name].error = str(exc)
                # Try a fallback: load the module directly from the repository sources/<mod>.py
                try:
                    import importlib.util as _il
                    import types as _types
                    rel_path = Path(*modname.split('.')).with_suffix('.py')
                    # try multiple candidate roots: current file ancestors, cwd, home
                    candidate_roots = []
                    p = Path(__file__).resolve()
                    for i in range(1, 6):
                        try:
                            candidate_roots.append(p.parents[i])
                        except Exception:
                            pass
                    candidate_roots.append(Path.cwd())
                    candidate_roots.append(Path.home())

                    found = False
                    for root in candidate_roots:
                        candidate_file = root / rel_path
                        if candidate_file.exists():
                            try:
                                # ensure package exists
                                if 'sources' not in sys.modules:
                                    pkg = _types.ModuleType('sources')
                                    pkg.__path__ = [str(candidate_file.parent)]
                                    sys.modules['sources'] = pkg
                                spec = _il.spec_from_file_location(modname, str(candidate_file))
                                if spec and spec.loader:
                                    m = _il.module_from_spec(spec)
                                    spec.loader.exec_module(m)
                                    sys.modules[modname] = m
                                    cls = getattr(m, clsname)
                                    candidates.append((name, cls))
                                    # clear stored error
                                    self.health_cache.pop(name, None)
                                    found = True
                                    break
                            except Exception:
                                continue
                    if found:
                        continue
                except Exception:
                    pass
                print(f"跳过源 {name}：{exc}")
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
                # compute completeness score per source (count of non-empty meta fields)
                meta_map = obj.source_meta if isinstance(obj.source_meta, dict) else {}
                scores = {}
                for sname, smeta in meta_map.items():
                    if not isinstance(smeta, dict):
                        scores[sname] = 0
                        continue
                    cnt = 0
                    for v in smeta.values():
                        try:
                            if v:
                                cnt += 1
                        except Exception:
                            pass
                    scores[sname] = cnt

                # Prefer ZBY for display only when its completeness exceeds the sum of others
                zby_score = scores.get('ZBY', 0)
                others_score = sum(v for k2, v in scores.items() if k2 != 'ZBY')
                if zby_score > others_score and zby_score > 0:
                    obj._display_source = 'ZBY'
                    # move ZBY to front of sources list for UI display, keep uniqueness
                    srcs = list(dict.fromkeys(obj.sources or []))
                    if 'ZBY' in srcs:
                        srcs.remove('ZBY')
                        srcs.insert(0, 'ZBY')
                        obj.sources = srcs
                else:
                    # otherwise, leave display source as-is (first source)
                    obj._display_source = obj.sources[0] if obj.sources else None
        except Exception:
            pass

    def search(self, keyword: str, **kwargs) -> List[Standard]:
        combined: Dict[str, Standard] = {}
        
        # 直接使用所有启用的源，不依赖健康检查
        # 健康检查仅用于UI显示，不影响搜索
        for src in self.sources:
            try:
                items = src.search(keyword, **kwargs)
            except TypeError:
                items = src.search(keyword)
            except Exception as exc:
                print(f"{src.name} 搜索失败：{exc}")
                continue
            self._merge_items(combined, items, src.name)
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

    def download(self, item: Standard, log_cb=None) -> tuple:
        """按优先级下载（GBW > BY > ZBY），逐个尝试直到成功。返回(路径或None, 日志列表)。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logs: list[str] = []
        seen_item: set[str] = set()

        def filtered_cb(line: str):
            if not isinstance(line, str):
                return
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

        # 构建下载尝试顺序：严格按照全局 PRIORITY（GBW > BY > ZBY）去匹配可用的 item.sources
        ordered_sources = []
        try:
            src_names_set = set(item.sources or [])
            for name in PRIORITY:
                for src in self.sources:
                    if src.name == name and src.name in src_names_set:
                        ordered_sources.append(src)
            # 兜底：若还有未包含的 sources（不在 PRIORITY 中），追加在最后
            for src in self.sources:
                if src.name in src_names_set and src not in ordered_sources:
                    ordered_sources.append(src)
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
                try:
                    result = src.download(clone, self.output_dir, log_cb=filtered_cb)
                except TypeError:
                    result = src.download(clone, self.output_dir)
                if isinstance(result, tuple):
                    path, extra_logs = result
                else:
                    path = result
                # 如果调用方提供了 log_cb，extra_logs 通常已经在回调中输出；避免重复。
                if extra_logs and not log_cb:
                    for line in extra_logs:
                        emit(line)
                if path:
                    emit(f"{src.name}: 成功 -> {path}")
                    return path, logs
                else:
                    emit(f"{src.name}: 未获取到文件，尝试下一个源")
            except Exception as exc:
                emit(f"{src.name}: 失败 -> {exc}，尝试下一个源")
        emit("所有来源均未成功")
        return None, logs
