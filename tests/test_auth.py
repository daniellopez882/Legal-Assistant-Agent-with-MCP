"""
Every /api/v1 route requires X-API-Key; the probes do not.

Before: every agent route was open. Anyone who could reach the port could
submit a client's contract to the configured model provider and spend the
operator's credit. A JWT module existed, with open self-registration into an
in-memory dict and a default signing secret, and no agent route used it.
"""

from __future__ import annotations

import pytest

from src.config import INSECURE_API_KEY, Settings

PROTECTED = [
    ("post", "/api/v1/contract/review"),
    ("post", "/api/v1/case/research"),
    ("post", "/api/v1/document/draft"),
    ("post", "/api/v1/deadlines/check"),
    ("post", "/api/v1/billing/calculate"),
    ("post", "/api/v1/orchestrate"),
    ("get", "/api/v1/templates"),
    ("post", "/api/v1/validate/time-description?description=x"),
]


class TestAuthentication:
    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_rejected_without_a_key(self, anon_client, method, path):
        assert getattr(anon_client, method)(path).status_code == 401

    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_rejected_with_a_wrong_key(self, anon_client, method, path):
        r = getattr(anon_client, method)(path, headers={"X-API-Key": "not-the-key"})
        assert r.status_code == 401

    def test_rejection_names_the_scheme(self, anon_client):
        r = anon_client.get("/api/v1/templates")
        assert r.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_error_body_does_not_leak_the_expected_key(self, anon_client, api_key):
        r = anon_client.get("/api/v1/templates", headers={"X-API-Key": "wrong"})
        assert api_key not in r.text

    def test_valid_key_is_accepted(self, client):
        assert client.get("/api/v1/templates").status_code == 200

    def test_the_old_jwt_routes_are_gone(self, anon_client):
        assert anon_client.post("/api/v1/auth/register", json={}).status_code in (404, 401)
        assert anon_client.post("/api/v1/auth/login").status_code in (404, 401)


class TestOpenRoutes:
    def test_root_needs_no_key(self, anon_client):
        assert anon_client.get("/").status_code == 200

    def test_health_needs_no_key(self, anon_client):
        r = anon_client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"
        # Timezone-aware: the previous timestamp was a naive utcnow().
        assert r.json()["timestamp"].endswith(("Z", "+00:00"))

    def test_ready_needs_no_key(self, anon_client):
        assert anon_client.get("/ready").status_code in (200, 503)


class TestProductionGuard:
    def test_production_refuses_the_placeholder_key(self):
        with pytest.raises(ValueError, match="API_KEY"):
            Settings(environment="production", api_key=INSECURE_API_KEY)

    def test_production_starts_with_a_real_key(self):
        settings = Settings(environment="production", api_key="a-real-looking-key")
        assert settings.is_production
        assert not settings.has_insecure_api_key

    def test_development_tolerates_the_placeholder(self):
        settings = Settings(environment="development", api_key=INSECURE_API_KEY)
        assert settings.has_insecure_api_key
        assert not settings.is_production


class TestCors:
    def test_origins_parse_from_a_comma_separated_string(self):
        s = Settings(cors_allow_origins="https://a.example, https://b.example ,")
        assert s.cors_origins == ["https://a.example", "https://b.example"]

    def test_no_origins_by_default(self):
        assert Settings().cors_origins == []

    def test_preflight_from_an_unknown_origin_is_not_allowed(self, anon_client):
        r = anon_client.options(
            "/api/v1/templates",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.headers.get("access-control-allow-origin") != "https://evil.example"
        assert r.headers.get("access-control-allow-origin") != "*"
