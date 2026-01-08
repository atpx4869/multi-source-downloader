# -*- coding: utf-8 -*-
"""
API 配置管理模块

支持本地 API 或远程 VPS 部署的配置管理
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class APIMode(Enum):
    """API 运行模式"""
    LOCAL = "local"          # 本地进程内 API
    REMOTE = "remote"        # 远程 VPS 部署的 API


class APIConfig:
    """API 配置类 - 支持 JSON 持久化"""
    
    CONFIG_FILE = Path(__file__).parent.parent / "config" / "api_config.json"
    
    def __init__(self):
        self.mode: APIMode = APIMode.LOCAL
        self.local_output_dir: str = "downloads"
        self.local_timeout: int = 30  # 秒
        self.remote_base_url: str = "http://127.0.0.1:8000"  # VPS API 地址
        self.remote_timeout: int = 60  # 远程请求超时
        self.enable_sources: list = ["gbw", "by", "zby"]
        self.search_limit: int = 100  # 搜索返回结果数
        self.verify_ssl: bool = False  # 是否验证 SSL（VPS）
        self.max_retries: int = 3  # 搜索失败重试次数
        self.retry_delay: int = 2  # 重试延迟（秒）
        
    def load(self) -> bool:
        """从文件加载配置"""
        try:
            if self.CONFIG_FILE.exists():
                data = json.loads(self.CONFIG_FILE.read_text(encoding='utf-8'))
                self._apply_dict(data)
                return True
        except Exception as e:
            print(f"⚠️ 加载配置失败: {e}，使用默认配置")
        return False
    
    def save(self) -> bool:
        """保存配置到文件"""
        try:
            self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = self.to_dict()
            self.CONFIG_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            return True
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "mode": self.mode.value,
            "local_output_dir": self.local_output_dir,
            "local_timeout": self.local_timeout,
            "remote_base_url": self.remote_base_url,
            "remote_timeout": self.remote_timeout,
            "enable_sources": self.enable_sources,
            "search_limit": self.search_limit,
            "verify_ssl": self.verify_ssl,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
        }
    
    def _apply_dict(self, data: Dict[str, Any]) -> None:
        """从字典应用配置"""
        if "mode" in data:
            try:
                self.mode = APIMode(data["mode"])
            except ValueError:
                self.mode = APIMode.LOCAL
        
        if "local_output_dir" in data:
            self.local_output_dir = str(data["local_output_dir"])
        if "local_timeout" in data:
            self.local_timeout = int(data["local_timeout"])
        if "remote_base_url" in data:
            self.remote_base_url = str(data["remote_base_url"])
        if "remote_timeout" in data:
            self.remote_timeout = int(data["remote_timeout"])
        if "enable_sources" in data:
            sources = data["enable_sources"]
            if isinstance(sources, list):
                self.enable_sources = [s.lower() for s in sources]
        if "search_limit" in data:
            self.search_limit = int(data["search_limit"])
        if "verify_ssl" in data:
            self.verify_ssl = bool(data["verify_ssl"])
        if "max_retries" in data:
            self.max_retries = int(data["max_retries"])
        if "retry_delay" in data:
            self.retry_delay = int(data["retry_delay"])
    
    def update(self, **kwargs) -> None:
        """更新配置值"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                if key == "mode" and isinstance(value, str):
                    try:
                        setattr(self, key, APIMode(value))
                    except ValueError:
                        pass
                else:
                    setattr(self, key, value)
    
    def is_local_mode(self) -> bool:
        """是否本地模式"""
        return self.mode == APIMode.LOCAL
    
    def is_remote_mode(self) -> bool:
        """是否远程模式"""
        return self.mode == APIMode.REMOTE
    
    def get_enabled_sources_list(self) -> list:
        """获取已启用源的列表"""
        return [s.upper() for s in self.enable_sources if s]
    
    def __repr__(self) -> str:
        mode_str = "📍 本地" if self.is_local_mode() else f"🌐 远程 ({self.remote_base_url})"
        return f"APIConfig({mode_str}, sources={self.get_enabled_sources_list()})"


# 全局配置实例
_api_config: Optional[APIConfig] = None


def get_api_config() -> APIConfig:
    """获取全局 API 配置实例"""
    global _api_config
    if _api_config is None:
        _api_config = APIConfig()
        _api_config.load()
    return _api_config


def reset_api_config() -> APIConfig:
    """重置并重新加载全局配置"""
    global _api_config
    _api_config = APIConfig()
    _api_config.load()
    return _api_config
