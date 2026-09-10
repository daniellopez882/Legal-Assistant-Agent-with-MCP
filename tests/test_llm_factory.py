"""
Tests for src.llm, the single place chat models are built.

Each agent used to construct its own client inline, which meant there was no
seam to substitute a model. Every API test therefore made a real network call
and six of them failed with

    Error code: 401 - {'type': 'authentication_error', 'message': 'API key is invalid.'}

With a *valid* key present, the suite would have made real, billable calls
instead. These tests pin the seam and the credential handling.
"""

from __future__ import annotations

import pytest

from src import llm
from src.llm import (
    PLACEHOLDER_KEYS,
    LLMNotConfigured,
    credentials_available,
    get_chat_model,
    provider_for,
    set_model_factory,
)


class TestProviderRouting:
    @pytest.mark.parametrize(
        "model,expected",
        [
            ("claude-sonnet-5", "anthropic"),
            ("claude-3-5-sonnet-20241022", "anthropic"),
            ("anthropic/claude-x", "anthropic"),
            ("gpt-4o", "openai"),
            ("gpt-5", "openai"),
            ("some-other-model", "openai"),
        ],
    )
    def test_model_name_selects_the_vendor(self, model, expected):
        assert provider_for(model) == expected


class TestPlaceholderCredentials:
    """
    config.py ships `openai_api_key = "sk-placeholder"`. A client was
    constructed happily with that, and the failure surfaced as a 500 at request
    time rather than as a configuration error.
    """

    @pytest.mark.parametrize("value", sorted(PLACEHOLDER_KEYS))
    def test_placeholder_values_are_not_credentials(self, value, monkeypatch):
        from src.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "openai_api_key", value, raising=False)
        monkeypatch.setattr(settings, "anthropic_api_key", value, raising=False)
        get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
        assert credentials_available() == {"anthropic": False, "openai": False}

    def test_building_a_model_without_credentials_is_a_clear_error(self, monkeypatch):
        from src.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "openai_api_key", "sk-placeholder", raising=False)
        monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-placeholder", raising=False)
        set_model_factory(None)
        try:
            with pytest.raises(LLMNotConfigured, match="OPENAI_API_KEY"):
                get_chat_model("gpt-4o")
        finally:
            from tests.conftest import make_fake_model

            set_model_factory(make_fake_model)

    def test_credentials_report_covers_both_vendors(self):
        assert set(credentials_available()) == {"anthropic", "openai"}


class TestFactorySeam:
    def test_the_installed_factory_is_used(self):
        sentinel = object()
        previous = llm._factory
        try:
            set_model_factory(lambda name, **kw: sentinel)
            assert get_chat_model("gpt-4o") is sentinel
        finally:
            set_model_factory(previous)

    def test_the_conftest_fake_is_active_during_tests(self):
        """No test should be able to reach a real provider by accident."""
        model = get_chat_model("claude-sonnet-5")
        assert type(model).__name__ == "GenericFakeChatModel"

    def test_the_fake_is_a_real_runnable(self):
        """
        The agents build `prompt | llm | parser` chains. A duck-typed stand-in
        fails with "Expected a Runnable, callable or dict".
        """
        from langchain_core.runnables import Runnable

        assert isinstance(get_chat_model("gpt-4o"), Runnable)

    def test_the_fake_returns_parseable_content(self):
        result = get_chat_model("gpt-4o").invoke("anything")
        assert result.content.strip().startswith("{")

    def test_the_fake_answers_repeatedly(self):
        """Agents call the model more than once per request."""
        model = get_chat_model("gpt-4o")
        assert model.invoke("a").content == model.invoke("b").content


class TestNoDirectConstruction:
    def test_no_agent_builds_its_own_client(self):
        """
        Regression guard: five agents each constructed ChatOpenAI/ChatAnthropic
        inline, which is what removed the seam in the first place.
        """
        from pathlib import Path

        agents_dir = Path(__file__).resolve().parents[1] / "src" / "agents"
        offenders = [
            path.name
            for path in agents_dir.glob("*.py")
            if "ChatOpenAI(" in path.read_text(encoding="utf-8")
            or "ChatAnthropic(" in path.read_text(encoding="utf-8")
        ]
        assert not offenders, f"these build a model directly instead of via src.llm: {offenders}"
