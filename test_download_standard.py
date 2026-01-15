#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试下载特定标准 GB/T28478-2024
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.aggregated_downloader import AggregatedDownloader
from core.models import Standard


def test_download_standard(std_no: str = "GB/T28478-2024"):
    """测试下载指定标准"""
    print("=" * 70)
    print(f"标准下载测试: {std_no}")
    print("=" * 70)
    
    # 1. 创建搜索关键字
    keyword = std_no.replace("/", "").replace("T", "")  # GB/T28478-2024 -> GB28478-2024 或 2024
    print(f"\n[1] 搜索标准: {std_no} (关键词: {keyword})")
    
    try:
        # 2. 获取聚合下载器
        downloader = AggregatedDownloader(output_dir="test_downloads", enable_sources=None)
        
        # 3. 搜索标准
        print("\n[2] 在三个源中搜索...")
        search_results = downloader.search(keyword)
        
        if not search_results:
            print("   ❌ 未找到相关标准")
            return False
        
        print(f"   OK 找到 {len(search_results)} 条结果")
        
        # 查找目标标准 - 优先精确匹配，再模糊匹配
        target = None
        
        # 策略 1: 精确匹配编号（不考虑格式）
        std_no_normalized = std_no.replace("/", "").replace("-", "").replace("T", "").lower()
        for item in search_results:
            std_no_value = item.std_no if hasattr(item, 'std_no') else item.get("std_no", "")
            item_normalized = std_no_value.replace("/", "").replace("-", "").replace("T", "").lower()
            if std_no_normalized in item_normalized or item_normalized in std_no_normalized:
                target = item
                break
        
        # 策略 2: 如果未找到精确匹配，尝试找包含完整编号的
        if not target:
            for item in search_results:
                std_no_value = item.std_no if hasattr(item, 'std_no') else item.get("std_no", "")
                # 提取数字部分进行比较
                import re
                target_digits = re.findall(r'\d+', std_no)
                item_digits = re.findall(r'\d+', std_no_value)
                if target_digits and target_digits == item_digits[:len(target_digits)]:
                    target = item
                    break
        
        if not target:
            # 如果仍未找到，显示搜索结果让用户选择
            print("\n   搜索结果:")
            for i, item in enumerate(search_results[:10], 1):
                std_no_value = item.std_no if hasattr(item, 'std_no') else item.get("std_no", "")
                name_value = item.name if hasattr(item, 'name') else item.get("name", "")
                sources = item.sources if hasattr(item, 'sources') else item.get("sources", [])
                print(f"      {i}. {std_no_value} - {name_value}")
                print(f"         来源: {', '.join(sources)}")
            
            target = search_results[0]  # 默认选择第一个
            std_no_value = target.std_no if hasattr(target, 'std_no') else target.get("std_no", "")
            print(f"\n   WARNING: 未找到精确匹配，使用第一条: {std_no_value}")
        else:
            std_no_value = target.std_no if hasattr(target, 'std_no') else target.get("std_no", "")
            name_value = target.name if hasattr(target, 'name') else target.get("name", "")
            sources = target.sources if hasattr(target, 'sources') else target.get("sources", [])
            print(f"   OK 找到目标标准: {std_no_value} - {name_value}")
            print(f"      来源: {', '.join(sources)}")
        
        # 4. 下载
        print("\n[3] 开始下载...")
        output_dir = Path("./test_downloads")
        output_dir.mkdir(exist_ok=True)
        
        # 获取源偏好设置
        prefer_sources = getattr(test_download_standard, '_prefer_sources', None)
        if prefer_sources:
            print(f"   仅使用源: {prefer_sources}")
        
        file_path, logs = downloader.download(target, prefer_order=prefer_sources or ["GBW", "BY", "ZBY"])
        
        if file_path:
            print(f"   OK 下载成功!")
            print(f"      文件: {Path(file_path).name}")
            print(f"      大小: {Path(file_path).stat().st_size / (1024*1024):.2f} MB")
            
            # 显示详细日志
            if logs:
                print("\n   下载日志:")
                for log in logs[-5:]:  # 显示最后 5 条日志
                    print(f"      {log}")
            
            return True
        else:
            print(f"   FAIL 下载失败")
            if logs:
                print("\n   错误日志:")
                for log in logs[-5:]:
                    print(f"      {log}")
            return False
    
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="标准下载测试")
    parser.add_argument("std", nargs="?", default="GB/T28478-2024", help="标准编号 (默认: GB/T28478-2024)")
    parser.add_argument("--source", type=str, default=None, help="指定源 (GBW|BY|ZBY，默认尝试全部)")
    args = parser.parse_args()
    
    # 设置源偏好
    if args.source:
        test_download_standard._prefer_sources = [args.source.upper()]
    
    success = test_download_standard(args.std)
    
    print("\n" + "=" * 70)
    if success:
        print("OK - 下载测试成功")
    else:
        print("FAIL - 下载测试失败")
    print("=" * 70)
    
    sys.exit(0 if success else 1)
