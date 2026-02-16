from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv

from packages.core.config import AppConfig, load_config
from packages.policy.engine import PolicyEngine
from packages.policy.loader import load_policies
from packages.policy.schema import MergedPolicy
from packages.providers.base import BaseProvider
from packages.providers.factory import get_provider

load_dotenv()


@lru_cache
def get_config() -> AppConfig:
    return load_config("config.yml")


@lru_cache
def get_policy() -> MergedPolicy:
    return load_policies(get_config())


@lru_cache
def get_policy_engine() -> PolicyEngine:
    return PolicyEngine()


@lru_cache
def get_data_provider() -> BaseProvider:
    return get_provider(get_config())
