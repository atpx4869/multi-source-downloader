# -*- coding: utf-8 -*-
"""
统一数据模型测试

验证 UnifiedStandard 的所有功能：
1. 基本创建和属性访问
2. 向后兼容性（.publish vs .publish_date）
3. 序列化和反序列化
4. 模型转换（旧模型 <-> 新模型）
5. 实用方法
"""
import sys
import io
from pathlib import Path

# 设置 UTF-8 编码
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.unified_models import UnifiedStandard, Standard, convert_legacy_standards


def test_basic_creation():
    """测试基本创建"""
    print("\n" + "="*70)
    print("测试 1: 基本创建和属性访问")
    print("="*70)

    std = UnifiedStandard(
        std_no="GB/T 3324-2024",
        name="标准化工作导则 第1部分：标准化文件的结构和起草规则",
        publish_date="2024-03-15",
        implement_date="2024-10-01",
        status="即将实施",
        has_pdf=True,
        sources=["GBW", "ZBY"]
    )

    print(f"✓ 标准号: {std.std_no}")
    print(f"✓ 名称: {std.name}")
    print(f"✓ 发布日期: {std.publish_date}")
    print(f"✓ 实施日期: {std.implement_date}")
    print(f"✓ 状态: {std.status}")
    print(f"✓ 有PDF: {std.has_pdf}")
    print(f"✓ 数据源: {std.sources}")
    print(f"✓ 显示标签: {std.display_label()}")
    print(f"✓ 文件名: {std.filename()}")

    assert std.std_no == "GB/T 3324-2024"
    assert std.has_pdf == True
    assert len(std.sources) == 2
    print("\n✅ 基本创建测试通过")


def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n" + "="*70)
    print("测试 2: 向后兼容性（旧字段名）")
    print("="*70)

    std = UnifiedStandard(
        std_no="GB/T 1234-2020",
        name="测试标准",
        publish_date="2020-01-01",
        implement_date="2020-07-01"
    )

    # 测试旧字段名访问（.publish 和 .implement）
    print(f"✓ 新字段名 publish_date: {std.publish_date}")
    print(f"✓ 旧字段名 publish: {std.publish}")
    print(f"✓ 新字段名 implement_date: {std.implement_date}")
    print(f"✓ 旧字段名 implement: {std.implement}")

    assert std.publish == std.publish_date
    assert std.implement == std.implement_date

    # 测试通过旧字段名设置值
    std.publish = "2021-01-01"
    std.implement = "2021-07-01"

    print(f"✓ 设置后 publish_date: {std.publish_date}")
    print(f"✓ 设置后 implement_date: {std.implement_date}")

    assert std.publish_date == "2021-01-01"
    assert std.implement_date == "2021-07-01"

    print("\n✅ 向后兼容性测试通过")


def test_serialization():
    """测试序列化和反序列化"""
    print("\n" + "="*70)
    print("测试 3: 序列化和反序列化")
    print("="*70)

    original = UnifiedStandard(
        std_no="GB/T 5678-2023",
        name="另一个测试标准",
        publish_date="2023-05-20",
        implement_date="2024-01-01",
        status="现行",
        has_pdf=True,
        sources=["GBW", "BY", "ZBY"],
        source_meta={
            "GBW": {"id": "123", "hcno": "abc"},
            "BY": {"siid": "456"}
        }
    )

    # 转换为字典
    data = original.to_dict()
    print(f"✓ 转换为字典: {len(data)} 个字段")
    print(f"  - std_no: {data['std_no']}")
    print(f"  - sources: {data['sources']}")
    print(f"  - source_meta keys: {list(data['source_meta'].keys())}")

    # 从字典恢复
    restored = UnifiedStandard.from_dict(data)
    print(f"✓ 从字典恢复")
    print(f"  - std_no: {restored.std_no}")
    print(f"  - sources: {restored.sources}")
    print(f"  - has_pdf: {restored.has_pdf}")

    assert restored.std_no == original.std_no
    assert restored.sources == original.sources
    assert restored.has_pdf == original.has_pdf
    assert restored.source_meta == original.source_meta

    print("\n✅ 序列化测试通过")


def test_legacy_conversion():
    """测试与旧模型的转换"""
    print("\n" + "="*70)
    print("测试 4: 旧模型转换")
    print("="*70)

    # 模拟旧模型（现在使用新字段名，因为已经统一了）
    from core.models import Standard as LegacyStandard

    old_std = LegacyStandard(
        std_no="GB/T 9999-2022",
        name="旧模型测试标准",
        publish_date="2022-03-01",
        implement_date="2022-09-01",
        status="现行",
        has_pdf=True,
        sources=["GBW"]
    )

    print(f"✓ 旧模型创建: {old_std.std_no}")

    # 转换为新模型
    new_std = UnifiedStandard.from_legacy_standard(old_std)
    print(f"✓ 转换为新模型")
    print(f"  - std_no: {new_std.std_no}")
    print(f"  - publish_date: {new_std.publish_date}")
    print(f"  - implement_date: {new_std.implement_date}")

    assert new_std.std_no == old_std.std_no
    assert new_std.publish_date == old_std.publish
    assert new_std.implement_date == old_std.implement

    # 转换回旧模型
    back_to_old = new_std.to_legacy_standard()
    print(f"✓ 转换回旧模型")
    print(f"  - std_no: {back_to_old.std_no}")
    print(f"  - publish: {back_to_old.publish}")

    assert back_to_old.std_no == old_std.std_no
    assert back_to_old.publish == old_std.publish

    print("\n✅ 旧模型转换测试通过")


def test_utility_methods():
    """测试实用方法"""
    print("\n" + "="*70)
    print("测试 5: 实用方法")
    print("="*70)

    std = UnifiedStandard(
        std_no="GB/T 1111-2021",
        name="实用方法测试",
        sources=["GBW", "BY", "ZBY"],
        source_meta={
            "GBW": {"id": "111", "_has_pdf": True},
            "BY": {"siid": "222", "_has_pdf": False},
            "ZBY": {"uuid": "333"}
        },
        _display_source="GBW"
    )

    # 测试主要数据源
    primary = std.get_primary_source()
    print(f"✓ 主要数据源: {primary}")
    assert primary == "GBW"

    # 测试获取源元数据
    gbw_meta = std.get_source_meta("GBW")
    print(f"✓ GBW 元数据: {gbw_meta}")
    assert gbw_meta["id"] == "111"

    # 测试检查数据源
    has_by = std.has_source("BY")
    has_unknown = std.has_source("UNKNOWN")
    print(f"✓ 包含 BY: {has_by}")
    print(f"✓ 包含 UNKNOWN: {has_unknown}")
    assert has_by == True
    assert has_unknown == False

    # 测试排序
    std1 = UnifiedStandard(std_no="GB/T 1000-2020", name="A")
    std2 = UnifiedStandard(std_no="GB/T 2000-2020", name="B")
    std3 = UnifiedStandard(std_no="GB/T 500-2020", name="C")

    sorted_stds = sorted([std2, std1, std3])
    print(f"✓ 排序结果: {[s.std_no for s in sorted_stds]}")
    assert sorted_stds[0].std_no == "GB/T 500-2020"
    assert sorted_stds[1].std_no == "GB/T 1000-2020"
    assert sorted_stds[2].std_no == "GB/T 2000-2020"

    print("\n✅ 实用方法测试通过")


def test_alias():
    """测试别名"""
    print("\n" + "="*70)
    print("测试 6: 别名（Standard = UnifiedStandard）")
    print("="*70)

    # 使用别名创建
    std = Standard(
        std_no="GB/T 7777-2023",
        name="别名测试"
    )

    print(f"✓ 使用 Standard 别名创建: {std.std_no}")
    print(f"✓ 类型: {type(std).__name__}")

    assert isinstance(std, UnifiedStandard)
    assert std.std_no == "GB/T 7777-2023"

    print("\n✅ 别名测试通过")


def test_dict_compatibility():
    """测试字典兼容性（from_dict 支持旧字段名）"""
    print("\n" + "="*70)
    print("测试 7: 字典兼容性（旧字段名）")
    print("="*70)

    # 使用旧字段名的字典
    old_dict = {
        'std_no': 'GB/T 8888-2022',
        'name': '字典兼容性测试',
        'publish': '2022-01-01',      # 旧字段名
        'implement': '2022-07-01',    # 旧字段名
        'status': '现行',
        'has_pdf': True,
        'sources': ['GBW']
    }

    std = UnifiedStandard.from_dict(old_dict)
    print(f"✓ 从旧格式字典创建: {std.std_no}")
    print(f"  - publish_date: {std.publish_date}")
    print(f"  - implement_date: {std.implement_date}")

    assert std.publish_date == "2022-01-01"
    assert std.implement_date == "2022-07-01"

    # 使用新字段名的字典
    new_dict = {
        'std_no': 'GB/T 9999-2023',
        'name': '新格式测试',
        'publish_date': '2023-01-01',
        'implement_date': '2023-07-01',
        'status': '现行',
        'has_pdf': True,
        'sources': ['GBW']
    }

    std2 = UnifiedStandard.from_dict(new_dict)
    print(f"✓ 从新格式字典创建: {std2.std_no}")
    print(f"  - publish_date: {std2.publish_date}")

    assert std2.publish_date == "2023-01-01"

    print("\n✅ 字典兼容性测试通过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("统一数据模型测试套件")
    print("="*70)

    try:
        test_basic_creation()
        test_backward_compatibility()
        test_serialization()
        test_legacy_conversion()
        test_utility_methods()
        test_alias()
        test_dict_compatibility()

        print("\n" + "="*70)
        print("🎉 所有测试通过！")
        print("="*70)
        print("\n统一数据模型已准备就绪，可以开始迁移。")
        print("\n下一步：")
        print("1. 阅读 MIGRATION_GUIDE.md 了解迁移步骤")
        print("2. 逐步替换旧模型的使用")
        print("3. 运行现有测试确保兼容性")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
