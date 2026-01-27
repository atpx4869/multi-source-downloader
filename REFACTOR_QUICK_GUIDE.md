# Phase 1 快速参考指南

## 快速入门

### 添加新的数据源（3 步）

```python
# 1. 创建新源文件 sources/my_source.py
from .base import BaseSource, DownloadResult
from .registry import registry
from core.models import Standard
from pathlib import Path

@registry.register
class MySource(BaseSource):
    source_id = "my_source"      # 唯一标识
    source_name = "我的数据源"    # UI 显示名称
    priority = 5                  # 优先级（1=最高）
    
    def search(self, keyword: str, page_size: int = 20) -> list:
        # 实现搜索逻辑
        return []
    
    def download(self, std: Standard, outdir: Path) -> DownloadResult:
        # 实现下载逻辑
        logs = []
        try:
            # 下载...
            file_path = outdir / "example.pdf"
            return DownloadResult.ok(file_path, logs)
        except Exception as e:
            return DownloadResult.fail(str(e), logs)

# 2. sources/__init__.py 中添加导入
from . import my_source

# 3. 完成！现在可以在 UI 中使用
sources = registry.identify(keyword="某标准")  # 自动识别
```

---

## 核心 API

### SourceRegistry

```python
from sources import registry

# 获取特定源
gbw_source = registry.get_instance("gbw")

# 获取所有源（按优先级排序）
all_sources = registry.get_all_instances()

# 源识别（聪明的查询）
suitable_sources = registry.identify(
    url="https://...",
    keyword="GB 6675"
)

# 列出所有源信息（UI 用）
sources_info = registry.list_sources()
# 输出: [
#   {"id": "gbw", "name": "国标网", "priority": 1},
#   {"id": "by", "name": "标院内网", "priority": 2},
#   {"id": "zby", "name": "正规标准网", "priority": 3},
# ]
```

### DownloadResult

```python
from sources import DownloadResult
from pathlib import Path

# 成功情况
result = DownloadResult.ok(Path("file.pdf"), logs=["步骤1", "步骤2"])

# 失败情况
result = DownloadResult.fail("网络错误", logs=["尝试...失败"])

# 检查结果
if result.success:
    print(f"文件: {result.file_path}")
else:
    print(f"错误: {result.error}")
    for log in result.logs:
        print(f"  - {log}")
```

### BaseSource 接口

```python
from sources import BaseSource, DownloadResult
from core.models import Standard
from pathlib import Path

class MySource(BaseSource):
    source_id = "my"
    source_name = "名称"
    priority = 5
    
    @classmethod
    def can_handle(cls, url: str = None, keyword: str = None) -> bool:
        """判断是否可处理
        
        可选实现（默认 True）
        """
        return url and "my_domain" in url
    
    def search(self, keyword: str, page_size: int = 20) -> list:
        """搜索标准
        
        Args:
            keyword: 搜索关键词
            page_size: 返回数量
            
        Returns:
            Standard 对象列表
        """
        pass
    
    def download(self, std: Standard, outdir: Path) -> DownloadResult:
        """下载标准
        
        Args:
            std: Standard 对象
            outdir: 输出目录
            
        Returns:
            DownloadResult（必须）
            
        约定：
        - 所有错误都应在 logs 中记录
        - 不应抛出异常给上层
        - 必须创建输出目录（outdir.mkdir(parents=True, exist_ok=True)）
        """
        pass
```

---

## 常见使用场景

### 场景 1：搜索所有可用源

```python
from sources import registry

keyword = "GB 6675"
candidates = registry.identify(keyword=keyword)

for source_cls in candidates:
    source = source_cls()
    results = source.search(keyword)
    print(f"{source.source_name}: {len(results)} 条结果")
```

### 场景 2：下载并处理结果

```python
from sources import registry

std = search_results[0]  # 某个标准

# 按优先级尝试下载
for source_cls in registry.get_all():
    source = source_cls()
    result = source.download(std, Path("downloads"))
    
    if result.success:
        print(f"✅ 从 {source.source_name} 下载成功")
        print(f"   文件: {result.file_path}")
        break
    else:
        print(f"❌ {source.source_name} 失败: {result.error}")
```

### 场景 3：UI 源列表初始化

```python
from sources import registry

sources_info = registry.list_sources()

# 生成 QComboBox
for info in sources_info:
    combo_box.addItem(
        info["name"],  # 显示名称
        info["id"]     # 底层 ID
    )
```

---

## 旧代码迁移清单

如果你在其他地方有旧的代码，需要这样改：

### 旧方式
```python
from sources.gbw import GBWSource

src = GBWSource()
result = src.download(std, outdir, log_cb=callback)

if result:
    if isinstance(result, tuple):
        path, logs = result
    else:
        path = result
```

### 新方式
```python
from sources import registry

src = registry.get_instance("gbw")
result = src.download(std, outdir)

if result.success:
    path = result.file_path
    logs = result.logs
```

---

## 错误排查

### 问题：ImportError: cannot import name 'registry'

**解决**：确保你的导入是：
```python
from sources import registry  # ✅
# 或
from sources.registry import registry  # ✅

# ❌ 不要这样做
from sources.gbw import registry
```

### 问题：源没有注册

**检查**：
1. 源类是否有 `@registry.register` 装饰器
2. sources/__init__.py 是否导入了该源
3. 源类是否定义了 `source_id`

### 问题：download() 返回 None 但没有错误信息

**原因**：旧的 _download_impl() 返回了 None，但适配层没有捕获

**修复**：修改该源的 _download_impl，确保总是返回 (path, logs) 元组，或改为新接口

---

## 性能考虑

### 源实例化

```python
# ✅ 推荐：每次使用时新建（轻量级）
src = registry.get_instance("gbw")

# ⚠️ 避免：缓存实例（源状态可能不一致）
src = registry.get_instance("gbw")
# ... 长时间使用 ...
# 可能会有 session 状态问题
```

### 批量操作

```python
# ✅ 推荐：多线程并行搜索
import concurrent.futures

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(src().search, keyword): src.source_id
        for src in registry.get_all()
    }
    
    for future in concurrent.futures.as_completed(futures):
        source_id = futures[future]
        results = future.result()
        print(f"{source_id}: {len(results)} 条")
```

---

## 未来扩展点

### 计划中的改进

1. **search() 流式化**
   ```python
   # 现在: List[Standard]
   # 未来: Iterator[Standard]
   ```

2. **动态优先级**
   ```python
   # 现在: 静态 priority = 1
   # 未来: priority 基于实时可用性检测
   ```

3. **源配置化**
   ```python
   # 现在: 硬编码 source_id
   # 未来: 从配置文件读取（便于禁用某些源）
   ```

4. **插件化加载**
   ```python
   # 现在: 静态导入
   # 未来: 动态加载 .so/.pyd（支持自定义源包）
   ```

