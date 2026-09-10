# ADR 0001 — One place builds the chat model, and it is built on first use

**Status:** accepted · **Date:** 2026-09-06 (the factory records the decision made in PR #1; the laziness was added in the follow-up)

## Context

Each of the five agents constructed its own client inline:

```python
if "claude" in self.model_name.lower():
    self.llm = ChatAnthropic(model=..., api_key=settings.anthropic_api_key, ...)
else:
    self.llm = ChatOpenAI(model=..., api_key=settings.openai_api_key, ...)
```

Three things followed. There was no seam to substitute a model, so every API
test made a real network call: six failed with `Error code: 401 - API key is
invalid` because no key was present, and with a valid key the suite would have
spent money. `config.py` shipped `openai_api_key = "sk-placeholder"`, and a
client was built happily with it, so the failure surfaced as a 500 at request
time rather than as a configuration error. And the defaults named
`claude-3-5-sonnet-20241022`, a retired model.

The pull request introduced `src.llm.get_chat_model` as the single constructor,
with `set_model_factory` as the test seam and placeholder detection that fails
fast. It kept one habit: every agent still called `get_chat_model` in
`__init__`, and `create_app()` constructs every agent. Booting the container
for the first time showed the cost — with no credentials configured the process
raised `LLMNotConfigured` during `create_app()` and exited before serving
`/health`. CI had built the image on every run and never started it.

## Decision

1. `src.llm.get_chat_model` remains the only place a chat model is built. It
   recognises placeholder keys and raises `LLMNotConfigured`; `fallback_model`
   is a configuration-time fallback, not a retry.
2. Agents declare `llm = LazyChatModel()` and set `model_name` and
   `llm_options` in `__init__`. The model is built on the first attribute
   access, through the factory, and cached on the instance. Assigning
   `agent.llm = ...` overrides it.
3. `tests/conftest.py` installs a deterministic `GenericFakeChatModel` for the
   whole session, so no test can reach a provider. A test that needs a live
   model is marked `requires_api` and skipped unless credentials exist. CI
   asserts the fixture is still installed and that no agent builds a client
   directly.
4. The API maps `LLMNotConfigured` to `503` with a message that points at
   `/ready`, which reports per provider whether a usable key exists.

## Consequences

- The service boots, serves `/health`, and answers `/ready` truthfully with no
  credentials at all; the first agent call on a missing provider is a 503, not a
  crash at startup.
- Swapping providers or adding one is a change to `src/llm.py`.
- Constructing an agent is cheap and side-effect free, which the MCP server
  (which builds an agent per tool call) and the tests both rely on.
- A model is built once per agent instance; per-request temperature changes
  would need a new agent, which nothing here does.
