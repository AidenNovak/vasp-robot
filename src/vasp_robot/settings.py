"""Centralised configuration helpers for the VASP robot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class Settings:
    """Bundle of orchestrator, prompt and secret configuration."""

    base: Dict[str, Any]
    prompts: Dict[str, Any]
    secrets: Dict[str, Any]

    def get_incar_defaults(self) -> Dict[str, Any]:
        """Return a copy of the configured INCAR defaults."""

        defaults = {}
        config_defaults = self.base.get("defaults", {})
        if isinstance(config_defaults, dict):
            incar_defaults = config_defaults.get("incar", {})
            if isinstance(incar_defaults, dict):
                defaults = incar_defaults
        return defaults.copy()

    def get_service_config(self, service: str) -> Dict[str, Any]:
        """Return a copy of the service configuration stored in secrets."""

        services = self.secrets.get("services", {})
        if not isinstance(services, dict):
            return {}
        service_config = services.get(service, {})
        return service_config.copy() if isinstance(service_config, dict) else {}

    def get_api_key(self, service: str, *, env_var: Optional[str] = None) -> Optional[str]:
        """Resolve an API key using environment variables as override."""

        env_name = env_var or f"{service.upper()}_API_KEY"
        api_key = os.getenv(env_name)
        if api_key:
            return api_key

        api_keys = self.secrets.get("api_keys", {})
        if isinstance(api_keys, dict):
            candidate = api_keys.get(service) or api_keys.get(service.upper())
            if candidate and "SET_ME" not in candidate:
                return candidate
        return None


def get_settings(
    base_config_path: str = "config/vasp_config.yaml",
    prompts_path: str = "config/system_prompts.yaml",
    secrets_path: str = "config/secrets.yaml",
) -> Settings:
    """Load and cache configuration bundles for orchestrator components."""

    base_config = _resolve_path(base_config_path)
    prompts_config = _resolve_path(prompts_path)
    secrets_config = _resolve_path(secrets_path)
    return _load_settings_cached(base_config, prompts_config, secrets_config)


@lru_cache(maxsize=None)
def _load_settings_cached(
    base_config_path: Optional[str],
    prompts_path: Optional[str],
    secrets_path: Optional[str],
) -> Settings:
    base = _read_yaml(base_config_path)
    prompts = _read_yaml(prompts_path)
    secrets = _read_yaml(secrets_path)
    return Settings(base=base, prompts=prompts, secrets=secrets)


def _resolve_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    resolved = Path(path).expanduser().resolve()
    return str(resolved)


def _read_yaml(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Expected mapping at {file_path}, got {type(data).__name__}")
        return data
