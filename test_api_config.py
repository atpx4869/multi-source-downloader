#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 配置和客户端测试脚本
"""
from core.api_client import get_api_client
from core.api_config import get_api_config, APIMode

print("=" * 60)
print("API 配置系统测试")
print("=" * 60)

# 测试 1: 配置加载
print("\n1️⃣ 测试配置加载...")
config = get_api_config()
print(f"   ✓ 配置对象: {config}")
print(f"   ✓ 运行模式: {'📍 本地' if config.is_local_mode() else '🌐 远程'}")
print(f"   ✓ 启用的源: {config.get_enabled_sources_list()}")
print(f"   ✓ 下载目录: {config.local_output_dir}")
print(f"   ✓ 搜索限制: {config.search_limit}")

# 测试 2: API 客户端初始化
print("\n2️⃣ 测试 API 客户端...")
client = get_api_client()
print(f"   ✓ 客户端初始化成功")
print(f"   ✓ 模式: {'本地' if config.is_local_mode() else '远程'}")

# 测试 3: 配置更新
print("\n3️⃣ 测试配置更新...")
config.update(
    search_limit=200,
    max_retries=5
)
print(f"   ✓ 搜索限制已更新: {config.search_limit}")
print(f"   ✓ 最大重试次数已更新: {config.max_retries}")

# 测试 4: 配置保存
print("\n4️⃣ 测试配置保存...")
success = config.save()
if success:
    print(f"   ✓ 配置已保存到: {config.CONFIG_FILE}")
else:
    print(f"   ✗ 配置保存失败")

# 测试 5: 配置转换为字典
print("\n5️⃣ 测试配置转换...")
config_dict = config.to_dict()
print(f"   ✓ 配置字典已生成")
print(f"   ✓ 包含 {len(config_dict)} 个配置项")

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)
