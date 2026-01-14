#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
标准查新功能测试脚本 - 验证发布日期、实施日期、状态字段的提取和显示
"""
import sys
import os
from pathlib import Path

# 设置环境变量以支持 UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 重新设置 stdout 的编码
if sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from core.aggregated_downloader import AggregatedDownloader


def test_zby_metadata_extraction():
    """测试 ZBY 源的元数据提取"""
    print("=" * 70)
    print("[TEST] 标准查新功能测试 - ZBY 数据源元数据验证")
    print("=" * 70)
    
    try:
        # 创建下载器实例
        print("\n[STEP 1] 初始化 AggregatedDownloader...")
        downloader = AggregatedDownloader(enable_sources=["ZBY"], output_dir="downloads")
        
        # 测试搜索
        test_keywords = ["GB/T 3100", "GB/T 9000"]
        
        for keyword in test_keywords:
            print("\n[STEP 2] 搜索关键词: '{}'".format(keyword))
            results = downloader.search(keyword, limit=5)
            
            if results:
                print("   [OK] 找到 {} 条结果".format(len(results)))
                print("\n   [DETAILS] 结果信息:")
                
                # 表格头部
                print("   {:15} {:20} {:12} {:12} {:12}".format('标准号', '名称', '发布日期', '实施日期', '状态'))
                print("   {} {} {} {} {}".format('-'*15, '-'*20, '-'*12, '-'*12, '-'*12))
                
                # 数据行
                for i, std in enumerate(results[:5], 1):
                    publish = std.publish or "未知"
                    implement = std.implement or "未知"
                    status = std.status or "未知"
                    
                    print("   {:15} {:20} {:12} {:12} {:12}".format(
                        std.std_no[:15], 
                        std.name[:20] if std.name else '',
                        publish[:12],
                        implement[:12],
                        status[:12]
                    ))
                    
                    # 详细信息
                    if std.publish or std.implement or std.status:
                        print("      [OK] 包含元数据: 发布日期={}, 实施日期={}, 状态={}".format(
                            std.publish, std.implement, std.status
                        ))
                    else:
                        print("      [WARN] 缺少元数据")
            else:
                print("   [FAIL] 未找到结果")
        
        print("\n" + "=" * 70)
        print("[RESULT] 测试完成！")
        print("=" * 70)
        
    except Exception as e:
        print("\n[FAIL] 测试失败: {}".format(e))
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = test_zby_metadata_extraction()
    sys.exit(0 if success else 1)
