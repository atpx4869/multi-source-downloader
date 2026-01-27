# 统一数据模型迁移指南

## 📋 概述

本指南帮助您将项目从**双模型系统**迁移到**统一数据模型**。

### 当前问题
```
旧架构：
├─ core.models.Standard        (Desktop App 使用)
└─ api.models.StandardInfo      (Web App 使用)

问题：
❌ 字段名不一致（publish vs publish_date）
❌ 需要手动转换格式
❌ 容易出现 KeyError
❌ 维护成本高（改一处要改两处）
```

### 新架构
```
新架构：
└─ core.unified_models.UnifiedStandard  (所有地方使用)

优势：
✅ 单一数据源
✅ 向后兼容（支持旧字段名）
✅ 类型安全
✅ 易于维护
```

---

## 🎯 迁移策略：渐进式替换

**原则**：不破坏现有功能，逐步替换。

### 阶段 1：引入统一模型（已完成 ✅）
- [x] 创建 `core/unified_models.py`
- [x] 编写测试验证功能
- [x] 确保向后兼容

### 阶段 2：核心模块迁移（本阶段）
- [ ] 迁移 `AggregatedDownloader`
- [ ] 迁移搜索合并器
- [ ] 迁移 API 层

### 阶段 3：UI 层迁移
- [ ] 迁移 Desktop App
- [ ] 迁移 Web App

### 阶段 4：清理
- [ ] 移除旧模型
- [ ] 更新文档

---

## 📝 迁移步骤

### Step 1: 更新导入语句

**旧代码**：
```python
from core.models import Standard
```

**新代码**：
```python
from core.unified_models import UnifiedStandard as Standard
# 或者
from core.unified_models import Standard  # 使用别名
```

**说明**：使用别名可以最小化代码改动。

---

### Step 2: 字段名迁移

#### 选项 A：使用新字段名（推荐）

**旧代码**：
```python
std = Standard(
    std_no="GB/T 1234-2020",
    name="测试标准",
    publish="2020-01-01",      # 旧字段名
    implement="2020-07-01"     # 旧字段名
)

print(std.publish)             # 访问旧字段
```

**新代码**：
```python
std = Standard(
    std_no="GB/T 1234-2020",
    name="测试标准",
    publish_date="2020-01-01",    # 新字段名
    implement_date="2020-07-01"   # 新字段名
)

print(std.publish_date)           # 访问新字段
```

#### 选项 B：继续使用旧字段名（兼容模式）

**代码**：
```python
std = Standard(
    std_no="GB/T 1234-2020",
    name="测试标准",
    publish_date="2020-01-01"
)

# 仍然可以使用旧字段名访问
print(std.publish)  # 自动映射到 publish_date
```

**说明**：向后兼容属性会自动处理映射。

---

### Step 3: 批量转换现有数据

#### 场景 1：从旧模型列表转换

```python
from core.unified_models import convert_legacy_standards

# 旧代码返回 List[core.models.Standard]
old_standards = aggregated_downloader.search("GB/T 3324")

# 转换为统一模型
unified_standards = convert_legacy_standards(old_standards)

# 现在可以使用统一模型的所有功能
for std in unified_standards:
    print(std.publish_date)  # 新字段名
    print(std.get_primary_source())  # 新方法
```

#### 场景 2：单个对象转换

```python
from core.unified_models import UnifiedStandard

# 从旧模型转换
old_std = some_function_returns_old_standard()
new_std = UnifiedStandard.from_legacy_standard(old_std)

# 从字典转换（支持旧字段名）
data = {
    'std_no': 'GB/T 1234-2020',
    'name': '测试',
    'publish': '2020-01-01',  # 旧字段名也能识别
}
new_std = UnifiedStandard.from_dict(data)
```

---

### Step 4: 更新函数签名

#### 示例：搜索函数

**旧代码**：
```python
def search(keyword: str) -> List[Standard]:
    # 返回 core.models.Standard 列表
    pass
```

**新代码**：
```python
from core.unified_models import UnifiedStandard

def search(keyword: str) -> List[UnifiedStandard]:
    # 返回统一模型列表
    pass
```

**渐进式迁移**：
```python
from core.unified_models import UnifiedStandard, convert_legacy_standards

def search(keyword: str) -> List[UnifiedStandard]:
    # 内部仍使用旧逻辑
    old_results = _old_search_logic(keyword)

    # 转换后返回
    return convert_legacy_standards(old_results)
```

---

## 🔧 具体文件迁移示例

### 文件 1: `core/aggregated_downloader.py`

**当前状态**：使用 `core.models.Standard`

**迁移步骤**：

1. **更新导入**：
```python
# 旧
from core.models import Standard

# 新
from core.unified_models import UnifiedStandard as Standard
```

2. **无需修改其他代码**（因为使用了别名）

3. **测试**：运行现有测试确保功能正常

---

### 文件 2: `core/smart_search.py` 和 `core/enhanced_search.py`

**当前状态**：使用字典格式

**迁移步骤**：

1. **更新返回类型**：
```python
# 旧
def merge_results(zby_results: List[Dict], gbw_results: List[Dict]) -> List[Dict]:
    pass

# 新
from core.unified_models import UnifiedStandard

def merge_results(zby_results: List[UnifiedStandard],
                  gbw_results: List[UnifiedStandard]) -> List[UnifiedStandard]:
    pass
```

2. **更新内部逻辑**：
```python
# 旧：字典操作
result = {
    'std_no': item.get('std_no'),
    'name': item.get('name'),
    'status': item.get('status')
}

# 新：对象操作
result = UnifiedStandard(
    std_no=item.std_no,
    name=item.name,
    status=item.status
)
```

---

### 文件 3: `api/router.py`

**当前状态**：使用 `api.models.StandardInfo`

**迁移步骤**：

1. **更新导入**：
```python
# 旧
from api.models import StandardInfo

# 新
from core.unified_models import UnifiedStandard
```

2. **更新返回类型**：
```python
# 旧
def search_single(self, source: SourceType, query: str) -> SearchResponse:
    # SearchResponse.standards: List[StandardInfo]
    pass

# 新
def search_single(self, source: SourceType, query: str) -> SearchResponse:
    # SearchResponse.standards: List[UnifiedStandard]
    pass
```

---

## ⚠️ 注意事项

### 1. 字段名一致性

**问题**：混用新旧字段名会导致混乱。

**建议**：
- 新代码统一使用 `publish_date` 和 `implement_date`
- 旧代码可以继续使用 `publish` 和 `implement`（向后兼容）
- 逐步迁移，不要一次性全改

### 2. 类型检查

**问题**：类型检查工具可能报错。

**解决**：
```python
from typing import Union
from core.models import Standard as LegacyStandard
from core.unified_models import UnifiedStandard

# 过渡期支持两种类型
def process_standard(std: Union[LegacyStandard, UnifiedStandard]):
    # 统一转换为新模型
    if isinstance(std, LegacyStandard):
        std = UnifiedStandard.from_legacy_standard(std)

    # 使用新模型
    print(std.publish_date)
```

### 3. 序列化兼容性

**问题**：JSON 序列化可能需要调整。

**解决**：
```python
# 统一模型提供 to_dict() 方法
data = std.to_dict()
json_str = json.dumps(data, ensure_ascii=False)

# 反序列化
data = json.loads(json_str)
std = UnifiedStandard.from_dict(data)
```

---

## 📊 迁移进度跟踪

### 核心模块
- [ ] `core/aggregated_downloader.py`
- [ ] `core/smart_search.py`
- [ ] `core/enhanced_search.py`

### API 层
- [ ] `api/router.py`
- [ ] `api/by_api.py`
- [ ] `api/zby_api.py`
- [ ] `api/gbw_api.py`

### 数据源
- [ ] `sources/gbw.py`
- [ ] `sources/by.py`
- [ ] `sources/zby.py`

### UI 层
- [ ] `app/desktop_app_impl.py`
- [ ] `web_app/web_app.py`
- [ ] `web_app/excel_standard_processor.py`

---

## 🧪 测试策略

### 1. 单元测试

```python
# 测试文件：test_unified_models.py（已完成）
python test_unified_models.py
```

### 2. 集成测试

```python
# 测试迁移后的模块
def test_aggregated_downloader_with_unified_model():
    from core.aggregated_downloader import AggregatedDownloader
    from core.unified_models import UnifiedStandard

    downloader = AggregatedDownloader()
    results = downloader.search("GB/T 3324")

    # 验证返回类型
    assert all(isinstance(r, UnifiedStandard) for r in results)

    # 验证字段
    for r in results:
        assert hasattr(r, 'publish_date')
        assert hasattr(r, 'implement_date')
```

### 3. 回归测试

运行现有的所有测试，确保没有破坏功能：
```bash
python -m pytest tests/
```

---

## 🚀 快速开始

### 最小化迁移（5分钟）

只需修改一行代码即可开始使用统一模型：

```python
# 在文件顶部
from core.unified_models import Standard  # 替代 from core.models import Standard

# 其他代码无需修改！
```

### 完整迁移（建议）

1. **第一周**：迁移核心模块（`aggregated_downloader.py`）
2. **第二周**：迁移搜索合并器
3. **第三周**：迁移 API 层
4. **第四周**：迁移 UI 层
5. **第五周**：清理和文档更新

---

## 💡 常见问题

### Q1: 迁移会破坏现有功能吗？

**A**: 不会。统一模型设计了完整的向后兼容性：
- 支持旧字段名（`publish` 自动映射到 `publish_date`）
- 提供转换方法（`from_legacy_standard()`, `to_legacy_standard()`）
- 可以渐进式迁移，不需要一次性全改

### Q2: 如果遇到问题怎么办？

**A**: 可以随时回退：
```python
# 如果新模型有问题，转换回旧模型
old_std = unified_std.to_legacy_standard()
```

### Q3: 性能会受影响吗？

**A**: 不会。统一模型使用 `@dataclass`，性能与旧模型相同。

### Q4: 需要修改数据库吗？

**A**: 不需要。统一模型的序列化格式兼容旧格式。

---

## 📞 获取帮助

如果在迁移过程中遇到问题：

1. 查看测试文件 `test_unified_models.py` 中的示例
2. 阅读 `core/unified_models.py` 中的文档字符串
3. 运行测试验证功能：`python test_unified_models.py`

---

## ✅ 迁移检查清单

完成迁移后，确认以下项目：

- [ ] 所有测试通过
- [ ] 搜索功能正常
- [ ] 下载功能正常
- [ ] UI 显示正确
- [ ] 数据序列化/反序列化正常
- [ ] 性能无明显下降
- [ ] 日志输出正常

---

**祝迁移顺利！** 🎉
