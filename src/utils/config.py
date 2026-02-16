from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.utils.exceptions import ConfigError


def load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file. Raises ConfigError on failure."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ConfigError(f"Expected mapping at top level of {path}")
    return data


def load_config(config_path: Path = Path("config.yml")) -> dict[str, Any]:
    """Load the main scanner config and merge policy overrides."""
    config = load_yaml(config_path)

    policy_cfg = config.get("policy", {})
    default_policy = load_yaml(Path(policy_cfg["default_file"]))

    override_path = Path(policy_cfg["user_override_file"])
    if override_path.exists():
        overrides = load_yaml(override_path)
        default_policy = _deep_merge(default_policy, overrides)

    if policy_cfg.get("enable_advanced"):
        adv_path = Path(policy_cfg["advanced_override_file"])
        if adv_path.exists():
            advanced = load_yaml(adv_path)
            default_policy = _deep_merge(default_policy, advanced)

    config["resolved_policy"] = default_policy
    return config


def require_env(name: str) -> str:
    """Get a required environment variable. Raises ConfigError if missing."""
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Required environment variable not set: {name}")
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
