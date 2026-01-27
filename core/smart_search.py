# -*- coding: utf-8 -*-
"""
智能数据源合并器 - 结合 ZBY 和 GBW 的优势
对于 GB/T 和 GB 标准，同时查询 GBW（更完整的元数据），
然后合并结果，GBW 的数据作为补充和验证

已迁移到统一数据模型 (UnifiedStandard)
"""
import re
import concurrent.futures
from typing import List, Tuple, Optional, TYPE_CHECKING
from functools import lru_cache

if TYPE_CHECKING:
    from core.unified_models import UnifiedStandard

# 导入超时配置
try:
    from core.timeout_config import get_parallel_timeout
except ImportError:
    # 如果配置文件不存在，使用默认值
    def get_parallel_timeout(operation: str) -> int:
        return 15


# 预编译正则表达式 - 避免每次调用都重新编译
# 精确匹配 GB/T、GB、GBT，排除 QB/T、WB/T 等其他标准
_GB_PATTERN = re.compile(r'\b(?:GB/T|GB|GBT)\s*\d+', re.IGNORECASE)
_NORMALIZE_PATTERN = re.compile(r'[\s\-–—_/]')


class StandardSearchMerger:
    """智能标准搜索合并器"""
    
    @staticmethod
    def is_gb_standard(keyword: str) -> bool:
        """检测是否是 GB/T 或 GB 标准（不包括 QB/T 等其他标准）"""
        # 使用预编译的正则表达式，提升性能 ~3-5 倍
        # 使用 \b 单词边界确保精确匹配，避免 QB/T 被误识别
        kw_upper = keyword.upper()
        # 明确排除其他标准类型
        if any(prefix in kw_upper for prefix in ['QB/T', 'QBT', 'WB/T', 'WBT', 'HB/T', 'HBT', 'JC/T', 'JCT']):
            return False
        
        # 检查是否包含 GB/T、GB、GBT 前缀
        if _GB_PATTERN.search(keyword):
            return True
        
        # 启发式检测：纯数字标准号（如 6675.1）可能是 GB 标准
        # GB 标准号范围通常在 1-10000 范围内
        # 这样可以处理用户只输入标准号而不含前缀的情况（如在 UI 搜索框中输入 6675.1-）
        pure_num_match = re.match(r'^(\d+(?:\.\d+)?)', keyword.strip())
        if pure_num_match:
            try:
                std_num = int(pure_num_match.group(1).split('.')[0])
                # GB 标准号一般在 1-10000 范围内，可以认为是 GB 标准的可能性很高
                if 1 <= std_num <= 10000:
                    return True
            except (ValueError, IndexError):
                pass
        
        return False
    
    @staticmethod
    def merge_results(zby_results: List, gbw_results: List) -> List:
        """
        合并 ZBY 和 GBW 的搜索结果

        策略：
        1. 首先以 ZBY 的标准为主
        2. 对每个 ZBY 结果，查找匹配的 GBW 结果（按标准号匹配）
        3. 使用 GBW 的数据来补充和更新 ZBY 的字段（特别是状态、实施日期）
        4. GBW 的数据优先级：替代标准 > 状态 > 实施日期 > 发布日期

        Args:
            zby_results: ZBY 搜索结果 (List[UnifiedStandard])
            gbw_results: GBW 搜索结果 (List[UnifiedStandard])

        Returns:
            合并后的结果 (List[UnifiedStandard])
        """
        # 延迟导入避免循环依赖
        from core.unified_models import UnifiedStandard

        if not zby_results:
            return gbw_results

        if not gbw_results:
            return zby_results

        # 构建 GBW 查找表（优化：一次性扫描，避免存储空键）
        gbw_map = {}
        for result in gbw_results:
            key = StandardSearchMerger._normalize_std_no(result.std_no)
            if key:
                gbw_map[key] = result

        # 合并结果（优化：减少重复的字典操作和复制）
        merged = []
        used_gbw_keys = set()

        for zby_result in zby_results:
            zby_key = StandardSearchMerger._normalize_std_no(zby_result.std_no)

            # 查找对应的 GBW 结果
            gbw_result = gbw_map.get(zby_key) if zby_key else None

            if gbw_result:
                used_gbw_keys.add(zby_key)
                # 创建合并后的结果（使用 ZBY 为基础）
                # PDF 可用性判断：优先信任 GBW 的检测结果（更准确）
                # 只有当 GBW 没有检测到 PDF 时，才考虑 ZBY 的结果
                has_pdf_merged = gbw_result.has_pdf if gbw_result.has_pdf else zby_result.has_pdf

                merged_result = UnifiedStandard(
                    std_no=zby_result.std_no,
                    name=zby_result.name,
                    publish_date=zby_result.publish_date or gbw_result.publish_date,
                    implement_date=zby_result.implement_date or gbw_result.implement_date,
                    status=zby_result.status or gbw_result.status,
                    replace_std=zby_result.replace_std or gbw_result.replace_std,
                    has_pdf=has_pdf_merged,
                    sources=list(set(zby_result.sources + gbw_result.sources)),
                    source_meta={**zby_result.source_meta, **gbw_result.source_meta}
                )
            else:
                # 没有 GBW 对应项，直接使用 ZBY 结果
                merged_result = zby_result

            merged.append(merged_result)

        # 添加 GBW 独有的结果（ZBY 中没有的）
        for gbw_key, gbw_result in gbw_map.items():
            if gbw_key not in used_gbw_keys:
                merged.append(gbw_result)

        return merged
    
    @staticmethod
    @lru_cache(maxsize=512)
    def _normalize_std_no(std_no: str) -> str:
        """规范化标准号以便比较（带缓存，避免重复转换）"""
        if not std_no:
            return ""
        # 使用预编译的正则表达式，移除所有空格和特殊符号，转换为大写
        normalized = _NORMALIZE_PATTERN.sub('', std_no).upper()
        return normalized


class SmartSearchThread:
    """智能搜索线程 - 支持多源合并"""
    
    @staticmethod
    def smart_search(keyword: str, downloader, output_dir: str = "downloads"):
        """
        智能搜索：
        - 对于 GB/T 或 GB 标准，同时搜索 ZBY 和 GBW，然后合并
        - 对于其他标准，仅使用 ZBY

        Returns:
            (merged_results, (zby_count, gbw_count))
        """
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        from core.aggregated_downloader import AggregatedDownloader

        # 检测是否是 GB/T 或 GB 标准
        is_gb_std = StandardSearchMerger.is_gb_standard(keyword)

        if not is_gb_std:
            # 非 GB 标准，仅使用 ZBY
            return downloader.search(keyword), (0, 0)

        # GB/T 或 GB 标准，并行搜索 ZBY 和 GBW
        zby_results = []
        gbw_results = []

        def search_zby():
            try:
                dl = AggregatedDownloader(enable_sources=["ZBY"], output_dir=output_dir)
                items = dl.search(keyword, parallel=False)
                return items  # 直接返回 UnifiedStandard 列表
            except Exception as e:
                print(f"[SmartSearch] ZBY 搜索失败: {e}")
                return []

        def search_gbw():
            try:
                dl = AggregatedDownloader(enable_sources=["GBW"], output_dir=output_dir)
                items = dl.search(keyword, parallel=False)
                return items  # 直接返回 UnifiedStandard 列表
            except Exception as e:
                print(f"[SmartSearch] GBW 搜索失败: {e}")
                return []

        # 并行执行两个搜索，添加超时控制
        search_timeout = get_parallel_timeout("search_total")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_zby = executor.submit(search_zby)
            future_gbw = executor.submit(search_gbw)

            try:
                # 使用 as_completed 并设置总超时
                done, not_done = concurrent.futures.wait(
                    [future_zby, future_gbw],
                    timeout=search_timeout,
                    return_when=concurrent.futures.ALL_COMPLETED
                )

                # 获取结果
                if future_zby in done:
                    try:
                        zby_results = future_zby.result(timeout=0)
                    except Exception as e:
                        print(f"[SmartSearch] ZBY 搜索异常: {e}")
                        zby_results = []
                else:
                    print(f"[SmartSearch] ZBY 搜索超时 ({search_timeout}秒)")
                    zby_results = []

                if future_gbw in done:
                    try:
                        gbw_results = future_gbw.result(timeout=0)
                    except Exception as e:
                        print(f"[SmartSearch] GBW 搜索异常: {e}")
                        gbw_results = []
                else:
                    print(f"[SmartSearch] GBW 搜索超时 ({search_timeout}秒)")
                    gbw_results = []

                # 取消未完成的任务
                for future in not_done:
                    future.cancel()

            except Exception as e:
                print(f"[SmartSearch] 并行搜索异常: {e}")
                zby_results = []
                gbw_results = []

        # 合并结果
        merged = StandardSearchMerger.merge_results(zby_results, gbw_results)

        return merged, (len(zby_results), len(gbw_results))


if __name__ == "__main__":
    # 测试
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    from core.unified_models import UnifiedStandard

    print("=" * 70)
    print("智能搜索合并器测试")
    print("=" * 70)

    # 测试 GB/T 检测
    test_keywords = [
        "GB/T 3100",
        "GB 3100",
        "GBT3100",
        "HB 123",  # 非 GB
        "QB/T 456",  # 非 GB
    ]

    print("\nGB 标准检测:")
    for kw in test_keywords:
        is_gb = StandardSearchMerger.is_gb_standard(kw)
        print(f"  {kw:<20} -> {'是 GB 标准' if is_gb else '非 GB 标准'}")

    # 测试合并
    print("\n\n数据合并测试:")
    zby_data = [
        UnifiedStandard(std_no="GB/T 3100-2015", name="社会治安综合治理基础数据规范",
                       status="", implement_date="2016-03-01", sources=["ZBY"]),
        UnifiedStandard(std_no="GB/T 3101-2015", name="标准代号",
                       status="", implement_date="", sources=["ZBY"]),
    ]

    gbw_data = [
        UnifiedStandard(std_no="GB/T 3100-2015", name="社会治安综合治理基础数据规范",
                       status="现行", implement_date="2016-03-01", sources=["GBW"]),
        UnifiedStandard(std_no="GB/T 3200-2020", name="新标准",
                       status="即将实施", implement_date="2026-01-01", sources=["GBW"]),
    ]

    merged = StandardSearchMerger.merge_results(zby_data, gbw_data)

    print("\nZBY 数据数量:", len(zby_data))
    print("GBW 数据数量:", len(gbw_data))
    print("合并后数量:", len(merged))
    print("\n合并结果:")
    for item in merged:
        print(f"  {item.std_no}: 状态={item.status}, 来源={item.sources}")
