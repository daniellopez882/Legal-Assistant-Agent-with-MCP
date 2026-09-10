"""
src/task_classifier.py
Route a free-text request to the agent that should handle it.

This was a dictionary of flat keyword lists inside the orchestrator, scored one
point per substring hit, with ties resolved by dictionary insertion order.
Three requests routed to the wrong agent:

| Request | Went to | Should be | Why |
|---|---|---|---|
| "Create time entry report" | drafting | billing | tie 1-1 on "create" vs "time entry"; drafting declared first |
| "When is the statute of limitations?" | case research | deadline | tie 1-1; case research declared first |
| "Bill the client for work done" | case research | billing | the keyword was the phrase "bill client", which never matches with "the" in between, so nothing scored and it hit the default |

The model here separates two kinds of evidence:

* **Actions** are verbs that name an intent. They dominate, because intent is
  what selects the agent. "Draft an NDA agreement" is a drafting request even
  though it names two contract nouns.
* **Terms** are domain nouns. They decide when no action verb is present:
  "When is the statute of limitations?" has no verb of intent, so the deadline
  term settles it, while "Look up statute of limitations" carries a research
  verb and goes to research.

Deliberately still deterministic and rule-based. Classification is on the hot
path of every request, and a rule table can be tested exhaustively for free --
which the suite now does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# An action outweighs any realistic number of topic nouns, so a clear verb of
# intent is never outvoted by the subject it operates on.
ACTION_WEIGHT = 100
TERM_WEIGHT = 30
WEAK_WEIGHT = 10


@dataclass(frozen=True)
class Rules:
    actions: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()
    weak: tuple[str, ...] = ()


#: task key -> rules. Keys are the TaskType *values*, so this module does not
#: import the model layer and can be tested on its own.
RULES: dict[str, Rules] = {
    "contract_review": Rules(
        actions=("review", "analyze", "analyse", "redline"),
        terms=(
            "contract",
            "agreement",
            "nda",
            "msa",
            "sow",
            "lease",
            "amendment",
            "clause",
            "clauses",
            "terms",
            "risks",
            "unfavorable terms",
            "indemnity",
            "liability cap",
            "termination clause",
        ),
        weak=("check", "look at"),
    ),
    "case_research": Rules(
        actions=("research", "look up", "search", "find cases", "find case law"),
        terms=(
            "case law",
            "caselaw",
            "precedent",
            "precedents",
            "cases",
            "citation",
            "citations",
            "ruling",
            "rulings",
            "authority",
            "jurisprudence",
        ),
        weak=("find", "similar"),
    ),
    "drafting": Rules(
        actions=("draft", "write", "prepare", "compose"),
        terms=(
            "demand letter",
            "engagement letter",
            "template",
            "pleading",
            "motion",
            "brief",
            "memorandum",
            "complaint",
            "letter",
        ),
        weak=("create", "generate", "document"),
    ),
    "deadline": Rules(
        actions=("track", "diarise", "diarize", "calendar"),
        terms=(
            "deadline",
            "deadlines",
            "filing deadline",
            "filing",
            "docket",
            "court date",
            "court dates",
            "due date",
            "statute of limitations",
            "response due",
            "hearing",
            "limitation period",
        ),
        weak=("when is", "how long"),
    ),
    "billing": Rules(
        actions=("bill", "invoice"),
        terms=(
            "billing",
            "billable",
            "invoice",
            "invoices",
            "time entry",
            "time entries",
            "time tracking",
            "hours",
            "fees",
            "disbursements",
            "generate invoice",
        ),
        weak=("charge", "cost"),
    ),
}

#: Applied only when weighted scores tie. Specialised agents beat general ones.
PRIORITY: tuple[str, ...] = (
    "billing",
    "deadline",
    "contract_review",
    "drafting",
    "case_research",
)

#: Returned when nothing matches at all. Documented default, not a tie-break.
DEFAULT_TASK = "case_research"


def _matches(phrase: str, text: str) -> bool:
    """
    Word-boundary match, tolerant of intervening whitespace/punctuation.

    ``bill`` matches "Bill the client" but not "billboard", and ``bill client``
    matches "bill the client" -- the old exact-substring test did neither.
    """
    pattern = r"\b" + r"\W+(?:\w+\W+){0,2}?".join(re.escape(w) for w in phrase.split()) + r"\b"
    return re.search(pattern, text) is not None


def score(text: str) -> dict[str, int]:
    """Weighted score per task. Exposed so tests can explain a decision."""
    lowered = text.lower()
    scores: dict[str, int] = {}
    for task, rules in RULES.items():
        total = 0
        for phrase in rules.actions:
            if _matches(phrase, lowered):
                total += ACTION_WEIGHT
        for phrase in rules.terms:
            if _matches(phrase, lowered):
                total += TERM_WEIGHT
        for phrase in rules.weak:
            if _matches(phrase, lowered):
                total += WEAK_WEIGHT
        scores[task] = total
    return scores


def classify(text: str) -> str:
    """Return the task key that should handle this request."""
    scores = score(text)
    best = max(scores.values()) if scores else 0
    if best == 0:
        return DEFAULT_TASK

    winners = [task for task, value in scores.items() if value == best]
    if len(winners) == 1:
        return winners[0]
    for candidate in PRIORITY:
        if candidate in winners:
            return candidate
    return winners[0]


def explain(text: str) -> str:
    """Human-readable breakdown. Useful when a routing decision is disputed."""
    scores = score(text)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    parts = ", ".join(f"{task}={value}" for task, value in ranked if value)
    return f"{text!r} -> {classify(text)} ({parts or 'no matches, default'})"
