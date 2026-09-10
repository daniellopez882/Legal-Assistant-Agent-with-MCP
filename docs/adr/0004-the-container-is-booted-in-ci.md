# ADR 0004 — The container is booted and probed in CI; readiness reports what is missing

**Status:** accepted · **Date:** 2026-09-06

## Context

The pull request added a CI job that built the Docker image. It never ran it.
Running the original image for the first time, with no environment beyond a
port mapping, gave:

```
src.llm.LLMNotConfigured: claude-sonnet-5 needs ANTHROPIC_API_KEY, which is unset or still a placeholder.
```

exit code 1, three seconds after start, `/health` never answered. Every agent
built its model in `__init__` and `create_app()` built every agent (ADR 0001).
Around that: a single-stage image with `gcc` and `postgresql-client` in the
runtime layer (1.37 GB), uid 1000, `uvicorn src.server.server:create_app`
without `--factory` (uvicorn detected the factory and warned on each start),
`curl` installed for the health check, and no `.dockerignore`, so `COPY . .`
took `.git`, the local virtualenv and any developer `.env` into a layer.
`docker-compose.yml` started a Postgres that nothing connects to and a pgAdmin
with `admin/admin`.

## Decision

1. **Two stages.** Dependencies are built into `/opt/venv` in a builder stage;
   the runtime stage is `python:3.12-slim` plus that virtualenv and the source.
2. **Non-root.** A system user with uid 10001 owns `/app`; CI asserts the image
   does not run as root.
3. **Explicit factory.** `uvicorn src.server.server:create_app --factory`, exec
   form, graceful shutdown timeout, no server header.
4. **The probe is Python.** `HEALTHCHECK` uses `urllib`, so `curl` is not in the
   image.
5. **Production by default.** The image sets `ENVIRONMENT=production`, so it
   refuses to start with the placeholder `API_KEY`. `docker-compose.yml` marks
   `API_KEY` required (`${API_KEY:?...}`) and starts only the API.
6. **`/ready` says what is missing.** It reports each provider's credential
   state and whether the key is safe for the environment, with `503` until both
   hold. A container without model keys is *up and not ready*, visibly, instead
   of dead.
7. **CI boots the image** with only `API_KEY` set and asserts: `/health` is 200;
   `/ready` is 503 with `llm_credentials.ok == false`; an unauthenticated agent
   call is 401; a production start with the placeholder key is refused; the
   process is not root.
8. `.dockerignore` excludes `.git`, virtualenvs, caches, tests, docs and every
   `.env` but `.env.example`.

## Consequences

- A regression of the kind that motivated this — a startup-time dependency on
  a secret — fails CI instead of being found by whoever deploys next.
- The image cannot be started in development mode by accident; set
  `ENVIRONMENT=development` explicitly to get the OpenAPI documents and the
  placeholder key.
- The database models in `src/database.py` are still importable and still
  unused; the compose file no longer pretends otherwise. Wiring persistence is
  future work and would bring Postgres back with it.
