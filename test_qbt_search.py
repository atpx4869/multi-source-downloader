# -*- coding: utf-8 -*-
"""测试QB/T搜索问题"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sources.zby import ZBYSource

print("=" * 60)
print("测试QB/T搜索过滤（不应返回GB标准）")
print("=" * 60)

test_cases = [
    ('qb/t 1950-2024', 'QB/T', 'QB'),
    ('QB/T 1950-2024', 'QB/T', 'QB'),
    ('gb/t 1950-2024', 'GB/T', 'GB'),
]

zby = ZBYSource()

for keyword, expected_type, expected_prefix in test_cases:
    print(f"\n测试关键词: {keyword}")
    print("-" * 60)
    
    try:
        results = zby.search(keyword)
        print(f"找到 {len(results)} 条结果")
        
        if results:
            for i, r in enumerate(results[:5], 1):  # 只显示前5个
                std_no = r.std_no
                name = r.name
                # 检查标准号前缀
                prefix_ok = std_no.upper().startswith(expected_prefix)
                status = "✓" if prefix_ok else "✗"
                print(f"  {status} [{i}] {std_no:25s} {name[:30]}")
            
            # 统计错误匹配
            wrong_matches = [r for r in results if not r.std_no.upper().startswith(expected_prefix)]
            if wrong_matches:
                print(f"\n  ❌ 发现 {len(wrong_matches)} 条错误匹配！")
                for r in wrong_matches[:3]:
                    print(f"     错误: {r.std_no}")
            else:
                print(f"\n  ✅ 所有结果匹配正确")
        else:
            print("  ℹ️  未找到结果")
            
    except Exception as e:
        print(f"  ❌ 搜索出错: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
