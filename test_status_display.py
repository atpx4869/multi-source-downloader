# -*- coding: utf-8 -*-
"""测试状态显示"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sources.zby import ZBYSource

print("=" * 60)
print("测试状态码映射（应显示中文而非数字）")
print("=" * 60)

test_keywords = [
    'QB/T 2280',
    'GB/T 3920',
]

zby = ZBYSource()

for keyword in test_keywords:
    print(f"\n搜索: {keyword}")
    print("-" * 60)
    
    try:
        results = zby.search(keyword)
        print(f"找到 {len(results)} 条结果\n")
        
        for i, r in enumerate(results[:5], 1):
            status_display = r.status if r.status else '(无)'
            publish_display = r.publish if r.publish else '(无)'
            implement_display = r.implement if r.implement else '(无)'
            
            # 检查状态是否是中文
            is_chinese = any('\u4e00' <= c <= '\u9fff' for c in status_display)
            status_mark = "✓" if is_chinese else "✗"
            
            print(f"{status_mark} [{i}] {r.std_no:25s}")
            print(f"      状态: {status_display:10s} 发布: {publish_display:12s} 实施: {implement_display}")
            
    except Exception as e:
        print(f"❌ 搜索出错: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
