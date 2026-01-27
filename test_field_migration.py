# -*- coding: utf-8 -*-
"""
全面测试字段名迁移 - 确保所有地方都使用新字段名
"""
import sys
import io

# 设置标准输出为UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def test_basic_creation():
    """测试基本创建"""
    print("="*70)
    print("测试 1: 基本创建")
    print("="*70)

    from core.models import Standard

    # 使用新字段名
    std = Standard(
        std_no="GB/T 1234-2024",
        name="测试标准",
        publish_date="2024-01-01",
        implement_date="2024-07-01",
        status="现行",
        sources=["GBW"],
        has_pdf=True
    )

    assert std.std_no == "GB/T 1234-2024"
    assert std.publish_date == "2024-01-01"
    assert std.implement_date == "2024-07-01"

    # 测试向后兼容
    assert std.publish == "2024-01-01"
    assert std.implement == "2024-07-01"

    print("[OK] 基本创建测试通过")
    print()
    return True


def test_clone_for_source():
    """测试 _clone_for_source 方法"""
    print("="*70)
    print("测试 2: _clone_for_source 方法")
    print("="*70)

    from core.models import Standard
    from core.aggregated_downloader import AggregatedDownloader

    std = Standard(
        std_no="GB/T 5678-2023",
        name="另一个标准",
        publish_date="2023-01-01",
        implement_date="2023-07-01",
        sources=["GBW", "ZBY"],
        has_pdf=True,
        source_meta={"GBW": {"id": "123"}, "ZBY": {"id": "456"}}
    )

    downloader = AggregatedDownloader()
    cloned = downloader._clone_for_source(std, "GBW")

    assert cloned.std_no == "GB/T 5678-2023"
    assert cloned.publish_date == "2023-01-01"
    assert cloned.implement_date == "2023-07-01"
    assert cloned.sources == ["GBW"]

    print("[OK] _clone_for_source 测试通过")
    print()
    return True


def test_from_dict():
    """测试从字典创建（模拟从数据库读取）"""
    print("="*70)
    print("测试 3: 从字典创建")
    print("="*70)

    from core.models import Standard

    # 模拟从数据库读取的旧格式数据
    obj_data = {
        "std_no": "GB/T 9999-2022",
        "name": "旧格式标准",
        "publish": "2022-01-01",  # 旧字段名
        "implement": "2022-07-01",  # 旧字段名
        "status": "现行",
        "sources": ["ZBY"],
        "has_pdf": True,
        "source_meta": {}
    }

    # 使用新字段名，但从旧字段名获取值
    std = Standard(
        std_no=obj_data.get("std_no", ""),
        name=obj_data.get("name", ""),
        publish_date=obj_data.get("publish", ""),
        implement_date=obj_data.get("implement", ""),
        status=obj_data.get("status", ""),
        sources=obj_data.get("sources", []),
        has_pdf=obj_data.get("has_pdf", False),
        source_meta=obj_data.get("source_meta", {})
    )

    assert std.std_no == "GB/T 9999-2022"
    assert std.publish_date == "2022-01-01"
    assert std.implement_date == "2022-07-01"

    print("[OK] 从字典创建测试通过")
    print()
    return True


def test_search_and_merge():
    """测试搜索和合并"""
    print("="*70)
    print("测试 4: 搜索和合并")
    print("="*70)

    from core.smart_search import StandardSearchMerger
    from core.unified_models import UnifiedStandard

    # 创建测试数据
    zby_results = [
        UnifiedStandard(
            std_no="GB/T 1111-2020",
            name="测试标准A",
            publish_date="2020-01-01",
            sources=["ZBY"]
        )
    ]

    gbw_results = [
        UnifiedStandard(
            std_no="GB/T 1111-2020",
            name="测试标准A（更详细）",
            publish_date="2020-01-01",
            implement_date="2020-07-01",
            sources=["GBW"]
        )
    ]

    # 执行合并
    merged = StandardSearchMerger.merge_results(zby_results, gbw_results)

    assert len(merged) == 1
    result = merged[0]
    assert result.std_no == "GB/T 1111-2020"
    assert result.publish_date == "2020-01-01"
    assert result.implement_date == "2020-07-01"
    assert "ZBY" in result.sources and "GBW" in result.sources

    print("[OK] 搜索和合并测试通过")
    print()
    return True


def test_all_sources():
    """测试所有数据源"""
    print("="*70)
    print("测试 5: 所有数据源")
    print("="*70)

    try:
        from sources.by import BYSource
        from sources.gbw import GBWSource
        from sources.zby import ZBYSource

        print("[OK] 所有数据源导入成功")

        # 测试创建实例
        by_source = BYSource()
        gbw_source = GBWSource()
        zby_source = ZBYSource()

        print("[OK] 所有数据源实例化成功")
        print()
        return True
    except Exception as e:
        print(f"[FAIL] 数据源测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("字段名迁移全面测试")
    print("="*70 + "\n")

    tests = [
        ("基本创建", test_basic_creation),
        ("_clone_for_source", test_clone_for_source),
        ("从字典创建", test_from_dict),
        ("搜索和合并", test_search_and_merge),
        ("所有数据源", test_all_sources),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"[FAIL] 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
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
        print("\n[SUCCESS] 所有测试通过！字段名迁移完成。\n")
        return 0
    else:
        print(f"\n[WARN] 有 {total-passed} 个测试失败，请检查。\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
