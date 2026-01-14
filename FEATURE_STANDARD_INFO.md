# 标准查新功能 - 实现计划

## 📋 功能需求

**标准查新（Standard Information Query）**：查询标准的发布日期、实施日期、废止日期等元数据，帮助用户了解标准的生命周期状态。

### 核心功能
- ✅ 查询单个标准的详细信息（发布日期、实施日期、状态）
- ✅ 显示标准是否已废止及原因
- ✅ 在 UI 中新增展示这些信息
- ✅ Excel 导出包含这些字段

---

## 🗂️ 当前数据模型

### StandardInfo (api/models.py)
```python
@dataclass
class StandardInfo:
    std_no: str                           # 标准编号
    name: str                             # 名称
    source: SourceType                    # 源
    has_pdf: bool = False                 # 是否有PDF
    publish_date: Optional[str] = None    # 发布日期 ✅ 已有
    implement_date: Optional[str] = None  # 实施日期 ✅ 已有
    status: Optional[str] = None          # 状态 ✅ 已有
    source_meta: Dict[str, Any]           # 源特定数据
```

✅ **好消息**：所需字段已经存在！只需要填充和显示这些数据。

---

## 📊 实现步骤

### 阶段 1️⃣：API 层 (1小时)
**文件**：`api/zby_api.py`, `sources/zby.py`

**任务**：
1. [ ] 在 ZBY 搜索结果中提取以下信息：
   - `publish_date` - 发布日期
   - `implement_date` - 实施日期  
   - `status` - 标准状态（现行/废止）
   - 其他元数据存储在 `source_meta`

2. [ ] 创建 `query_standard_info()` 方法
   ```python
   def query_standard_info(self, std_no: str) -> StandardInfo:
       """查询单个标准的详细信息"""
       # 调用 ZBY API 获取标准元数据
   ```

3. [ ] 测试数据填充
   ```python
   # 示例
   std.publish_date = "2023-12-29"
   std.implement_date = "2024-12-01"  
   std.status = "现行"
   ```

### 阶段 2️⃣：UI 层 (1.5小时)
**文件**：`app/desktop_app_impl.py`

**任务**：
1. [ ] 在搜索结果表格中新增列：
   - "发布日期" (publish_date)
   - "实施日期" (implement_date)
   - "状态" (status)

2. [ ] 修改 `setup_search_tab()` 中的表格：
   ```python
   self.search_results_table.setColumnCount(X + 3)  # 原X列 + 3列
   headers = [..., "发布日期", "实施日期", "状态"]
   ```

3. [ ] 在 `display_search_results()` 中填充数据：
   ```python
   item = QTableWidgetItem(std.publish_date or "")
   self.search_results_table.setItem(row, col, item)
   ```

4. [ ] 新增"标准信息"对话框（可选）
   - 点击标准行时显示详情
   - 展示完整的发布/实施/废止信息

### 阶段 3️⃣：Excel 导出 (30分钟)
**文件**：`app/excel_dialog.py`, `core/cache_manager.py`

**任务**：
1. [ ] 扩展 Excel 导出字段：
   ```python
   headers = ["标准编号", "标准名称", "发布日期", "实施日期", "状态", ...]
   ```

2. [ ] 修改 `export_to_excel()` 添加这些列

3. [ ] 保存到缓存时包含这些字段

### 阶段 4️⃣：高级功能 (1小时)
**可选增强**：

1. [ ] **标准状态指示器**
   - 🟢 现行 - 绿色背景
   - 🟡 即将实施 - 黄色背景
   - 🔴 已废止 - 红色背景

2. [ ] **替代标准提示**
   - 如果标准已废止，显示替代标准

3. [ ] **时间轴视图**
   - 发布日期 → 实施日期 → 有效期
   - 可视化标准的生命周期

4. [ ] **快速过滤**
   - 仅显示现行标准
   - 仅显示已废止标准
   - 按发布年份过滤

---

## 🔍 数据来源检查

### ZBY 数据源
- [ ] 确认 ZBY API 提供这些字段
- [ ] 提取规则：
  ```python
  # 从 ZBY 响应的示例
  std_data = {
      "std_no": "GB/T 3324-2024",
      "name": "..."
      "publish_date": "2023-12-29",       # ← 提取
      "implement_date": "2024-12-01",     # ← 提取
      "status": "现行",                    # ← 提取
  }
  ```

### BY 数据源
- [ ] 检查 BY 是否提供这些信息
- [ ] 如不提供，标记为 None

### GBW 数据源
- [ ] 检查 GBW 是否提供这些信息
- [ ] 只有 GB/T 标准可能有此信息

---

## 📝 需要修改的文件

| 文件 | 修改项 | 优先级 |
|------|--------|--------|
| `api/zby_api.py` | 在搜索结果中填充 publish_date, implement_date, status | 🔴 必须 |
| `sources/zby.py` | 从 ZBY 响应提取这些字段 | 🔴 必须 |
| `app/desktop_app_impl.py` | 表格新增 3 列，显示这些数据 | 🔴 必须 |
| `app/excel_dialog.py` | Excel 导出包含这些列 | 🟡 推荐 |
| `api/models.py` | 可能新增模型（如 StandardRevisionHistory） | 🟢 可选 |

---

## 🧪 测试计划

### 单元测试
```python
def test_query_standard_info():
    """测试标准查询"""
    api = ZBYSourceAPI()
    std = api.query_standard_info("GB/T 3324-2024")
    
    assert std.publish_date is not None
    assert std.implement_date is not None
    assert std.status in ["现行", "废止"]
```

### UI 测试
1. [ ] 搜索一个标准，确认三列显示正确
2. [ ] Excel 导出，确认新列存在并有数据
3. [ ] 状态指示器颜色正确（如实现）

### 数据验证
1. [ ] 对比 ZBY 官网数据准确性
2. [ ] 检查日期格式一致性（YYYY-MM-DD）
3. [ ] 废止标准标记正确

---

## ⏱️ 时间估计

| 阶段 | 任务 | 时间 |
|------|------|------|
| 1 | API 层实现与测试 | 1-1.5小时 |
| 2 | UI 表格和对话框 | 1-1.5小时 |
| 3 | Excel 导出扩展 | 0.5小时 |
| 4 | 高级功能（可选） | 1-2小时 |
| **总计** | **核心功能** | **3-4小时** |
| **总计** | **完整功能** | **4-6小时** |

---

## 🚀 快速开始

### 第一步：检查 ZBY 数据
```python
# 在 sources/zby.py 中添加临时测试代码
std = zby_source.search("GB/T 3324-2024")[0]
print(f"发布: {std.get('publish_date')}")
print(f"实施: {std.get('implement_date')}")
print(f"状态: {std.get('status')}")
```

### 第二步：填充 StandardInfo
```python
# 在 api/zby_api.py 的搜索方法中
std_info = StandardInfo(
    std_no=std['std_no'],
    name=std['name'],
    ...
    publish_date=std.get('publish_date'),      # ← 新增
    implement_date=std.get('implement_date'),  # ← 新增
    status=std.get('status'),                  # ← 新增
)
```

### 第三步：更新 UI
```python
# 在 app/desktop_app_impl.py 中
headers = ["编号", "名称", ..., "发布日期", "实施日期", "状态"]
```

---

## 📌 注意事项

1. **数据完整性**：ZBY 可能对某些字段返回 None，需要处理
2. **日期格式**：统一为 `YYYY-MM-DD` 格式
3. **多源支持**：不同源的数据格式可能不同，需要映射
4. **向后兼容**：Excel 导出新增列不应破坏现有数据

---

## 🎯 MVP (最小可行产品)

最快实现方式（0.5-1小时）：
1. ✅ 在表格中新增 3 列
2. ✅ 从现有数据填充（如果 ZBY 已提供）
3. ✅ 测试显示正确

**无需实现**：
- 高级过滤
- 状态指示器
- 替代标准提示
- 对话框详情

---

**下一步**：
1. 确认 ZBY API 是否已返回这些字段
2. 决定先实现 MVP 还是完整功能
3. 开始代码实现
