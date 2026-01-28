# -*- coding: utf-8 -*-
"""
ZBY 源下载问题诊断脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sources.zby import ZBYSource
from core.models import Standard


def test_zby_download():
    """测试 ZBY 源下载 GB/T 25623-2017"""

    print("=" * 80)
    print("ZBY 源下载诊断")
    print("=" * 80)

    # 创建 ZBY 源实例
    zby = ZBYSource()

    # 测试搜索
    print("\n[1] 搜索 GB/T 25623-2017...")
    results = zby.search("GB/T 25623-2017", page_size=5)

    if not results:
        print("   [X] 搜索失败，未找到结果")
        return

    print(f"   [OK] 找到 {len(results)} 条结果")

    # 显示搜索结果
    for i, item in enumerate(results, 1):
        print(f"\n   结果 {i}:")
        print(f"      标准号: {item.std_no}")
        print(f"      名称: {item.name[:50]}...")
        print(f"      状态: {item.status}")
        print(f"      has_pdf: {item.has_pdf}")
        print(f"      source_meta keys: {list(item.source_meta.keys()) if isinstance(item.source_meta, dict) else 'N/A'}")

        # 检查 meta 中的关键字段
        if isinstance(item.source_meta, dict):
            meta = item.source_meta
            print(f"      standardId: {meta.get('standardId', 'N/A')}")
            print(f"      hasPdf: {meta.get('hasPdf', 'N/A')}")
            print(f"      hasPreview: {meta.get('hasPreview', 'N/A')}")
            print(f"      pdfList: {meta.get('pdfList', 'N/A')}")
            print(f"      taskPdfList: {meta.get('taskPdfList', 'N/A')}")

    # 尝试下载第一个结果
    if results:
        print(f"\n[2] 尝试下载第一个结果...")
        item = results[0]
        output_dir = Path("test_downloads")
        output_dir.mkdir(exist_ok=True)

        print(f"   标准号: {item.std_no}")
        print(f"   has_pdf: {item.has_pdf}")
        print(f"   开始下载...")

        result = zby.download(item, output_dir)

        if result.success:
            print(f"   [OK] 下载成功: {result.file_path}")
        else:
            print(f"   [X] 下载失败: {result.error}")
            print(f"\n   日志:")
            for log in result.logs:
                print(f"      {log}")


if __name__ == "__main__":
    test_zby_download()
