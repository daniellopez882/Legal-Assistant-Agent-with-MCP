# ADR 0002 — Route by verbs of intent, then topic nouns; break ties by an explicit order

**Status:** accepted · **Date:** 2026-09-06 (records the decision made in PR #1)

## Context

The orchestrator chose an agent with a flat keyword table scored one point per
substring hit, ties resolved by dictionary insertion order. Three request
types went to the wrong agent:

| Request | Scored | Reached | Should reach |
|---|---|---|---|
| "Create time entry report" | drafting 1 ("create") – billing 1 ("time entry") | drafting, declared first | billing |
| "When is the statute of limitations?" | case_research 1 – deadline 1 | case_research | deadline |
| "Bill the client for work done" | zero everywhere: the keyword was the phrase "bill client", which "the" breaks | the CASE_RESEARCH default | billing |

In a tool that tracks legal deadlines and bills clients, a misrouted request is
not a cosmetic error.

## Decision

`src/task_classifier.py` owns routing, outside the orchestrator so it can be
tested without constructing one.

1. **Verbs of intent are scored before topic nouns**, because intent is what
   selects an agent. "Draft an NDA agreement" is a drafting request although it
   names two contract nouns; "When is the statute of limitations?" has no verb
   and is settled by its noun.
2. **Matching is on word boundaries and tolerates intervening words**, so
   "bill the client" matches the billing intent.
3. **Ties fall back to an explicit priority order**, written down in the module,
   never to dictionary order.
4. `explain()` returns why a request routed where it did, for when a decision is
   disputed.

## Consequences

- The routing table is tested exhaustively in `tests/test_task_classifier.py`;
  the three cases above are regression tests.
- Adding a task type means adding its verbs, nouns and a place in the priority
  order, in one file.
- Classification is still lexical. A request that names no known verb or noun
  falls to the default, and the default is case research, which is the least
  consequential agent. A model-based classifier would be a new ADR.
