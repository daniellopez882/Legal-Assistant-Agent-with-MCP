# ADR 0003 — One API key on every agent route; the in-memory JWT scheme is removed; production fails closed

**Status:** accepted · **Date:** 2026-09-06

## Context

Every `/api/v1` route was open. Anyone who could reach the port could submit a
client's contract to the configured model provider, run legal research, draft
documents and spend the operator's credit — with no record of who did it.

The repository had `src/auth.py`: JWT access and refresh tokens, bcrypt password
hashing, role checks, and login, register, refresh and `/me` routes. Read
closely, it protected nothing:

- The user store was a dict inside `register_auth_routes`. It was empty on every
  start, and `POST /api/v1/auth/register` had no gate, so anyone could create an
  account and log in.
- Tokens were signed with `settings.secret_key`, default `"dev-secret-key"`, so
  anyone who had read the repository could forge one.
- Not one agent route depended on `require_auth`. Only `/api/v1/auth/me` did.

Its dependencies (`python-jose`, `passlib`, `python-multipart`) were the only
users of those packages.

## Decision

1. `src/auth.py` is now the API-key dependency: `require_api_key` compares the
   `X-API-Key` header in constant time against `settings.api_key` and answers
   `401` with `WWW-Authenticate: X-API-Key` otherwise. Every route under
   `/api/v1` depends on it; `/`, `/health` and `/ready` do not.
2. `Settings.api_key` defaults to `changeme-in-production` so development works
   with no secret, and `Settings` refuses to construct in `production` while the
   key is that placeholder. The image runs with `ENVIRONMENT=production`, so a
   container started without `API_KEY` exits with the reason, and CI asserts
   that it does.
3. The JWT scheme, its routes, its settings (`secret_key`, `encryption_key`) and
   its three dependencies are gone. Per-user identity is a documented limit,
   not a half-built feature.
4. CORS is configuration: `CORS_ALLOW_ORIGINS`, the localhost dev origins by
   default in development, no origin in production. It was `*` with credentials.
5. Route failures no longer return `str(e)`. A missing credential is a `503`
   that points at `/ready`; anything else is a `500` whose detail is in the
   server log.

## Consequences

- One shared key: adequate for a single firm's internal deployment, wrong for a
  multi-tenant product. Adding real users means a user store first, then
  tokens — in that order, and as a new ADR.
- Development runs with the insecure default and no warning beyond `/ready`
  reporting it; production refuses it. The distinction rests on `ENVIRONMENT`,
  so that variable must be set correctly in deployment (the image sets it).
- The OpenAPI documents are served only outside production.
- `tests/test_auth.py` pins every protected route, the open probes, the header,
  the production refusal and the CORS default; the CI docker job boots the image
  and asserts the `401` and the refusal from outside.
