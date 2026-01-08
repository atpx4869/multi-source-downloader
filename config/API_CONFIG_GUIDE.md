# API 配置系统说明

## 快速开始

### 1. 本地模式（推荐）
默认配置使用本地模式，API 在应用进程内运行：

```python
from core.api_config import get_api_config
from core.api_client import get_api_client

config = get_api_config()
client = get_api_client(config)

# 搜索标准
results = client.search("GB/T 3324")

# 下载文件
file_path, logs = client.download("gbw", "GB/T 3324")

# 检查健康状态
health = client.health_check()
```

### 2. 远程模式（VPS 部署）
如果部署在 VPS 上，修改配置：

```python
from core.api_config import get_api_config, APIMode

config = get_api_config()
config.mode = APIMode.REMOTE
config.remote_base_url = "http://vps-ip:8000"
config.save()
```

## 配置文件结构

配置文件位置：`config/api_config.json`

```json
{
  "mode": "local",                    // "local" 或 "remote"
  "local_output_dir": "downloads",    // 本地下载目录
  "local_timeout": 30,                // 本地请求超时（秒）
  "remote_base_url": "http://127.0.0.1:8000",  // VPS API 地址
  "remote_timeout": 60,               // 远程请求超时（秒）
  "enable_sources": ["gbw", "by", "zby"],      // 启用的数据源
  "search_limit": 100,                // 搜索返回结果数
  "verify_ssl": false,                // 是否验证 SSL（VPS）
  "max_retries": 3,                   // 搜索失败最大重试次数
  "retry_delay": 2                    // 重试延迟（秒）
}
```

## 配置类 (APIConfig)

### 属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| mode | APIMode | LOCAL | 运行模式（本地/远程） |
| local_output_dir | str | downloads | 本地下载目录 |
| local_timeout | int | 30 | 本地请求超时（秒） |
| remote_base_url | str | http://127.0.0.1:8000 | VPS API 地址 |
| remote_timeout | int | 60 | 远程请求超时（秒） |
| enable_sources | list | [gbw, by, zby] | 启用的数据源 |
| search_limit | int | 100 | 搜索返回结果数 |
| verify_ssl | bool | False | 是否验证 SSL |
| max_retries | int | 3 | 搜索失败重试次数 |
| retry_delay | int | 2 | 重试延迟（秒） |

### 常用方法

```python
# 加载配置
config = get_api_config()
success = config.load()

# 保存配置
config.save()

# 更新配置
config.update(mode="remote", remote_base_url="http://vps:8000")

# 检查模式
if config.is_local_mode():
    print("本地模式运行")
    
if config.is_remote_mode():
    print("远程模式运行")

# 转换为字典
config_dict = config.to_dict()

# 获取启用的源
sources = config.get_enabled_sources_list()  # ['GBW', 'BY', 'ZBY']
```

## API 客户端 (APIClient)

统一的 API 客户端，自动根据配置选择本地或远程模式。

### 常用方法

```python
from core.api_client import get_api_client

client = get_api_client()

# 搜索（返回 dict）
results = client.search("GB/T 3324", limit=50)
# {
#   "gbw": [{"std_no": "GB/T 3324-2024", ...}],
#   "by": [...],
#   "zby": [...]
# }

# 下载（返回 (file_path, logs)）
path, logs = client.download("gbw", "GB/T 3324", output_dir="downloads")

# 健康检查
health = client.health_check()
# {
#   "status": "ok",
#   "available": 3,
#   "total": 3,
#   "sources": {...}
# }
```

## 在桌面应用中使用

### 1. 打开设置对话框

![Settings Dialog](screenshot)

菜单 → 设置 → 弹出设置对话框

### 2. 配置 API 模式

- **📍 本地模式**：API 在本地进程运行
  - 下载目录
  - 请求超时

- **🌐 远程模式**：连接到 VPS 部署的 API
  - API 地址
  - 请求超时
  - SSL 验证

### 3. 配置数据源

选择启用的数据源：
- ✓ GBW (国家标准平台)
- ✓ BY (内部系统)
- ✓ ZBY (标准云)

### 4. 搜索和重试配置

- 返回结果数：10-500
- 最大重试次数：1-10
- 重试延迟：1-30 秒

### 5. 保存或重置

- **保存**：应用用户配置
- **重置默认**：恢复默认设置

## 本地 vs 远程对比

### 本地模式 ✅
```
优点：
- 无网络暴露
- 零成本运行
- 隐私最强（数据不离开本地）
- 不受 VPS 安全事件影响
- 性能：±0% 额外延迟

缺点：
- 需要本机有完整运行环境
- 不能多用户共享
```

### 远程模式
```
优点：
- 可多用户共享
- 中心化日志管理
- VPS 可独立升级
- 可配置反向代理

缺点：
- 需要维护 VPS 服务
- 数据在网络传输（需 HTTPS）
- VPS 被入侵则全部沦陷
- 额外网络延迟：200-400ms
```

## 最佳实践

### 1. 本地部署（推荐）
```python
# 使用默认本地配置
config = get_api_config()
# 无需修改，直接使用
```

### 2. 生产环保（如需 VPS）
```python
# 部署在 VPS 上
config = get_api_config()
config.mode = APIMode.REMOTE
config.remote_base_url = "https://api.example.com"  # 使用 HTTPS
config.verify_ssl = True
config.save()
```

### 3. 开发/测试
```python
# 本地开发 + VPS 测试
config = get_api_config()

# 开发时：本地模式
config.mode = APIMode.LOCAL
config.save()

# 测试时：远程模式
config.mode = APIMode.REMOTE
config.remote_base_url = "http://test-vps:8000"
config.save()
```

## 故障排除

### 本地模式找不到 Playwright
```python
# 确保安装了 Playwright
pip install playwright
playwright install chromium
```

### 远程模式连接超时
```python
# 检查 VPS 地址和防火墙
# 增加超时时间
config = get_api_config()
config.remote_timeout = 120  # 改为 120 秒
config.save()
```

### 配置加载失败
```python
# 重置为默认配置
from core.api_config import APIConfig
default = APIConfig()
default.save()
```

## 文件清单

```
core/
├── api_config.py        # API 配置管理类
├── api_client.py        # API 统一客户端
└── ...

config/
└── api_config.json      # 配置文件（自动生成）

app/
└── desktop_app_impl.py  # 桌面应用（已集成设置对话框）
```

## API 配置权限流

```
用户打开设置 → SettingsDialog 显示当前配置 → 用户修改 
    ↓
点击"保存" → get_settings() 更新全局 APIConfig 
    ↓
APIConfig.save() 写入 JSON 文件 
    ↓
reset_api_client() 重新初始化客户端 
    ↓
应用立即生效
```
