#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 使用示例 - Demonstrates unified API usage
"""
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api import APIRouter, SourceType


def demo_search():
    """演示搜索功能"""
    print("\n" + "="*60)
    print("🔍 演示搜索功能")
    print("="*60)
    
    router = APIRouter()
    
    # 在单个源中搜索
    print("\n1️⃣  在 ZBY 中搜索 'GB/T 3324-2024':")
    response = router.search_single(SourceType.ZBY, "GB/T 3324-2024", limit=5)
    print(f"   源: {response.source.value}")
    print(f"   结果数: {response.count}")
    print(f"   耗时: {response.elapsed_time:.2f}s")
    if response.standards:
        for std in response.standards[:3]:
            print(f"   - {std.std_no}: {std.name[:30]}")
    if response.error:
        print(f"   ❌ 错误: {response.error}")
    
    # 在所有源中搜索
    print("\n2️⃣  在所有源中搜索 'GB/T 3324-2024':")
    results = router.search_all("GB/T 3324-2024", limit=5)
    for source_type, response in results.items():
        print(f"\n   {source_type.value}:")
        print(f"     结果数: {response.count}")
        print(f"     耗时: {response.elapsed_time:.2f}s")
        if response.standards:
            for std in response.standards[:2]:
                has_pdf = "✅" if std.has_pdf else "❌"
                print(f"       {has_pdf} {std.std_no}: {std.name[:30]}")
        if response.error:
            print(f"     ❌ 错误: {response.error}")


def demo_download():
    """演示下载功能"""
    print("\n" + "="*60)
    print("⬇️  演示下载功能")
    print("="*60)
    
    router = APIRouter()
    
    # 从特定源下载
    print("\n1️⃣  从 ZBY 下载 'GB/T 3324-2024':")
    
    def progress_callback(msg: str):
        print(f"   📝 {msg}")
    
    response = router.download(
        SourceType.ZBY,
        "GB/T 3324-2024",
        output_dir="downloads_api_demo",
        progress_callback=progress_callback
    )
    
    print(f"\n   状态: {response.status.value}")
    print(f"   耗时: {response.elapsed_time:.2f}s")
    if response.filepath:
        print(f"   文件: {response.filename}")
        print(f"   大小: {response.file_size} 字节")
    if response.error:
        print(f"   ❌ 错误: {response.error}")


def demo_health_check():
    """演示健康检查"""
    print("\n" + "="*60)
    print("🏥 演示健康检查")
    print("="*60)
    
    router = APIRouter()
    
    print("\n检查所有源的健康状态...")
    health = router.check_health()
    
    print(f"\n整体状态: {'✅ 全部健康' if health.all_healthy else '⚠️  存在异常'}")
    print(f"检查时间: {health.timestamp}")
    
    for source_health in health.sources:
        status = "✅ 可用" if source_health.available else "❌ 不可用"
        print(f"\n{source_health.source.value}: {status}")
        print(f"  响应时间: {source_health.response_time:.2f}ms")
        if source_health.error:
            print(f"  错误: {source_health.error}")


def demo_response_format():
    """演示响应格式（JSON）"""
    print("\n" + "="*60)
    print("📦 演示统一响应格式")
    print("="*60)
    
    router = APIRouter()
    
    # 搜索响应
    print("\n1️⃣  搜索响应格式:")
    response = router.search_single(SourceType.BY, "GB", limit=2)
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
    
    # 健康检查响应
    print("\n2️⃣  健康检查响应格式:")
    health = router.check_health()
    print(json.dumps(health.to_dict(), ensure_ascii=False, indent=2))


def main():
    """主函数"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  多源标准下载 - 统一 API 演示 ".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        # 演示搜索
        demo_search()
        
        # 演示健康检查
        demo_health_check()
        
        # 演示响应格式
        demo_response_format()
        
        # 演示下载（可选）
        # demo_download()
        
        print("\n" + "="*60)
        print("✅ 所有演示完成!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
