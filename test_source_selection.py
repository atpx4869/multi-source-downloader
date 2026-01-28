#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试源选择功能 - 验证仅选择GBW时只搜索GBW源
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.enhanced_search import EnhancedSmartSearcher
from core import AggregatedDownloader


def test_gbw_only():
    """测试仅选择GBW源的搜索"""
    print("=" * 60)
    print("测试：仅选择GBW源")
    print("=" * 60)
    
    keyword = "GB/T 3324"
    sources = ["GBW"]  # 仅选择GBW
    
    collected_sources = set()
    
    def on_result(source_name, results_batch):
        """收集搜索到的源"""
        if results_batch:
            collected_sources.add(source_name)
            print(f"✓ 收到 {source_name} 的 {len(results_batch)} 条结果")
    
    try:
        downloader = AggregatedDownloader(enable_sources=sources)
        metadata = EnhancedSmartSearcher.search_with_callback(
            keyword,
            downloader,
            output_dir="downloads",
            on_result=on_result,
            sources=sources
        )
        
        print(f"\n搜索统计:")
        print(f"  - 关键词: {keyword}")
        print(f"  - 指定源: {sources}")
        print(f"  - 实际使用的源: {metadata['sources_used']}")
        print(f"  - 收到的源: {collected_sources}")
        print(f"  - 总结果数: {metadata['total_results']}")
        
        # 验证是否只搜索了指定的源
        if "MERGED" in collected_sources:
            # MERGED 是合并后的结果
            collected_sources.discard("MERGED")
        
        if collected_sources.issubset(set(sources)) or collected_sources.issubset({"MERGED"}):
            print("\n✅ 测试通过：只搜索了指定的源！")
            return True
        else:
            print(f"\n❌ 测试失败：搜索了未指定的源 {collected_sources - set(sources)}")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_sources():
    """测试多个源的搜索"""
    print("\n" + "=" * 60)
    print("测试：选择GBW和BY源")
    print("=" * 60)
    
    keyword = "GB/T 3324"
    sources = ["GBW", "BY"]  # 选择GBW和BY
    
    collected_sources = set()
    
    def on_result(source_name, results_batch):
        """收集搜索到的源"""
        if results_batch:
            collected_sources.add(source_name)
            print(f"✓ 收到 {source_name} 的 {len(results_batch)} 条结果")
    
    try:
        downloader = AggregatedDownloader(enable_sources=sources)
        metadata = EnhancedSmartSearcher.search_with_callback(
            keyword,
            downloader,
            output_dir="downloads",
            on_result=on_result,
            sources=sources
        )
        
        print(f"\n搜索统计:")
        print(f"  - 关键词: {keyword}")
        print(f"  - 指定源: {sources}")
        print(f"  - 实际使用的源: {metadata['sources_used']}")
        print(f"  - 收到的源: {collected_sources}")
        print(f"  - 总结果数: {metadata['total_results']}")
        
        # 验证是否只搜索了指定的源
        if "MERGED" in collected_sources:
            collected_sources.discard("MERGED")
        
        if collected_sources.issubset(set(sources)) or collected_sources.issubset({"MERGED"}):
            print("\n✅ 测试通过：只搜索了指定的源！")
            return True
        else:
            print(f"\n❌ 测试失败：搜索了未指定的源 {collected_sources - set(sources)}")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("标准下载器 - 源选择功能测试\n")
    
    test1 = test_gbw_only()
    test2 = test_multiple_sources()
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"仅GBW源测试: {'✅ 通过' if test1 else '❌ 失败'}")
    print(f"多源测试: {'✅ 通过' if test2 else '❌ 失败'}")
    
    if test1 and test2:
        print("\n✅ 所有测试通过！源选择功能正常工作。")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败。")
        sys.exit(1)
