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
        
        # 检测是否是 GB/T 或 GB 标准
        is_gb_std = StandardSearchMerger.is_gb_standard(keyword)
        metadata['is_gb_standard'] = is_gb_std
        
        if is_gb_std:
            # GB/T 或 GB 标准：尝试 ZBY + GBW 并行搜索
            results, used_sources, fallback_info = EnhancedSmartSearcher._search_gb_standard(
                keyword, downloader, output_dir
            )
            metadata['sources_used'] = used_sources
            metadata['primary_source'] = 'ZBY'
            metadata['fallback_source'] = fallback_info.get('source')
            metadata['has_fallback'] = fallback_info.get('used', False)
            metadata['retry_count'] = fallback_info.get('retry_count', 0)
        else:
            # 非 GB 标准：优先使用 ZBY，失败时尝试其他源
            results, used_sources, fallback_info = EnhancedSmartSearcher._search_non_gb_standard(
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
        
        # 检测是否是 GB/T 或 GB 标准
        is_gb_std = StandardSearchMerger.is_gb_standard(keyword)
        metadata['is_gb_standard'] = is_gb_std
        
        if is_gb_std:
            # GB/T 或 GB 标准：尝试 ZBY + GBW 并行搜索，流式返回
            used_sources, fallback_info, total = EnhancedSmartSearcher._search_gb_standard_streaming(
                keyword, downloader, output_dir, on_result
            )
            metadata['sources_used'] = used_sources
            metadata['primary_source'] = 'ZBY'
            metadata['fallback_source'] = fallback_info.get('source')
            metadata['has_fallback'] = fallback_info.get('used', False)
            metadata['retry_count'] = fallback_info.get('retry_count', 0)
            metadata['total_results'] = total
        else:
            # 非 GB 标准：优先使用 ZBY，失败时尝试其他源，流式返回
            used_sources, fallback_info, total = EnhancedSmartSearcher._search_non_gb_standard_streaming(
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
        GB/T 标准流式搜索 - 并行搜索 ZBY + GBW，逐条返回结果
        
        返回: (sources_used, fallback_info, total_count)
        """
        from core.aggregated_downloader import AggregatedDownloader
        
        fallback_info = {'source': None, 'used': False, 'retry_count': 0}
        sources_used = []
        total_count = 0
        zby_buffer = []
        gbw_buffer = []
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
        
        # 并行搜索 ZBY 和 GBW
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(search_and_stream_source, "ZBY"): "ZBY",
                executor.submit(search_and_stream_source, "GBW"): "GBW",
            }
            
            # 收集所有结果
            all_results = {source: [] for source in ["ZBY", "GBW"]}
            
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
        
        # 智能合并并流式返回结果
        if all_results["ZBY"] and all_results["GBW"]:
            # 两个源都有结果，进行智能合并去重
            merged_dict = {}
            
            # 先加入 ZBY 结果
            for source_name, result in all_results["ZBY"]:
                # 使用更精确的去重key：标准号+年份
                std_no_clean = result["std_no"].replace(" ", "").replace("/", "").upper()
                key = (std_no_clean, result["name"].lower().strip())
                if key not in seen_keys:
                    merged_dict[key] = result
                    seen_keys.add(key)
            
            # 再加入 GBW 结果，重复的进行合并
            for source_name, result in all_results["GBW"]:
                std_no_clean = result["std_no"].replace(" ", "").replace("/", "").upper()
                key = (std_no_clean, result["name"].lower().strip())
                if key in merged_dict:
                    # 合并信息：更新来源列表
                    merged_dict[key]["sources"] = list(set(
                        merged_dict[key].get("sources", []) + result.get("sources", ["GBW"])
                    ))
                else:
                    merged_dict[key] = result
                    seen_keys.add(key)
            
            # 流式返回合并后的结果
            merged_results = list(merged_dict.values())
            if on_result and merged_results:
                on_result("MERGED", merged_results)
            total_count = len(merged_results)
        
        elif all_results["ZBY"]:
            # 仅 ZBY 有结果
            zby_results = [result for _, result in all_results["ZBY"]]
            if on_result and zby_results:
                on_result("ZBY", zby_results)
            total_count = len(zby_results)
        
        elif all_results["GBW"]:
            # 仅 GBW 有结果（降级）
            gbw_results = [result for _, result in all_results["GBW"]]
            if on_result and gbw_results:
                on_result("GBW", gbw_results)
            total_count = len(gbw_results)
            fallback_info = {'source': 'GBW', 'used': True, 'retry_count': 0}
        
        else:
            # 两个都失败，尝试备用方案
            used_sources_other, fallback_info_other, total_other = EnhancedSmartSearcher._search_with_other_sources_streaming(
                keyword, downloader, output_dir, on_result
            )
            return used_sources_other, fallback_info_other, total_other
        
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
        
        # 并行搜索 ZBY 和 GBW
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(search_source, "ZBY", EnhancedSmartSearcher.DEFAULT_TIMEOUT): "ZBY",
                executor.submit(search_source, "GBW", EnhancedSmartSearcher.DEFAULT_TIMEOUT): "GBW",
            }
            
            for future in concurrent.futures.as_completed(futures, timeout=EnhancedSmartSearcher.DEFAULT_TIMEOUT * 1.5):
                source_name, results = future.result()
                
                if results is not None:
                    if source_name == "ZBY":
                        zby_results = results
                        sources_used.append("ZBY")
                    elif source_name == "GBW":
                        gbw_results = results
                        sources_used.append("GBW")
        
        # 智能合并结果
        if zby_results and gbw_results:
            # 两个源都成功，合并结果
            merged = StandardSearchMerger.merge_results(zby_results, gbw_results)
            return merged, sources_used, fallback_info
        elif zby_results:
            # 仅 ZBY 成功
            return zby_results, ["ZBY"], fallback_info
        elif gbw_results:
            # 仅 GBW 成功（降级）
            fallback_info = {'source': 'GBW', 'used': True, 'retry_count': 0}
            return gbw_results, ["GBW"], fallback_info
        else:
            # 两个都失败，尝试备用方案（其他源）
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
