"""
Shared test fixtures.

The suite previously had no conftest, and every agent built its own LLM client
inline, so the API tests made real network calls to Anthropic and OpenAI. Six
of them failed with

    Error code: 401 - {'type': 'authentication_error', 'message': 'API key is invalid.'}

because no credentials were present. Worse: with a *valid* key in the
environment, running the suite would have made real, billable calls.

``src.llm.set_model_factory`` is the seam that fixes this. A deterministic fake
is installed for the whole session, so tests are hermetic, free and fast. A
test that genuinely needs a live model must be marked ``requires_api`` and is
deselected by default.
"""

from __future__ import annotations

import itertools
import json
import os
from typing import Any

import pytest
from langchain_core.messages import AIMessage

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LOG_LEVEL", "WARNING")


DEFAULT_PAYLOAD = {
    "summary": "Deterministic test response.",
    "risk_level": "medium",
    "risks": [],
    "risk_clauses": [],
    "missing_protections": [],
    "unfavorable_terms": [],
    "recommendations": [],
    "citations": [],
    "cases": [],
    "deadlines": [],
    "line_items": [],
    "total": 0,
    "confidence": 0.5,
    "task_type": "contract_review",
    "reasoning": "test",
    "content": "Deterministic test response.",
}


def make_fake_model(model_name: str = "fake-model", response: str | None = None, **kwargs: Any):
    """
    A real LangChain chat model that always returns the same content.

    It must be an actual Runnable: the agents build ``prompt | llm | parser``
    chains, and a duck-typed stand-in fails with
    "Expected a Runnable, callable or dict".

    GenericFakeChatModel is LangChain's own fake, so the whole Runnable
    protocol -- invoke, ainvoke, stream, pipe -- behaves correctly.
    """
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    payload = response if response is not None else json.dumps(DEFAULT_PAYLOAD)
    # itertools.cycle: the same content for every call, however many are made.
    model = GenericFakeChatModel(messages=itertools.cycle([AIMessage(content=payload)]))
    return model


@pytest.fixture(scope="session", autouse=True)
def _no_live_llm_calls():
    """
    Install the fake model for the whole session.

    autouse and session-scoped on purpose: no test should reach a real provider
    by accident, and a per-test opt-in would leave that possible.
    """
    from src import llm

    llm.set_model_factory(make_fake_model)
    yield
    llm.set_model_factory(None)


@pytest.fixture
def fake_llm():
    """A fake model returning the default payload."""
    return make_fake_model()


@pytest.fixture
def fake_llm_returning():
    """Build a fake model with a caller-chosen response."""

    def _factory(response):
        payload = response if isinstance(response, str) else json.dumps(response)
        return make_fake_model(response=payload)

    return _factory


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from src.server.server import create_app

    with TestClient(create_app()) as c:
        yield c


def pytest_collection_modifyitems(config, items):
    """Skip tests marked ``requires_api`` unless credentials are really present."""
    from src.llm import credentials_available

    if any(credentials_available().values()):
        return
    skip = pytest.mark.skip(reason="no live LLM credentials; run with a real key to exercise")
    for item in items:
        if "requires_api" in item.keywords:
            item.add_marker(skip)
