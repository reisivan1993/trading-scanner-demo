from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from packages.core.config import AppConfig
from packages.policy.schema import MergedPolicy


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base*. Override values win."""
    merged: dict[str, Any] = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Policy file not found: {file_path}")

    with open(file_path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Policy file is empty: {file_path}")

    return raw


def load_policies(config: AppConfig) -> MergedPolicy:
    """Load and merge all policy layers into a single MergedPolicy.

    Loads the default policy, applies user overrides on top, and optionally
    applies the advanced overrides if ``config.policy.enable_advanced`` is True.
    """
    merged = _load_yaml(config.policy.default_file)

    user_override = _load_yaml(config.policy.user_override_file)
    merged = deep_merge(merged, user_override)

    if config.policy.enable_advanced:
        advanced = _load_yaml(config.policy.advanced_override_file)
        merged = deep_merge(merged, advanced)

    return MergedPolicy.model_validate(merged)
