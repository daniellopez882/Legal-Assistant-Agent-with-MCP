"""
The application boots without model credentials.

Reproduced defect: every agent built its chat model in ``__init__`` and
``create_app()`` built every agent, so on a machine without live API keys
``create_app()`` raised ``LLMNotConfigured``. The container image exited at
startup (exit code 1, never answering ``/health``); CI had only ever built it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src import llm
from src.agents import ContractReviewerAgent
from src.server.server import create_app

REVIEW = {
    "document_text": "This Agreement is between A and B. " * 5,
    "document_name": "a.txt",
    "matter_id": "M-1",
    "client_name": "A",
    "jurisdiction": "Texas",
}


@pytest.fixture
def no_model_factory():
    """Remove the session-wide fake so the real (placeholder) credentials apply."""
    llm.set_model_factory(None)
    try:
        yield
    finally:
        from tests.conftest import make_fake_model

        llm.set_model_factory(make_fake_model)


class TestBootWithoutCredentials:
    def test_create_app_does_not_need_credentials(self, no_model_factory):
        app = create_app()  # used to raise LLMNotConfigured
        assert app is not None

    def test_health_is_served_without_credentials(self, no_model_factory):
        with TestClient(create_app()) as c:
            assert c.get("/health").status_code == 200

    def test_ready_is_503_and_says_why(self, no_model_factory):
        with TestClient(create_app()) as c:
            r = c.get("/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["ready"] is False
        assert body["checks"]["llm_credentials"]["ok"] is False
        assert body["checks"]["llm_credentials"]["providers"] == {
            "anthropic": False,
            "openai": False,
        }

    def test_an_agent_route_answers_503_not_500(self, no_model_factory, auth_headers):
        with TestClient(create_app(), headers=auth_headers) as c:
            r = c.post("/api/v1/contract/review", json=REVIEW)
        assert r.status_code == 503
        assert "credentials" in r.json()["detail"]
        # No exception text, no key fragments, no file paths.
        assert "Traceback" not in r.text
        assert "ANTHROPIC_API_KEY" not in r.text


class TestLazyModel:
    def test_the_model_is_built_on_first_use(self, no_model_factory):
        agent = ContractReviewerAgent()  # no credentials needed here
        assert "_llm_instance" not in agent.__dict__
        with pytest.raises(llm.LLMNotConfigured):
            agent.llm  # noqa: B018

    def test_the_test_factory_still_applies(self):
        agent = ContractReviewerAgent()
        model = agent.llm
        assert model is agent.llm  # cached after the first access

    def test_an_assigned_model_wins(self):
        agent = ContractReviewerAgent()
        agent.llm = "stand-in"
        assert agent.llm == "stand-in"


class TestErrorsAreNotEchoed:
    def test_unexpected_failures_are_a_generic_500(self, client, monkeypatch):
        async def boom(self, input_data):
            raise RuntimeError("secret path C:\\keys\\prod.pem and sk-abc123")

        monkeypatch.setattr(ContractReviewerAgent, "review", boom)
        r = client.post("/api/v1/contract/review", json=REVIEW)
        assert r.status_code == 500
        assert "sk-abc123" not in r.text
        assert "prod.pem" not in r.text
