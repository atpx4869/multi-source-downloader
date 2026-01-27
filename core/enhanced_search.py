# -*- coding: utf-8 -*-
"""
增强型智能搜索器 - 多线程 + 容错 + 重试机制

已迁移到统一数据模型 (UnifiedStandard)
简化版本：移除重复的字典转换逻辑
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
    def search_with_fallback(keyword: str, downloader, output_dir: str = "downloads") -> Tuple[List, Dict]:
        """
        智能搜索 - 根据标准类型选择数据源，支持多线程和自动降级

        Args:
            keyword: 搜索关键词
            downloader: AggregatedDownloader 实例
            output_dir: 输出目录

        Returns:
            (results, metadata) 元组
            - results: 搜索结果列表 (List[UnifiedStandard])
            - metadata: 搜索元数据字典
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
    def _search_gb_standard(keyword: str, downloader, output_dir: str) -> Tuple[List, List[str], Dict]:
        """
        搜索 GB/T 或 GB 标准 - 优先并行搜索 ZBY + GBW，失败时兜底

        返回: (results, sources_used, fallback_info)
        """
        from core.aggregated_downloader import AggregatedDownloader

        fallback_info = {'source': None, 'used': False, 'retry_count': 0}
        zby_results = []
        gbw_results = []
        sources_used = []

        def search_source(source_name: str):
            """搜索单个数据源"""
            try:
                client = AggregatedDownloader(enable_sources=[source_name], output_dir=output_dir)
                items = client.search(keyword, parallel=False)
                return source_name, items
            except Exception as e:
                return source_name, None  # None 表示失败

        # 并行搜索 ZBY 和 GBW
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(search_source, "ZBY"): "ZBY",
                executor.submit(search_source, "GBW"): "GBW",
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
    def _search_non_gb_standard(keyword: str, downloader, output_dir: str) -> Tuple[List, List[str], Dict]:
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

            if items:
                return items, ["ZBY"], fallback_info
        except Exception as e:
            pass

        # ZBY 失败或无结果，尝试兜底方案
        return EnhancedSmartSearcher._search_with_other_sources(keyword, downloader, output_dir)

    @staticmethod
    def _search_with_other_sources(keyword: str, downloader, output_dir: str) -> Tuple[List, List[str], Dict]:
        """
        兜底方案：依次尝试其他数据源（GBW, BY 等）

        返回: (results, sources_used, fallback_info)
        """
        from core.aggregated_downloader import AggregatedDownloader

        fallback_sources = ["GBW", "BY"]  # 备用数据源的优先级

        for retry_count, fallback_source in enumerate(fallback_sources):
            try:
                client = AggregatedDownloader(enable_sources=[fallback_source], output_dir=output_dir)
                items = client.search(keyword, parallel=False)

                if items:
                    fallback_info = {
                        'source': fallback_source,
                        'used': True,
                        'retry_count': retry_count
                    }
                    return items, [fallback_source], fallback_info
            except Exception as e:
                continue

        # 所有来源都失败或无结果
        return [], [], {'source': None, 'used': False, 'retry_count': len(fallback_sources)}
