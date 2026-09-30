"""
MountainGuardian v1.0 – providers package.

v1.0 ships exactly one real provider: DeepSeekProvider (deepseek-flash).
See docs/mountainguardian_v1/03 §5 and 06 §21.
"""

from providers.base_provider import (
    ModelProvider,
    ModelRequest,
    ModelResult,
    ProviderError,
    ProviderErrorCategory,
    ProviderHealth,
    ProviderStatus,
    RETRYABLE_CATEGORIES,
    validate_json_schema,
)
from providers.deepseek_provider import DeepSeekProvider

__all__ = [
    "ModelProvider",
    "ModelRequest",
    "ModelResult",
    "ProviderError",
    "ProviderErrorCategory",
    "ProviderHealth",
    "ProviderStatus",
    "RETRYABLE_CATEGORIES",
    "DeepSeekProvider",
    "validate_json_schema",
]
