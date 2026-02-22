"""Provider registry — maps provider names to classes."""

from __future__ import annotations

from typing import Any

from evals.src.providers.base import Provider

_REGISTRY: dict[str, type[Provider]] = {}


def _ensure_registered() -> None:
    """Lazily register built-in providers to avoid import errors
    when optional SDKs aren't installed."""
    if _REGISTRY:
        return

    try:
        from evals.src.providers.gemini import GeminiProvider

        _REGISTRY["gemini"] = GeminiProvider
    except ImportError:
        pass

    try:
        from evals.src.providers.openai_provider import OpenAIProvider

        _REGISTRY["openai"] = OpenAIProvider
    except ImportError:
        pass


def get_provider(name: str, model: str, generation_params: dict[str, Any] | None = None) -> Provider:
    """Instantiate a provider by name.

    Args:
        name: Provider identifier (e.g. "gemini", "openai").
        model: Model name to use.
        generation_params: Default generation parameters.

    Returns:
        An initialised Provider instance.
    """
    _ensure_registered()
    if name not in _REGISTRY:
        available = ", ".join(_REGISTRY.keys()) or "(none — install provider SDKs)"
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")
    return _REGISTRY[name](model=model, generation_params=generation_params)
