# -*- coding: utf-8 -*-
"""
测试 ZBY API 响应，查看是否包含替代标准信息
"""
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sources.zby import ZBYSource

def test_zby_fields():
    """测试 ZBY API 字段"""
    print("=" * 70)
    print("测试 ZBY API 响应字段")
    print("=" * 70)
    
    zby = ZBYSource()
    results = zby.search("GB/T 3100", limit=3)
    
    if results:
        print(f"\n找到 {len(results)} 条结果\n")
        
        for i, std in enumerate(results[:3], 1):
            print(f"\n标准 {i}: {std.std_no}")
            print(f"  名称: {std.name}")
            print(f"  发布: {std.publish}")
            print(f"  实施: {std.implement}")
            print(f"  状态: {std.status}")
            
            # 打印 source_meta 中的所有字段
            if std.source_meta:
                print(f"\n  source_meta 字段:")
                meta = std.source_meta
                for key, value in meta.items():
                    if value and str(value).strip():
                        print(f"    {key}: {value}")
                
                # 查找可能的替代标准字段
                possible_keys = ['replace', 'supersede', 'alternative', 'instead', 
                               'abolish', 'cancel', 'new', 'revise', 'update',
                               'standardReplaceStandard', 'replaceStandard', 
                               'standardReplace', 'replaceBy', 'replacedBy']
                
                print(f"\n  可能的替代标准字段:")
                found = False
                for key in possible_keys:
                    if key in meta and meta[key]:
                        print(f"    ✓ {key}: {meta[key]}")
                        found = True
                
                if not found:
                    print(f"    未找到明确的替代标准字段")
            
            print("\n" + "-" * 70)
    else:
        print("未找到结果")

if __name__ == "__main__":
    test_zby_fields()
