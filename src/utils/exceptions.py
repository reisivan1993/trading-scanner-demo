from __future__ import annotations


class ScannerError(Exception):
    """Base exception for all scanner errors."""


class ConfigError(ScannerError):
    """Raised when configuration is invalid or missing."""


class ProviderError(ScannerError):
    """Raised when a data provider call fails."""


class RateLimitError(ProviderError):
    """Raised when a provider rate limit is hit."""


class PolicyValidationError(ScannerError):
    """Raised when a policy file is malformed or contains invalid rules."""


class RiskGateError(ScannerError):
    """Raised when risk calculation encounters invalid inputs."""
