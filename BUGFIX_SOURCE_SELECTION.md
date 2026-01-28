# 源选择功能修复 - 修改日志

## 问题描述
用户在主界面选择仅搜索GBW源，但搜索时仍然会三个源一起搜（GBW、BY、ZBY）。

## 根本原因分析
1. **SearchThread.run()** 方法中调用 `EnhancedSmartSearcher.search_with_callback()` 时，没有传递 `sources` 参数
2. **EnhancedSmartSearcher.search_with_callback()** 方法没有接收 `sources` 参数，导致总是调用 `_search_gb_standard_streaming()` 来搜索全部三个源
3. **_search_gb_standard_streaming()** 方法硬编码了搜索全部三个源（GBW、BY、ZBY），没有源过滤机制

## 修改方案

### 1. 修改 app/desktop_app_impl.py - SearchThread.run() 方法
**位置**: Line 503-511

**修改前**:
```python
metadata = EnhancedSmartSearcher.search_with_callback(
    self.keyword,
    AggregatedDownloader(),
    self.output_dir,
    on_result=on_result_callback
)
```

**修改后**:
```python
# 根据用户选择的源列表进行搜索
start_time = time.time()
metadata = EnhancedSmartSearcher.search_with_callback(
    self.keyword,
    AggregatedDownloader(enable_sources=self.sources),
    self.output_dir,
    on_result=on_result_callback,
    sources=self.sources
)
```

**改动说明**:
- 在创建 `AggregatedDownloader` 时传递 `enable_sources=self.sources` 参数
- 在调用 `search_with_callback()` 时新增 `sources=self.sources` 参数

### 2. 修改 core/enhanced_search.py - search_with_callback() 方法签名
**位置**: Line 72-115

**修改前**:
```python
def search_with_callback(keyword: str, downloader, output_dir: str = "downloads", 
                         on_result: Optional[Callable[[Dict, List[Dict]], None]] = None) -> Dict:
    ...
    used_sources, fallback_info, total = EnhancedSmartSearcher._search_gb_standard_streaming(
        keyword, downloader, output_dir, on_result
    )
```

**修改后**:
```python
def search_with_callback(keyword: str, downloader, output_dir: str = "downloads", 
                         on_result: Optional[Callable[[Dict, List[Dict]], None]] = None,
                         sources: Optional[List[str]] = None) -> Dict:
    ...
    # 如果指定了sources，则仅搜索指定的源
    used_sources, fallback_info, total = EnhancedSmartSearcher._search_gb_standard_streaming(
        keyword, downloader, output_dir, on_result, sources=sources
    )
```

**改动说明**:
- 添加 `sources` 可选参数（默认为 None，表示搜索全部源）
- 将 `sources` 参数传递给 `_search_gb_standard_streaming()`

### 3. 修改 core/enhanced_search.py - _search_gb_standard_streaming() 方法
**位置**: Line 122-234

**修改前**:
```python
@staticmethod
def _search_gb_standard_streaming(keyword: str, downloader, output_dir: str,
                                  on_result: Optional[Callable]) -> Tuple[List[str], Dict, int]:
    ...
    # 并行搜索 GBW、BY、ZBY（GB 标准的优先级：GBW > BY > ZBY）
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(search_and_stream_source, "GBW"): "GBW",
            executor.submit(search_and_stream_source, "BY"): "BY",
            executor.submit(search_and_stream_source, "ZBY"): "ZBY",
        }
```

**修改后**:
```python
@staticmethod
def _search_gb_standard_streaming(keyword: str, downloader, output_dir: str,
                                  on_result: Optional[Callable],
                                  sources: Optional[List[str]] = None) -> Tuple[List[str], Dict, int]:
    """
    GB/T 标准流式搜索 - 并行搜索 GBW + BY + ZBY（优先级：GBW > BY > ZBY），逐条返回结果
    
    Args:
        ...
        sources: 要搜索的源列表，如 ["GBW", "BY", "ZBY"]，默认为全部
    ...
    """
    # 如果没有指定sources，默认搜索全部
    if sources is None:
        sources = ["GBW", "BY", "ZBY"]
    
    # 标准化sources为大写
    sources = [s.upper() for s in sources]
    
    ...
    
    # 只并行搜索用户选择的源（优先级：GBW > BY > ZBY）
    sources_to_search = [s for s in ["GBW", "BY", "ZBY"] if s in sources]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for src in sources_to_search:
            futures[executor.submit(search_and_stream_source, src)] = src
        
        # 收集所有结果
        all_results = {source: [] for source in sources_to_search}
    
    # 按优先级进行智能合并（GBW > BY > ZBY），以完整规范化后的标准号为 key
    for priority_source in sources_to_search:
        ...
```

**改动说明**:
- 添加 `sources` 可选参数，默认为 None（搜索全部）
- 当 `sources` 为 None 时，默认设置为 `["GBW", "BY", "ZBY"]`
- 标准化 `sources` 为大写字符串
- 创建 `sources_to_search` 列表，只包含用户选择的源
- 仅为 `sources_to_search` 中的源创建搜索任务
- 仅对 `sources_to_search` 中的源进行合并处理

## 修改验证

### 代码检查
- ✅ Python 代码编译无错误
- ✅ 所有方法签名更新一致
- ✅ 向下兼容性保证（sources 参数为可选）

### 使用场景

**场景1：仅选择 GBW 源**
```python
sources = ["GBW"]
metadata = EnhancedSmartSearcher.search_with_callback(
    keyword, downloader, output_dir, on_result, sources=sources
)
# 结果：仅搜索 GBW 源
```

**场景2：选择 GBW 和 BY 源**
```python
sources = ["GBW", "BY"]
metadata = EnhancedSmartSearcher.search_with_callback(
    keyword, downloader, output_dir, on_result, sources=sources
)
# 结果：仅搜索 GBW 和 BY 源，按优先级合并
```

**场景3：选择所有源（默认行为）**
```python
# 不传递 sources 参数
metadata = EnhancedSmartSearcher.search_with_callback(
    keyword, downloader, output_dir, on_result
)
# 结果：搜索全部三个源（GBW、BY、ZBY）
```

## 修改影响范围

### 主程序 (app/desktop_app_impl.py)
- ✅ SearchThread.run() 方法：现在会传递用户选择的源

### 核心库 (core/enhanced_search.py)
- ✅ search_with_callback() 方法：现在接收并处理源参数
- ✅ _search_gb_standard_streaming() 方法：实现源过滤逻辑
- ✅ 保持向下兼容性：sources 参数为可选

### 不需要修改
- ❌ _search_non_gb_standard_streaming() 方法：暂不涉及此修改

## 测试建议

1. **UI测试**：
   - 仅选择GBW，搜索时验证日志是否显示"仅搜索GBW"
   - 选择多个源，验证搜索结果是否来自选定的源
   - 选择所有源，验证功能与原来相同

2. **代码测试**：
   - 运行 `test_source_selection.py` 进行单元测试

## 已知限制

- 当仅选择一个源时，搜索速度应该显著提升
- 源的优先级顺序保持不变：GBW > BY > ZBY
