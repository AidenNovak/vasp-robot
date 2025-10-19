"""
统一的配置管理器
Unified Configuration Manager

合并所有配置加载逻辑，减少重复代码
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class HPCConfig:
    """HPC配置"""
    host: str
    user: str
    port: int = 22
    work_dir: str = "~/vasp_calculations"
    timeout: int = 30
    strict_host_key: bool = False


@dataclass
class APIConfig:
    """API配置"""
    base_url: str
    api_key: str
    model: str


class ConfigManager:
    """统一配置管理器"""

    def __init__(self, config_dir: str = "config"):
        """初始化配置管理器"""
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}
        self._load_all_configs()

    def _load_all_configs(self):
        """加载所有配置文件"""
        # 定义配置文件映射
        config_files = {
            "base": "vasp_config.yaml",
            "workflow": "workflow_config.yaml",
            "prompts": "system_prompts.yaml",
            "secrets": "secrets.yaml",
            "subagents": "claude_subagents.yaml"
        }

        # 加载每个配置文件
        for key, filename in config_files.items():
            file_path = self.config_dir / filename
            self._cache[key] = self._load_yaml(file_path, {})

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的嵌套键

        Args:
            key: 配置键，支持 "nested.key" 格式
            default: 默认值

        Returns:
            配置值
        """
        # 尝试从缓存获取
        if "." in key:
            # 处理嵌套键
            parts = key.split(".")
            value = self._cache

            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default

            return value
        else:
            # 直接键
            return self._cache.get(key, default)

    def get_hpc_config(self) -> HPCConfig:
        """获取HPC配置"""
        # 从workflow配置中读取
        workflow = self.get("workflow", {})
        hpc_env = workflow.get("hpc_environment", {})
        cluster = hpc_env.get("cluster", {})

        return HPCConfig(
            host=cluster.get("host", "localhost"),
            user=cluster.get("user", ""),
            port=cluster.get("port", 22),
            work_dir=cluster.get("work_dir", "~/vasp_calculations"),
            timeout=hpc_env.get("connection", {}).get("timeout", 30),
            strict_host_key=hpc_env.get("connection", {}).get("strict_host_key_checking", False)
        )

    def get_api_config(self, service: str) -> Optional[APIConfig]:
        """
        获取API配置

        Args:
            service: 服务名称 (kimi, openai, etc.)

        Returns:
            API配置对象
        """
        # 优先从环境变量获取
        env_key = f"{service.upper()}_API_KEY"
        api_key = os.getenv(env_key)

        if api_key:
            return APIConfig(
                base_url=os.getenv(f"{service.upper()}_BASE_URL", ""),
                api_key=api_key,
                model=os.getenv(f"{service.upper()}_MODEL", "")
            )

        # 从配置文件获取
        secrets = self.get("secrets", {})

        # 检查services部分
        services = secrets.get("services", {})
        if service in services:
            service_config = services[service]
            return APIConfig(
                base_url=service_config.get("base_url", ""),
                api_key=service_config.get("api_key", ""),
                model=service_config.get("model", "")
            )

        # 检查api_keys部分
        api_keys = secrets.get("api_keys", {})
        if service in api_keys:
            return APIConfig(
                base_url="",
                api_key=api_keys[service],
                model=""
            )

        return None

    def get_incar_defaults(self) -> Dict[str, Any]:
        """获取INCAR默认参数"""
        base = self.get("base", {})
        defaults = base.get("defaults", {})
        return defaults.get("incar", {})

    def get_prompt(self, name: str) -> str:
        """获取系统提示词"""
        prompts = self.get("prompts", {})
        return prompts.get(name, "")

    def reload(self):
        """重新加载配置"""
        self._cache.clear()
        self._load_all_configs()

    def _load_yaml(self, path: Path, default: Any) -> Any:
        """加载YAML文件"""
        if not path.exists():
            return default

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or default
        except Exception as e:
            print(f"⚠️ 加载配置文件失败 {path}: {e}")
            return default

    def merge_configs(self, *config_names: str) -> Dict[str, Any]:
        """
        合并多个配置

        Args:
            config_names: 要合并的配置名称

        Returns:
            合并后的配置字典
        """
        merged = {}
        for name in config_names:
            config = self.get(name, {})
            if isinstance(config, dict):
                merged = self._deep_merge(merged, config)
        return merged

    def _deep_merge(self, dict1: Dict, dict2: Dict) -> Dict:
        """深度合并字典"""
        result = dict1.copy()

        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: str = "config") -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    """便捷函数：获取配置值"""
    return get_config_manager().get(key, default)


def get_hpc_config() -> HPCConfig:
    """便捷函数：获取HPC配置"""
    return get_config_manager().get_hpc_config()


def get_api_config(service: str) -> Optional[APIConfig]:
    """便捷函数：获取API配置"""
    return get_config_manager().get_api_config(service)