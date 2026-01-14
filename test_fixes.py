# -*- coding: utf-8 -*-
"""测试修复的两个问题"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.smart_search import StandardSearchMerger
from core.enhanced_search import EnhancedSmartSearcher
from core.aggregated_downloader import AggregatedDownloader

print("=" * 60)
print("测试1: GB标准识别（修复QB/T误识别问题）")
print("=" * 60)

test_cases = [
    ('GB/T 3100', True),
    ('gb/t 1950-2024', True),
    ('GB 28008', True),
    ('qb/t 1950-2024', False),
    ('QB/T 1950-2024', False),
    ('HB/T 123', False),
    ('JC/T 908-2013', False),
]

all_passed = True
for keyword, expected in test_cases:
    result = StandardSearchMerger.is_gb_standard(keyword)
    status = "✓" if result == expected else "✗"
    if result != expected:
        all_passed = False
    print(f"{status} {keyword:25s} -> GB标准: {str(result):5s} (期望: {expected})")

print(f"\n{'✅ 全部通过' if all_passed else '❌ 有失败'}")

print("\n" + "=" * 60)
print("测试2: 流式搜索回调功能")
print("=" * 60)

received_batches = []

def test_callback(source_name: str, results_batch: list):
    """测试回调函数"""
    received_batches.append({
        'source': source_name,
        'count': len(results_batch),
        'std_nos': [r['std_no'] for r in results_batch[:3]]  # 只显示前3个
    })
    print(f"  📥 收到 {source_name} 的 {len(results_batch)} 条结果")

try:
    print("\n正在测试流式搜索: GB/T 46489-2025")
    print("-" * 60)
    
    metadata = EnhancedSmartSearcher.search_with_callback(
        "GB/T 46489-2025",
        AggregatedDownloader(),
        "downloads",
        on_result=test_callback
    )
    
    print("-" * 60)
    print(f"✅ 搜索完成")
    print(f"  - 是否GB标准: {metadata['is_gb_standard']}")
    print(f"  - 使用的数据源: {', '.join(metadata['sources_used'])}")
    print(f"  - 总结果数: {metadata['total_results']}")
    print(f"  - 收到批次数: {len(received_batches)}")
    
    if len(received_batches) > 0:
        print(f"  ✓ 流式回调正常工作（收到 {len(received_batches)} 批数据）")
    else:
        print(f"  ✗ 流式回调未触发")
        
except Exception as e:
    print(f"❌ 测试出错: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
