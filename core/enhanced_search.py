# -*- coding: utf-8 -*-
"""
增强型智能搜索器 - 多线程 + 容错 + 重试机制
"""
import concurrent.futures
import time
from typing import List, Dict, Tuple, Optional, Callable
from core.smart_search import StandardSearchMerger


class EnhancedSmartSearcher:
    """增强型智能搜索器 - 支持多线程、容错和兜底"""
    
    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 10
    # 重试次数
    MAX_RETRIES = 2
    
    @staticmethod
    def search_with_fallback(keyword: str, downloader, output_dir: str = "downloads") -> Tuple[List[Dict], Dict]:
        """
        智能搜索 - 根据标准类型选择数据源，支持多线程和自动降级
        
        Args:
            keyword: 搜索关键词
            downloader: AggregatedDownloader 实例
            output_dir: 输出目录
        
        Returns:
            (results, metadata) 元组
            - results: 搜索结果列表
            - metadata: {
                'sources_used': [使用的数据源],
                'is_gb_standard': 是否为 GB 标准,
                'primary_source': 主数据源,
                'fallback_source': 备用数据源（如果使用了）,
                'elapsed_time': 总耗时,
                'retry_count': 重试次数
              }
        """
        metadata = {
            'keyword': keyword,
            'is_gb_standard': False,
            'sources_used': [],
            'primary_source': None,
            'fallback_source': None,
            'elapsed_time': 0,
            'retry_count': 0,
            'has_fallback': False,
        }
        
        start_time = time.time()
        
        # 检测是否是 GB/T 或 GB 标准（仅用于记录，不用于决定是否并行查询）
        is_gb_std = StandardSearchMerger.is_gb_standard(keyword)
        metadata['is_gb_standard'] = is_gb_std

        # 统一并行查询所有主要数据源（GBW, BY, ZBY），由合并逻辑决定最终结果
        results, used_sources, fallback_info = EnhancedSmartSearcher._search_gb_standard(
            keyword, downloader, output_dir
        )
        metadata['sources_used'] = used_sources
        metadata['primary_source'] = 'ZBY'
        metadata['fallback_source'] = fallback_info.get('source')
        metadata['has_fallback'] = fallback_info.get('used', False)
        metadata['retry_count'] = fallback_info.get('retry_count', 0)
        
        metadata['elapsed_time'] = time.time() - start_time
        return results, metadata
    
    @staticmethod
    def search_with_callback(keyword: str, downloader, output_dir: str = "downloads", 
                             on_result: Optional[Callable[[Dict, List[Dict]], None]] = None) -> Dict:
        """
        流式搜索 - 查到一条显示一条，实时回调
        
        Args:
            keyword: 搜索关键词
            downloader: AggregatedDownloader 实例
            output_dir: 输出目录
            on_result: 回调函数，签名为 on_result(source_name, results_batch)
                       - source_name: 数据源名称 (str)
                       - results_batch: 本批结果列表 (List[Dict])
        
        Returns:
            metadata: 搜索元数据
        """
        metadata = {
            'keyword': keyword,
            'is_gb_standard': False,
            'sources_used': [],
            'primary_source': None,
            'fallback_source': None,
            'elapsed_time': 0,
            'retry_count': 0,
            'has_fallback': False,
            'total_results': 0,
        }
        
        start_time = time.time()
        
        # 检测是否是 GB/T 或 GB 标准（仅用于记录，不用于决定是否并行查询）
        is_gb_std = StandardSearchMerger.is_gb_standard(keyword)
        metadata['is_gb_standard'] = is_gb_std

        # 统一流式并行搜索 GBW、BY、ZBY（谁先返回就先显示），由合并逻辑决定最终展示
        used_sources, fallback_info, total = EnhancedSmartSearcher._search_gb_standard_streaming(
            keyword, downloader, output_dir, on_result
        )
        metadata['sources_used'] = used_sources
        metadata['primary_source'] = 'ZBY'
        metadata['fallback_source'] = fallback_info.get('source')
        metadata['has_fallback'] = fallback_info.get('used', False)
        metadata['retry_count'] = fallback_info.get('retry_count', 0)
        metadata['total_results'] = total
        
        metadata['elapsed_time'] = time.time() - start_time
        return metadata
    
    @staticmethod
    def _search_gb_standard_streaming(keyword: str, downloader, output_dir: str,
                                      on_result: Optional[Callable]) -> Tuple[List[str], Dict, int]:
        """
        GB/T 标准流式搜索 - 并行搜索 GBW + BY + ZBY（优先级：GBW > BY > ZBY），逐条返回结果
        
        返回: (sources_used, fallback_info, total_count)
        """
        from core.aggregated_downloader import AggregatedDownloader
        
        fallback_info = {'source': None, 'used': False, 'retry_count': 0}
        sources_used = []
        total_count = 0
        seen_keys = set()  # 用于去重
        
        def search_and_stream_source(source_name: str):
            """搜索单个数据源，逐条返回"""
            results = []
            try:
                client = AggregatedDownloader(enable_sources=[source_name], output_dir=output_dir)
                items = client.search(keyword, parallel=False)
                
                for it in items:
                    result = {
                        "std_no": it.std_no,
                        "name": it.name,
                        "publish": it.publish or "",
                        "implement": it.implement or "",
                        "status": it.status or "",
                        "replace_std": it.replace_std or "",
                        "has_pdf": bool(it.has_pdf),
                        "sources": it.sources or [source_name],
                        "obj": it,
                    }
                    results.append((source_name, result))
            except Exception as e:
                pass
            
            return results
        
        # 并行搜索 GBW、BY、ZBY（GB 标准的优先级：GBW > BY > ZBY）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(search_and_stream_source, "GBW"): "GBW",
                executor.submit(search_and_stream_source, "BY"): "BY",
                executor.submit(search_and_stream_source, "ZBY"): "ZBY",
            }
            
            # 收集所有结果
            all_results = {source: [] for source in ["GBW", "BY", "ZBY"]}
            
            try:
                for future in concurrent.futures.as_completed(futures, timeout=EnhancedSmartSearcher.DEFAULT_TIMEOUT * 1.5):
                    source_name = futures[future]
                    try:
                        results = future.result()
                        all_results[source_name] = results
                        if results:
                            sources_used.append(source_name)
                    except Exception as e:
                        pass
            except concurrent.futures.TimeoutError:
                pass
        
        # 按优先级进行智能合并（GBW > BY > ZBY），以完整规范化后的标准号为 key
        merged_map = {}

        for priority_source in ["GBW", "BY", "ZBY"]:
            for source_name, result in all_results.get(priority_source, []):
                key = StandardSearchMerger._normalize_std_no(result.get("std_no", ""))
                if not key:
                    continue

                if key in merged_map:
                    # 合并 sources
                    merged_map[key]["sources"] = list(set(merged_map[key].get("sources", []) + result.get("sources", [priority_source])))
                    # 合并 has_pdf（任意源有则为 True）
                    merged_map[key]["has_pdf"] = bool(merged_map[key].get("has_pdf") or result.get("has_pdf"))
                    # 合并文本字段：优先保留已有值，若为空则使用当前源的值（任何源有文本则显示）
                    for fld in ("publish", "implement", "status", "replace_std", "name"):
                        if not merged_map[key].get(fld) and result.get(fld):
                            merged_map[key][fld] = result.get(fld)
                else:
                    row = result.copy()
                    row["sources"] = row.get("sources", [priority_source])
                    row["has_pdf"] = bool(row.get("has_pdf"))
                    merged_map[key] = row

        # 流式返回合并后的结果（一次性返回 MERGED 列表以保持行为一致）
        merged_results = list(merged_map.values())
        if merged_results:
            if on_result:
                on_result("MERGED", merged_results)
            total_count = len(merged_results)

        return sources_used, fallback_info, total_count
    
    @staticmethod
    def _search_non_gb_standard_streaming(keyword: str, downloader, output_dir: str,
                                          on_result: Optional[Callable]) -> Tuple[List[str], Dict, int]:
        """
        非 GB 标准流式搜索 - 优先 ZBY，失败时尝试其他源
        
        返回: (sources_used, fallback_info, total_count)
        """
        from core.aggregated_downloader import AggregatedDownloader
        
        fallback_info = {'source': None, 'used': False, 'retry_count': 0}
        
        # 优先尝试 ZBY
        try:
            client = AggregatedDownloader(enable_sources=["ZBY"], output_dir=output_dir)
            items = client.search(keyword, parallel=False)
            
            rows = []
            for it in items:
                rows.append({
                    "std_no": it.std_no,
                    "name": it.name,
                    "publish": it.publish or "",
                    "implement": it.implement or "",
                    "status": it.status or "",
                    "replace_std": it.replace_std or "",
                    "has_pdf": bool(it.has_pdf),
                    "sources": it.sources or ["ZBY"],
                    "obj": it,
                })
            
            if rows:
                if on_result:
                    on_result("ZBY", rows)
                return ["ZBY"], fallback_info, len(rows)
        except Exception as e:
            pass
        
        # ZBY 失败或无结果，尝试兜底方案
        return EnhancedSmartSearcher._search_with_other_sources_streaming(
            keyword, downloader, output_dir, on_result
        )
    
    @staticmethod
    def _search_with_other_sources_streaming(keyword: str, downloader, output_dir: str,
                                             on_result: Optional[Callable]) -> Tuple[List[str], Dict, int]:
        """
        兜底方案流式搜索：依次尝试其他数据源（GBW, BY 等）
        
        返回: (sources_used, fallback_info, total_count)
        """
        from core.aggregated_downloader import AggregatedDownloader
        
        fallback_sources = ["GBW", "BY"]  # 备用数据源的优先级
        
        for retry_count, fallback_source in enumerate(fallback_sources):
            try:
                client = AggregatedDownloader(enable_sources=[fallback_source], output_dir=output_dir)
                items = client.search(keyword, parallel=False)
                
                rows = []
                for it in items:
                    rows.append({
                        "std_no": it.std_no,
                        "name": it.name,
                        "publish": it.publish or "",
                        "implement": it.implement or "",
                        "status": it.status or "",
                        "replace_std": it.replace_std or "",
                        "has_pdf": bool(it.has_pdf),
                        "sources": it.sources or [fallback_source],
                        "obj": it,
                    })
                
                if rows:
                    if on_result:
                        on_result(fallback_source, rows)
                    
                    fallback_info = {
                        'source': fallback_source,
                        'used': True,
                        'retry_count': retry_count
                    }
                    return [fallback_source], fallback_info, len(rows)
            except Exception as e:
                continue
        
        # 所有来源都失败或无结果
        return [], {'source': None, 'used': False, 'retry_count': len(fallback_sources)}, 0
    
    @staticmethod
    def _search_gb_standard(keyword: str, downloader, output_dir: str) -> Tuple[List[Dict], List[str], Dict]:
        """
        搜索 GB/T 或 GB 标准 - 优先并行搜索 ZBY + GBW，失败时兜底
        
        返回: (results, sources_used, fallback_info)
        """
        from core.aggregated_downloader import AggregatedDownloader
        
        fallback_info = {'source': None, 'used': False, 'retry_count': 0}
        zby_results = []
        gbw_results = []
        sources_used = []
        
        def search_source(source_name: str, timeout: int):
            """搜索单个数据源"""
            try:
                client = AggregatedDownloader(enable_sources=[source_name], output_dir=output_dir)
                # 这里不使用 parallel 避免双重并行导致超时
                items = client.search(keyword, parallel=False)
                
                rows = []
                for it in items:
                    rows.append({
                        "std_no": it.std_no,
                        "name": it.name,
                        "publish": it.publish or "",
                        "implement": it.implement or "",
                        "status": it.status or "",
                        "replace_std": it.replace_std or "",
                        "has_pdf": bool(it.has_pdf),
                        "sources": it.sources or [source_name],
                        "obj": it,
                    })
                return source_name, rows
            except Exception as e:
                return source_name, None  # None 表示失败
        
        # 并行搜索 GBW、BY、ZBY（统一并行搜索，保证覆盖所有源）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(search_source, "GBW", EnhancedSmartSearcher.DEFAULT_TIMEOUT): "GBW",
                executor.submit(search_source, "BY", EnhancedSmartSearcher.DEFAULT_TIMEOUT): "BY",
                executor.submit(search_source, "ZBY", EnhancedSmartSearcher.DEFAULT_TIMEOUT): "ZBY",
            }
            
            all_results = {"GBW": [], "BY": [], "ZBY": []}
            for future in concurrent.futures.as_completed(futures, timeout=EnhancedSmartSearcher.DEFAULT_TIMEOUT * 1.5):
                source_name, results = future.result()
                if results is not None:
                    all_results[source_name] = results
                    sources_used.append(source_name)
        
        # 智能合并结果：按优先级 GBW > BY > ZBY 合并，保留所有来源信息
        merged_map = {}
        for priority in ["GBW", "BY", "ZBY"]:
            for item in all_results.get(priority, []):
                key = StandardSearchMerger._normalize_std_no(item.get("std_no", ""))
                if not key:
                    continue
                if key in merged_map:
                    # 合并 sources
                    merged_map[key]["sources"] = list(set(merged_map[key].get("sources", []) + item.get("sources", [priority])))
                    # 合并文本字段：任意源有文本就保留
                    for fld in ("publish", "implement", "status", "replace_std"):
                        if not merged_map[key].get(fld) and item.get(fld):
                            merged_map[key][fld] = item.get(fld)
                else:
                    # 复制一份，确保 sources 字段存在
                    row = item.copy()
                    row["sources"] = row.get("sources", [priority])
                    merged_map[key] = row

        if merged_map:
            merged = list(merged_map.values())
            return merged, sources_used, fallback_info

        # 所有源都无结果，尝试兜底方案
        return EnhancedSmartSearcher._search_with_other_sources(keyword, downloader, output_dir)
    
    @staticmethod
    def _search_non_gb_standard(keyword: str, downloader, output_dir: str) -> Tuple[List[Dict], List[str], Dict]:
        """
        搜索非 GB 标准 - 优先 ZBY，失败时尝试其他源
        
        返回: (results, sources_used, fallback_info)
        """
        from core.aggregated_downloader import AggregatedDownloader
        
        fallback_info = {'source': None, 'used': False, 'retry_count': 0}
        
        # 优先尝试 ZBY
        try:
            client = AggregatedDownloader(enable_sources=["ZBY"], output_dir=output_dir)
            items = client.search(keyword, parallel=False)
            
            rows = []
            for it in items:
                rows.append({
                    "std_no": it.std_no,
                    "name": it.name,
                    "publish": it.publish or "",
                    "implement": it.implement or "",
                    "status": it.status or "",
                    "replace_std": it.replace_std or "",
                    "has_pdf": bool(it.has_pdf),
                    "sources": it.sources or ["ZBY"],
                    "obj": it,
                })
            
            if rows:
                return rows, ["ZBY"], fallback_info
        except Exception as e:
            pass
        
        # ZBY 失败或无结果，尝试兜底方案
        return EnhancedSmartSearcher._search_with_other_sources(keyword, downloader, output_dir)
    
    @staticmethod
    def _search_with_other_sources(keyword: str, downloader, output_dir: str) -> Tuple[List[Dict], List[str], Dict]:
        """
        兜底方案：依次尝试其他数据源（BY, GBW 等）
        
        返回: (results, sources_used, fallback_info)
        """
        from core.aggregated_downloader import AggregatedDownloader
        
        fallback_sources = ["GBW", "BY"]  # 备用数据源的优先级
        
        for retry_count, fallback_source in enumerate(fallback_sources):
            try:
                client = AggregatedDownloader(enable_sources=[fallback_source], output_dir=output_dir)
                items = client.search(keyword, parallel=False)
                
                rows = []
                for it in items:
                    rows.append({
                        "std_no": it.std_no,
                        "name": it.name,
                        "publish": it.publish or "",
                        "implement": it.implement or "",
                        "status": it.status or "",
                        "replace_std": it.replace_std or "",
                        "has_pdf": bool(it.has_pdf),
                        "sources": it.sources or [fallback_source],
                        "obj": it,
                    })
                
                if rows:
                    fallback_info = {
                        'source': fallback_source,
                        'used': True,
                        'retry_count': retry_count
                    }
                    return rows, [fallback_source], fallback_info
            except Exception as e:
                continue
        
        # 所有来源都失败或无结果
        return [], [], {'source': None, 'used': False, 'retry_count': len(fallback_sources)}
