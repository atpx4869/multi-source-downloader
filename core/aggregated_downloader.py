# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Dict, List, Tuple
import re
import time

from core.models import Standard, natural_key
from sources.gbw import GBWSource
from sources.by import BYSource
from sources.zby import ZBYSource

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
    def __init__(self, output_dir: str = "downloads", enable_sources: List[str] | None = None):
        self.output_dir = Path(output_dir)
        self.sources: List[object] = []
        self.health_cache: Dict[str, SourceHealth] = {}
        candidates = [("GBW", GBWSource), ("BY", BYSource), ("ZBY", ZBYSource)]
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
            
            # 有缓存且未强制检查则跳过
            if not force and health.last_check > 0 and (time.time() - health.last_check < 60):
                continue
            
            # 执行健康检查
            try:
                start = time.time()
                # 不同源的检查方式不同
                if name == "GBW":
                    # GBW 简单检查：尝试请求搜索接口
                    import requests
                    resp = requests.head("https://std.samr.gov.cn", timeout=5)
                    resp.raise_for_status()
                elif name == "BY":
                    # BY 检查：需要能成功初始化会话
                    # 已在 __init__ 时测试过了
                    pass
                elif name == "ZBY":
                    # ZBY 检查：简单的 API 调用
                    import requests
                    resp = requests.head("https://bz.zhenggui.vip", timeout=5)
                    resp.raise_for_status()
                
                health.response_time = time.time() - start
                health.available = True
                health.error = ""
            except Exception as exc:
                health.available = False
                health.error = str(exc)[:50]
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
            # 确保当前 item 的 meta 包装成 map
            if not (isinstance(item.source_meta, dict) and src_name in item.source_meta):
                item.source_meta = {src_name: item.source_meta}
            if key in existing:
                cur = existing[key]
                if src_name not in cur.sources:
                    cur.sources.append(src_name)
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
                cur.source_meta[src_name] = item.source_meta.get(src_name, item.source_meta)
            else:
                item.sources = list(dict.fromkeys(item.sources or [src_name]))
                existing[key] = item

    def search(self, keyword: str, **kwargs) -> List[Standard]:
        combined: Dict[str, Standard] = {}
        available_sources = self.get_available_sources()
        
        # 如果没有可用源，自动检查一次
        if not available_sources:
            self.check_source_health(force=True)
            available_sources = self.get_available_sources()
        
        for src in available_sources:
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

    def download(self, item: Standard, log_cb=None) -> tuple[Path | None, list[str]]:
        """按优先级下载，返回(路径或None, 日志列表)。log_cb 用于实时输出。"""
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

        for src in self.sources:
            if src.name not in item.sources:
                continue
            clone = self._clone_for_source(item, src.name)
            emit(f"{src.name}: 开始尝试")
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
                    emit(f"{src.name}: 未获取到文件")
            except Exception as exc:
                emit(f"{src.name}: 失败 -> {exc}")
        emit("所有来源均未成功")
        return None, logs
