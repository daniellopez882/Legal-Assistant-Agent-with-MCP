"""
src/llm.py
One place that builds chat models.

Why this exists
---------------
Each of the five agents constructed its own client inline:

    if "claude" in self.model_name.lower():
        self.llm = ChatAnthropic(model=..., api_key=settings.anthropic_api_key, ...)
    else:
        self.llm = ChatOpenAI(model=..., api_key=settings.openai_api_key, ...)

Three consequences:

1. **No seam.** There was nowhere to substitute a model, so every API test
   made a real network call. The suite needed live credentials, cost money to
   run, and could not run in CI. Six of them failed with
   ``Error code: 401 - API key is invalid`` because no key was present.
2. **No fail-fast.** ``openai_api_key`` defaults to ``"sk-placeholder"``, so a
   client was constructed happily with a key that could never work; the failure
   surfaced as a 500 at request time rather than at startup.
3. **No fallback.** If the primary provider was down, the request failed.
   Routing is per-agent and duplicated five times.

``get_chat_model`` is now the single constructor. Tests install a deterministic
fake through ``set_model_factory``, so the suite is hermetic and free.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)

# Values that mean "nobody configured a real key".
PLACEHOLDER_KEYS = frozenset(
    {"", "sk-placeholder", "sk-ant-placeholder", "placeholder", "changeme", "your_api_key_here"}
)


class LLMNotConfigured(RuntimeError):
    """Raised when a model is requested but no usable credentials exist."""


def _is_placeholder(key: str | None) -> bool:
    return key is None or key.strip().lower() in PLACEHOLDER_KEYS


def provider_for(model_name: str) -> str:
    """Which vendor serves this model."""
    lowered = model_name.lower()
    if "claude" in lowered or lowered.startswith("anthropic"):
        return "anthropic"
    return "openai"


def credentials_available() -> dict[str, bool]:
    """Report which providers have a usable key. Used by the readiness probe."""
    settings = get_settings()
    return {
        "anthropic": not _is_placeholder(getattr(settings, "anthropic_api_key", None)),
        "openai": not _is_placeholder(getattr(settings, "openai_api_key", None)),
    }


# ---------------------------------------------------------------- factory
#: Swapped out by tests. See tests/conftest.py.
_factory: Callable[..., Any] | None = None


def set_model_factory(factory: Callable[..., Any] | None) -> None:
    """
    Install a replacement model builder, or pass None to restore the default.

    This is the seam the agents lacked. A test installs a fake here and every
    agent picks it up, with no per-agent patching and no network access.
    """
    global _factory
    _factory = factory


def _build_real_model(
    model_name: str, *, temperature: float, max_tokens: int, **kwargs: Any
) -> Any:
    settings = get_settings()
    provider = provider_for(model_name)

    if provider == "anthropic":
        key = getattr(settings, "anthropic_api_key", None)
        if _is_placeholder(key):
            raise LLMNotConfigured(
                f"{model_name} needs ANTHROPIC_API_KEY, which is unset or still a placeholder."
            )
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            api_key=key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=getattr(settings, "llm_timeout_seconds", 60),
            **kwargs,
        )

    key = getattr(settings, "openai_api_key", None)
    if _is_placeholder(key):
        raise LLMNotConfigured(
            f"{model_name} needs OPENAI_API_KEY, which is unset or still a placeholder."
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name,
        api_key=key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=getattr(settings, "llm_timeout_seconds", 60),
        **kwargs,
    )


def get_chat_model(
    model_name: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 8192,
    fallback_model: str | None = None,
    **kwargs: Any,
) -> Any:
    """
    Build a chat model.

    If ``fallback_model`` is given and the primary provider has no usable
    credentials, the fallback is tried before giving up. That is a
    configuration-time fallback, not a retry: a request that fails mid-flight
    is the caller's concern.
    """
    if _factory is not None:
        return _factory(model_name, temperature=temperature, max_tokens=max_tokens, **kwargs)

    try:
        return _build_real_model(
            model_name, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
    except LLMNotConfigured:
        if not fallback_model or fallback_model == model_name:
            raise
        logger.warning(
            "primary model unavailable, falling back",
            extra={"primary": model_name, "fallback": fallback_model},
        )
        return _build_real_model(
            fallback_model, temperature=temperature, max_tokens=max_tokens, **kwargs
        )


class LazyChatModel:
    """
    Build an agent's chat model on first access instead of in ``__init__``.

    Every agent constructed its model in ``__init__``, and ``create_app()``
    constructs every agent, so the API could not start without live
    credentials: on a machine with none, ``create_app()`` raised
    ``LLMNotConfigured`` and the container exited before serving ``/health``.
    CI never noticed because it built the image and never booted it.

    An agent declares ``llm = LazyChatModel()`` and sets ``self.model_name`` and
    ``self.llm_options`` in ``__init__``. The first attribute access builds the
    model through ``get_chat_model`` -- so the test factory still applies -- and
    caches it on the instance. Assigning ``agent.llm = ...`` overrides it.
    """

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr = f"_{name}_instance"

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        model = obj.__dict__.get(self._attr)
        if model is None:
            model = get_chat_model(obj.model_name, **getattr(obj, "llm_options", {}))
            obj.__dict__[self._attr] = model
        return model

    def __set__(self, obj: Any, value: Any) -> None:
        obj.__dict__[self._attr] = value
