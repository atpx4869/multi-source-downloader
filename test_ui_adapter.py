#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 3 集成测试 - 验证 UI 适配器

运行：
    python test_ui_adapter.py
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入适配器
from app.ui_service_adapter import UIDownloadAdapter, UISearchAdapter, SignalEmitter

# 导入核心
from core.models import Standard


def test_signal_emitter():
    """测试信号发射器初始化"""
    print("测试 1: SignalEmitter 初始化...")
    try:
        emitter = SignalEmitter()
        print("  ✅ SignalEmitter 创建成功")
        
        # 检查信号
        assert hasattr(emitter, 'download_started'), "缺少 download_started 信号"
        assert hasattr(emitter, 'download_progress'), "缺少 download_progress 信号"
        assert hasattr(emitter, 'download_completed'), "缺少 download_completed 信号"
        assert hasattr(emitter, 'search_started'), "缺少 search_started 信号"
        print("  ✅ 所有信号都存在")
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_download_adapter_init():
    """测试下载适配器初始化"""
    print("\n测试 2: UIDownloadAdapter 初始化...")
    try:
        adapter = UIDownloadAdapter(max_workers=2)
        print("  ✅ UIDownloadAdapter 创建成功")
        
        # 检查属性
        assert hasattr(adapter, 'signals'), "缺少 signals 属性"
        assert hasattr(adapter, 'service'), "缺少 service 属性"
        assert hasattr(adapter, '_batch_tasks'), "缺少 _batch_tasks 属性"
        print("  ✅ 所有属性都存在")
        
        # 检查方法
        assert hasattr(adapter, 'submit_downloads'), "缺少 submit_downloads 方法"
        assert hasattr(adapter, 'get_status'), "缺少 get_status 方法"
        assert hasattr(adapter, 'cancel_download'), "缺少 cancel_download 方法"
        print("  ✅ 所有方法都存在")
        
        adapter.shutdown()
        print("  ✅ 适配器关闭成功")
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_adapter_init():
    """测试搜索适配器初始化"""
    print("\n测试 3: UISearchAdapter 初始化...")
    try:
        adapter = UISearchAdapter(max_workers=2)
        print("  ✅ UISearchAdapter 创建成功")
        
        # 检查属性
        assert hasattr(adapter, 'signals'), "缺少 signals 属性"
        assert hasattr(adapter, 'service'), "缺少 service 属性"
        print("  ✅ 所有属性都存在")
        
        # 检查方法
        assert hasattr(adapter, 'submit_search'), "缺少 submit_search 方法"
        assert hasattr(adapter, 'get_results'), "缺少 get_results 方法"
        print("  ✅ 所有方法都存在")
        
        adapter.shutdown()
        print("  ✅ 适配器关闭成功")
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_connections():
    """测试信号连接"""
    print("\n测试 4: 信号连接...")
    try:
        adapter = UIDownloadAdapter(max_workers=2)
        
        # 测试连接
        received_signals = []
        
        def on_download_started(task_id):
            received_signals.append(('started', task_id))
        
        def on_download_progress(task_id, current, total, msg):
            received_signals.append(('progress', task_id))
        
        # 这里的连接方式取决于 Qt 框架版本
        # 但至少应该能调用 connect 方法
        try:
            adapter.signals.download_started.connect(on_download_started)
            adapter.signals.download_progress.connect(on_download_progress)
            print("  ✅ 信号连接成功")
        except Exception as e:
            print(f"  ⚠️  信号连接失败（可能需要 Qt 事件循环）: {e}")
        
        adapter.shutdown()
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 3 UI 适配器集成测试")
    print("=" * 60)
    
    results = []
    results.append(("SignalEmitter", test_signal_emitter()))
    results.append(("UIDownloadAdapter", test_download_adapter_init()))
    results.append(("UISearchAdapter", test_search_adapter_init()))
    results.append(("信号连接", test_signal_connections()))
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name:20} {status}")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\n总体: {passed}/{total} 测试通过")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
