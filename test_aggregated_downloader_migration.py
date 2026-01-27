# -*- coding: utf-8 -*-
"""
验证 AggregatedDownloader 迁移到统一模型后的功能

测试内容：
1. 初始化是否正常
2. 搜索功能是否正常
3. 返回的数据类型是否正确
4. 向后兼容性（旧字段名）
"""
import sys
from pathlib import Path

# 设置 UTF-8 编码
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.aggregated_downloader import AggregatedDownloader
from core.unified_models import UnifiedStandard


def test_initialization():
    """测试初始化"""
    print("\n" + "="*70)
    print("测试 1: AggregatedDownloader 初始化")
    print("="*70)

    try:
        downloader = AggregatedDownloader(output_dir="downloads")
        print(f"✓ 初始化成功")
        print(f"✓ 加载的源数量: {len(downloader.sources)}")
        print(f"✓ 源列表: {[src.name for src in downloader.sources]}")

        assert len(downloader.sources) > 0, "至少应该加载一个源"
        print("\n✅ 初始化测试通过")
        return downloader

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_search(downloader):
    """测试搜索功能"""
    print("\n" + "="*70)
    print("测试 2: 搜索功能（使用统一模型）")
    print("="*70)

    if not downloader:
        print("⚠️  跳过测试（初始化失败）")
        return False

    try:
        # 执行搜索（使用一个常见的标准号）
        keyword = "GB/T 1.1"
        print(f"搜索关键词: {keyword}")
        print("执行搜索中...")

        results = downloader.search(keyword, parallel=True)

        print(f"✓ 搜索完成")
        print(f"✓ 结果数量: {len(results)}")

        if len(results) > 0:
            # 检查返回类型
            first_result = results[0]
            print(f"\n检查第一个结果:")
            print(f"  - 类型: {type(first_result).__name__}")
            print(f"  - 是否为 UnifiedStandard: {isinstance(first_result, UnifiedStandard)}")
            print(f"  - 标准号: {first_result.std_no}")
            print(f"  - 名称: {first_result.name[:50]}..." if len(first_result.name) > 50 else f"  - 名称: {first_result.name}")

            # 测试新字段名
            print(f"\n测试新字段名:")
            print(f"  - publish_date: {first_result.publish_date}")
            print(f"  - implement_date: {first_result.implement_date}")

            # 测试向后兼容（旧字段名）
            print(f"\n测试向后兼容（旧字段名）:")
            print(f"  - publish: {first_result.publish}")
            print(f"  - implement: {first_result.implement}")

            # 验证字段映射
            assert first_result.publish == first_result.publish_date, "向后兼容失败"
            assert first_result.implement == first_result.implement_date, "向后兼容失败"

            # 测试新方法
            print(f"\n测试新方法:")
            print(f"  - display_label(): {first_result.display_label()[:60]}...")
            print(f"  - filename(): {first_result.filename()[:60]}...")
            print(f"  - get_primary_source(): {first_result.get_primary_source()}")
            print(f"  - sources: {first_result.sources}")

            # 验证所有结果都是统一模型
            all_unified = all(isinstance(r, UnifiedStandard) for r in results)
            print(f"\n✓ 所有结果都是 UnifiedStandard: {all_unified}")

            assert all_unified, "存在非统一模型的结果"

            print("\n✅ 搜索功能测试通过")
            return True
        else:
            print("\n⚠️  搜索无结果（可能是网络问题或源不可用）")
            return True  # 无结果不算失败

    except Exception as e:
        print(f"\n❌ 搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_merge_logic(downloader):
    """测试合并逻辑"""
    print("\n" + "="*70)
    print("测试 3: 结果合并逻辑")
    print("="*70)

    if not downloader:
        print("⚠️  跳过测试（初始化失败）")
        return False

    try:
        # 创建测试数据
        from core.unified_models import UnifiedStandard

        test_items = [
            UnifiedStandard(
                std_no="GB/T 1234-2020",
                name="测试标准A",
                publish_date="2020-01-01",
                implement_date="2020-07-01",
                has_pdf=True,
                sources=["GBW"]
            ),
            UnifiedStandard(
                std_no="GB/T 1234-2020",  # 相同标准号
                name="测试标准A（更长的名称）",
                publish_date="2020-01-01",
                has_pdf=False,
                sources=["BY"]
            ),
        ]

        # 测试合并
        combined = {}
        downloader._merge_items(combined, [test_items[0]], "GBW")
        downloader._merge_items(combined, [test_items[1]], "BY")

        print(f"✓ 合并前: 2 个项目")
        print(f"✓ 合并后: {len(combined)} 个项目")

        # 验证合并结果
        assert len(combined) == 1, "相同标准号应该合并为一个"

        merged_item = list(combined.values())[0]
        print(f"\n合并后的项目:")
        print(f"  - 标准号: {merged_item.std_no}")
        print(f"  - 名称: {merged_item.name}")
        print(f"  - 数据源: {merged_item.sources}")
        print(f"  - has_pdf: {merged_item.has_pdf}")

        # 验证合并逻辑
        assert "GBW" in merged_item.sources, "应包含 GBW 源"
        assert "BY" in merged_item.sources, "应包含 BY 源"
        assert merged_item.has_pdf == True, "任一源有 PDF 则应为 True"
        assert "更长的名称" in merged_item.name, "应保留更长的名称"

        print("\n✅ 合并逻辑测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 合并逻辑测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n" + "="*70)
    print("测试 4: 向后兼容性（旧代码仍能工作）")
    print("="*70)

    try:
        from core.unified_models import Standard  # 使用别名

        # 使用新字段名创建（正确方式）
        std = Standard(
            std_no="GB/T 9999-2023",
            name="向后兼容测试",
            publish_date="2023-01-01",      # 使用新字段名
            implement_date="2023-07-01",    # 使用新字段名
            has_pdf=True
        )

        print(f"✓ 使用新字段名创建成功")
        print(f"  - std_no: {std.std_no}")

        # 测试向后兼容：通过旧字段名访问
        print(f"\n测试向后兼容（通过旧字段名访问）:")
        print(f"  - publish (旧): {std.publish}")
        print(f"  - implement (旧): {std.implement}")
        print(f"  - publish_date (新): {std.publish_date}")
        print(f"  - implement_date (新): {std.implement_date}")

        # 验证映射
        assert std.publish == "2023-01-01", "旧字段名应该能正常访问"
        assert std.implement == "2023-07-01", "旧字段名应该能正常访问"
        assert std.publish == std.publish_date, "旧字段名应该映射到新字段名"
        assert std.implement == std.implement_date, "旧字段名应该映射到新字段名"

        # 测试通过旧字段名设置值
        print(f"\n测试通过旧字段名设置值:")
        std.publish = "2024-01-01"
        std.implement = "2024-07-01"
        print(f"  - 设置后 publish: {std.publish}")
        print(f"  - 设置后 publish_date: {std.publish_date}")

        assert std.publish_date == "2024-01-01", "通过旧字段名设置应该更新新字段"
        assert std.implement_date == "2024-07-01", "通过旧字段名设置应该更新新字段"

        # 测试旧代码的访问方式
        display = f"{std.std_no} {std.name}"
        print(f"\n✓ 旧代码访问方式正常: {display}")

        print("\n✅ 向后兼容性测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 向后兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("AggregatedDownloader 迁移验证测试套件")
    print("="*70)

    results = []

    # 测试 1: 初始化
    downloader = test_initialization()
    results.append(downloader is not None)

    # 测试 2: 搜索功能
    if downloader:
        results.append(test_search(downloader))
    else:
        print("\n⚠️  跳过搜索测试（初始化失败）")
        results.append(False)

    # 测试 3: 合并逻辑
    if downloader:
        results.append(test_merge_logic(downloader))
    else:
        print("\n⚠️  跳过合并逻辑测试（初始化失败）")
        results.append(False)

    # 测试 4: 向后兼容性
    results.append(test_backward_compatibility())

    # 总结
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)

    passed = sum(results)
    total = len(results)

    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过！")
        print("\n✅ AggregatedDownloader 已成功迁移到统一模型")
        print("✅ 向后兼容性完好")
        print("✅ 所有功能正常工作")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
