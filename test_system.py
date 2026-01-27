# -*- coding: utf-8 -*-
"""
系统集成测试 - 验证重构后的系统是否正常工作
"""
import sys
import io

# 设置标准输出为UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def test_imports():
    """测试所有关键模块是否能正常导入"""
    print("="*70)
    print("测试 1: 模块导入")
    print("="*70)

    try:
        # 测试统一模型
        from core.unified_models import UnifiedStandard, Standard
        print("[OK] core.unified_models 导入成功")

        # 测试旧模型别名
        from core.models import Standard as LegacyStandard
        print("[OK] core.models (兼容层) 导入成功")

        # 测试API模型
        from api.models import StandardInfo, SearchResponse
        print("[OK] api.models 导入成功")

        # 测试核心模块
        from core.aggregated_downloader import AggregatedDownloader
        print("[OK] core.aggregated_downloader 导入成功")

        from core.smart_search import StandardSearchMerger
        print("[OK] core.smart_search 导入成功")

        from core.enhanced_search import EnhancedSmartSearcher
        print("[OK] core.enhanced_search 导入成功")

        # 测试数据源
        from sources.gbw import GBWSource
        from sources.zby import ZBYSource
        from sources.by import BYSource
        print("[OK] 所有数据源导入成功")

        print("\n[PASS] 所有模块导入测试通过\n")
        return True
    except Exception as e:
        print(f"\n[FAIL] 导入失败: {e}\n")
        return False


def test_model_compatibility():
    """测试模型兼容性"""
    print("="*70)
    print("测试 2: 模型兼容性")
    print("="*70)

    try:
        from core.unified_models import UnifiedStandard, Standard
        from core.models import Standard as LegacyStandard
        from api.models import StandardInfo

        # 验证别名
        assert Standard is UnifiedStandard, "Standard 应该是 UnifiedStandard 的别名"
        print("[OK] Standard = UnifiedStandard")

        assert LegacyStandard is UnifiedStandard, "LegacyStandard 应该是 UnifiedStandard 的别名"
        print("[OK] LegacyStandard = UnifiedStandard")

        assert StandardInfo is UnifiedStandard, "StandardInfo 应该是 UnifiedStandard 的别名"
        print("[OK] StandardInfo = UnifiedStandard")

        # 测试创建
        std = Standard(
            std_no="GB/T 1234-2024",
            name="测试标准",
            publish_date="2024-01-01",
            implement_date="2024-07-01"
        )
        print(f"[OK] 创建标准: {std.std_no}")

        # 测试向后兼容
        assert std.publish == "2024-01-01", "旧字段名 publish 应该映射到 publish_date"
        assert std.implement == "2024-07-01", "旧字段名 implement 应该映射到 implement_date"
        print("[OK] 向后兼容性正常")

        print("\n[PASS] 模型兼容性测试通过\n")
        return True
    except Exception as e:
        print(f"\n[FAIL] 兼容性测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_search_basic():
    """测试基本搜索功能"""
    print("="*70)
    print("测试 3: 基本搜索功能")
    print("="*70)

    try:
        from core.aggregated_downloader import AggregatedDownloader
        from core.unified_models import UnifiedStandard

        # 创建下载器（只启用GBW源，速度较快）
        downloader = AggregatedDownloader(enable_sources=["GBW"])
        print("[OK] 创建 AggregatedDownloader")

        # 执行搜索
        keyword = "GB/T 1.1"
        print(f"[OK] 搜索关键词: {keyword}")
        results = downloader.search(keyword, parallel=False)

        print(f"[OK] 搜索完成，找到 {len(results)} 条结果")

        # 验证结果类型
        if results:
            first = results[0]
            assert isinstance(first, UnifiedStandard), f"结果应该是 UnifiedStandard 类型，实际是 {type(first)}"
            print(f"[OK] 结果类型正确: UnifiedStandard")
            print(f"[OK] 第一条结果: {first.std_no} - {first.name[:30]}...")

            # 测试新方法
            label = first.display_label()
            print(f"[OK] display_label(): {label[:50]}...")

            filename = first.filename()
            print(f"[OK] filename(): {filename[:50]}...")
        else:
            print("[WARN]  搜索无结果（可能是网络问题）")

        print("\n[PASS] 基本搜索功能测试通过\n")
        return True
    except Exception as e:
        print(f"\n[FAIL] 搜索测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_smart_search():
    """测试智能搜索合并"""
    print("="*70)
    print("测试 4: 智能搜索合并")
    print("="*70)

    try:
        from core.smart_search import StandardSearchMerger
        from core.unified_models import UnifiedStandard

        # 创建测试数据
        zby_results = [
            UnifiedStandard(
                std_no="GB/T 1234-2020",
                name="测试标准A",
                publish_date="2020-01-01",
                sources=["ZBY"]
            )
        ]

        gbw_results = [
            UnifiedStandard(
                std_no="GB/T 1234-2020",
                name="测试标准A（更详细）",
                publish_date="2020-01-01",
                implement_date="2020-07-01",
                sources=["GBW"]
            )
        ]

        print("[OK] 创建测试数据")
        print(f"  - ZBY: {len(zby_results)} 条")
        print(f"  - GBW: {len(gbw_results)} 条")

        # 执行合并
        merged = StandardSearchMerger.merge_results(zby_results, gbw_results)
        print(f"[OK] 合并完成: {len(merged)} 条")

        # 验证合并结果
        assert len(merged) == 1, "应该合并为1条"
        result = merged[0]
        assert isinstance(result, UnifiedStandard), "结果应该是 UnifiedStandard"
        assert "ZBY" in result.sources and "GBW" in result.sources, "应该包含两个数据源"
        assert result.implement_date == "2020-07-01", "应该保留GBW的实施日期"

        print(f"[OK] 合并结果验证通过")
        print(f"  - 标准号: {result.std_no}")
        print(f"  - 数据源: {result.sources}")
        print(f"  - 实施日期: {result.implement_date}")

        print("\n[PASS] 智能搜索合并测试通过\n")
        return True
    except Exception as e:
        print(f"\n[FAIL] 合并测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("系统集成测试套件")
    print("="*70 + "\n")

    tests = [
        ("模块导入", test_imports),
        ("模型兼容性", test_model_compatibility),
        ("基本搜索", test_search_basic),
        ("智能合并", test_smart_search),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"[FAIL] 测试 '{name}' 异常: {e}")
            results.append((name, False))

    # 总结
    print("="*70)
    print("测试总结")
    print("="*70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "[PASS] 通过" if success else "[FAIL] 失败"
        print(f"{status}: {name}")

    print(f"\n通过率: {passed}/{total} ({passed*100//total}%)")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过！系统运行正常。\n")
    else:
        print(f"\n[WARN]  有 {total-passed} 个测试失败，请检查。\n")


if __name__ == "__main__":
    main()
