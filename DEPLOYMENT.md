# Deployment

The previous version of this file was a 688-line guide for "LexPilot" that
told you to provision PostgreSQL, Stripe, Twilio, a `SECRET_KEY` and a
Kubernetes cluster, and to run a compose file with `POSTGRES_PASSWORD=password`.
The API connects to none of those. This is what the code needs.

## What the service needs

| | Required | Why |
|---|---|---|
| `API_KEY` | yes, in production | Every `/api/v1` route checks it; production refuses the placeholder |
| One of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | to serve agent calls | Without either the service boots, `/health` is 200, `/ready` is 503 and agent routes answer 503 |
| `CORS_ALLOW_ORIGINS` | if a browser calls it | Empty means no origin in production |
| A database, Pinecone, a message queue | no | `src/database.py` is unused; Pinecone is optional for case research |

Generate a key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Container

```bash
docker build -t legal-assistant .
docker run -d -p 8000:8000 -e API_KEY=... -e ANTHROPIC_API_KEY=... legal-assistant
curl -s localhost:8000/health
curl -s localhost:8000/ready          # 200 once a model key is present
```

The image runs as uid 10001 with `ENVIRONMENT=production`. Start it without
`API_KEY` and it exits with the reason. `/ready` is the readiness probe;
`/health` the liveness probe; the image's own `HEALTHCHECK` uses `/health`.

Or with compose, which starts the API and nothing else:

```bash
API_KEY=... ANTHROPIC_API_KEY=... docker compose up --build
```

## Without a container

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # set API_KEY and a model key
.venv/bin/python main.py serve --host 0.0.0.0 --port 8000
```

`main.py serve` binds to `127.0.0.1` unless told otherwise. Behind a reverse
proxy, terminate TLS there; the service does not.

## MCP server

```bash
python main.py mcp
```

Speaks MCP over stdio for a local client. It runs the same five agents with the
same model configuration; it has no network listener and no key check, because
its caller is the local user.

## Before exposing it

- `ENVIRONMENT=production` (the image sets it): hides the OpenAPI documents and
  refuses the placeholder key.
- Decide which provider receives client documents, and read that provider's
  data-handling terms; nothing here redacts a document before it is sent.
- Keep the server log where the service's access control applies: it holds the
  detail that responses deliberately omit.
- Read [docs/threat-model.md](docs/threat-model.md) for what remains open: one
  shared key, no rate limit, no audit log of submissions.
