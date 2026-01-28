# -*- coding: utf-8 -*-
"""
API 模块功能测试脚本

测试优化后的三个源（GBW、BY、ZBY）的功能和性能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import time
from typing import List, Dict, Any


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_section(title: str):
    """打印小节标题"""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}")


def test_source(source_name: str, source_class, test_keyword: str = "GB/T 3324") -> Dict[str, Any]:
    """
    测试单个数据源

    Args:
        source_name: 源名称
        source_class: 源类
        test_keyword: 测试关键词

    Returns:
        测试结果字典
    """
    result = {
        "source": source_name,
        "success": False,
        "error": None,
        "results_count": 0,
        "elapsed_time": 0,
        "sample_results": []
    }

    try:
        print(f"\n[*] 测试 {source_name} 源...")
        print(f"    关键词: {test_keyword}")

        # 创建源实例
        start_time = time.time()
        source = source_class()

        # 检查可用性
        if hasattr(source, 'is_available'):
            available = source.is_available()
            status_text = "[OK] 可用" if available else "[X] 不可用"
            print(f"    可用性: {status_text}")
            if not available:
                result["error"] = "源不可用"
                return result

        # 执行搜索
        print(f"    正在搜索...")
        results = source.search(test_keyword, page_size=5)
        elapsed = time.time() - start_time

        result["success"] = True
        result["results_count"] = len(results)
        result["elapsed_time"] = round(elapsed, 3)

        # 保存前3个结果作为样本
        for item in results[:3]:
            result["sample_results"].append({
                "std_no": item.std_no,
                "name": item.name[:50] + "..." if len(item.name) > 50 else item.name,
                "status": item.status,
                "has_pdf": item.has_pdf
            })

        print(f"    [OK] 搜索成功")
        print(f"    结果数量: {len(results)}")
        print(f"    耗时: {elapsed:.3f}s")

        # 显示样本结果
        if results:
            print(f"\n    样本结果:")
            for i, item in enumerate(results[:3], 1):
                print(f"    {i}. {item.std_no} - {item.name[:40]}...")
                pdf_text = "[OK]" if item.has_pdf else "[X]"
                print(f"       状态: {item.status} | PDF: {pdf_text}")

    except Exception as e:
        result["error"] = str(e)
        print(f"    [X] 测试失败: {e}")

    return result


def test_performance_monitor():
    """测试性能监控功能"""
    print_section("性能监控测试")

    try:
        from core.performance import get_performance_monitor

        monitor = get_performance_monitor()
        stats = monitor.get_stats()

        if not stats:
            print("[!] 暂无性能统计数据（需要先执行搜索操作）")
            return

        print("\n[*] 性能统计报告:")
        print(f"\n{'操作':<30} {'次数':<8} {'平均':<10} {'最小':<10} {'最大':<10} {'成功率':<10}")
        print("─" * 80)

        for key, data in sorted(stats.items()):
            print(f"{key:<30} {data['count']:<8} {data['avg_time']:<10.3f} "
                  f"{data['min_time']:<10.3f} {data['max_time']:<10.3f} {data['success_rate']:<10.1f}%")

        print("\n[OK] 性能监控功能正常")

    except ImportError:
        print("[!] 性能监控模块未安装")
    except Exception as e:
        print(f"[X] 性能监控测试失败: {e}")


def test_connection_pool():
    """测试连接池功能"""
    print_section("连接池测试")

    try:
        from core.performance import get_connection_pool_manager

        pool_manager = get_connection_pool_manager()

        # 创建测试 session
        session = pool_manager.create_session(timeout=10, max_retries=2)

        print("[OK] 连接池管理器创建成功")
        print(f"  连接池配置:")
        print(f"    - 连接数: {pool_manager.pool_connections}")
        print(f"    - 最大连接: {pool_manager.pool_maxsize}")
        print(f"  Session 配置:")
        print(f"    - 代理: 已禁用")
        print(f"    - 重试: 已启用")

        # 测试连接
        print("\n  测试连接...")
        try:
            resp = session.get("https://www.baidu.com", timeout=5)
            print(f"  [OK] 连接测试成功 (状态码: {resp.status_code})")
        except Exception as e:
            print(f"  [!] 连接测试失败: {e}")

    except ImportError:
        print("[!] 连接池模块未安装")
    except Exception as e:
        print(f"[X] 连接池测试失败: {e}")


def main():
    """主测试函数"""
    print_header("API 模块功能测试")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 测试结果汇总
    test_results = []

    # 测试 GBW 源
    print_section("GBW 源测试（国标网）")
    try:
        from sources.gbw import GBWSource
        result = test_source("GBW", GBWSource, "GB/T 3324")
        test_results.append(result)
    except Exception as e:
        print(f"[X] GBW 源导入失败: {e}")
        test_results.append({"source": "GBW", "success": False, "error": str(e)})

    # 测试 BY 源
    print_section("BY 源测试（标院内网）")
    try:
        from sources.by import BYSource
        result = test_source("BY", BYSource, "GB/T 3324")
        test_results.append(result)
    except Exception as e:
        print(f"[X] BY 源导入失败: {e}")
        test_results.append({"source": "BY", "success": False, "error": str(e)})

    # 测试 ZBY 源
    print_section("ZBY 源测试（正规宝）")
    try:
        from sources.zby import ZBYSource
        result = test_source("ZBY", ZBYSource, "GB/T 3324")
        test_results.append(result)
    except Exception as e:
        print(f"[X] ZBY 源导入失败: {e}")
        test_results.append({"source": "ZBY", "success": False, "error": str(e)})

    # 测试性能监控
    test_performance_monitor()

    # 测试连接池
    test_connection_pool()

    # 生成测试报告
    print_header("测试报告")

    # 过滤掉 None 结果
    test_results = [r for r in test_results if r is not None]

    success_count = sum(1 for r in test_results if r.get("success", False))
    total_count = len(test_results)

    print(f"\n总体结果: {success_count}/{total_count} 个源测试通过")
    print(f"\n详细结果:")
    print(f"{'源':<10} {'状态':<15} {'结果数':<10} {'耗时':<10} {'备注':<30}")
    print("─" * 80)

    for result in test_results:
        if not result or not isinstance(result, dict):  # 跳过 None 或无效结果
            continue
        try:
            status = "[OK] 成功" if result.get("success") else "[X] 失败"
            results_count = result.get("results_count", 0)
            elapsed = result.get("elapsed_time", 0)
            error = result.get("error", "")
            source = result.get("source", "Unknown")

            print(f"{source:<10} {status:<15} {results_count:<10} "
                  f"{elapsed:<10.3f} {error[:30]:<30}")
        except Exception as e:
            print(f"Error printing result: {e}")

    # 性能对比
    if success_count > 0:
        print(f"\n性能对比:")
        successful_results = [r for r in test_results if r and r.get("success", False)]
        if successful_results:
            avg_time = sum(r["elapsed_time"] for r in successful_results) / len(successful_results)
            fastest = min(successful_results, key=lambda x: x["elapsed_time"])
            slowest = max(successful_results, key=lambda x: x["elapsed_time"])

            print(f"  平均耗时: {avg_time:.3f}s")
            print(f"  最快: {fastest['source']} ({fastest['elapsed_time']:.3f}s)")
            print(f"  最慢: {slowest['source']} ({slowest['elapsed_time']:.3f}s)")

            # 优化效果评估
            print(f"\n优化效果评估:")
            if avg_time < 2.0:
                print(f"  [OK] 优秀 - 平均搜索时间 < 2秒")
            elif avg_time < 3.0:
                print(f"  [OK] 良好 - 平均搜索时间 < 3秒")
            elif avg_time < 5.0:
                print(f"  [!] 一般 - 平均搜索时间 < 5秒")
            else:
                print(f"  [X] 需要优化 - 平均搜索时间 > 5秒")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
