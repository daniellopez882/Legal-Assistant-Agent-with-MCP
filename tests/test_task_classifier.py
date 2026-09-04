"""
Tests for src.task_classifier.

Routing used to be a flat keyword table scored one point per substring hit,
with ties resolved by dictionary insertion order. Three of the suite's own
cases went to the wrong agent:

* "Create time entry report" tied drafting 1 - billing 1 on "create" versus
  "time entry"; drafting was declared first, so a billing request reached the
  drafting agent.
* "When is the statute of limitations?" tied case_research 1 - deadline 1 the
  same way.
* "Bill the client for work done" scored zero everywhere, because the keyword
  was the phrase "bill client" and the text has "the" in between. It fell
  through to the CASE_RESEARCH default.

The table is cheap to evaluate exhaustively, so it is.
"""

from __future__ import annotations

import pytest

from src.task_classifier import DEFAULT_TASK, PRIORITY, RULES, classify, explain, score


class TestRoutingCases:
    """Every phrasing the suite and the README claim to support."""

    @pytest.mark.parametrize(
        "text",
        [
            "Review this contract for risks",
            "Check the agreement for unfavorable terms",
            "Analyze this NDA for problematic clauses",
            "Find risks in this service agreement",
            "Redline the master services agreement",
        ],
    )
    def test_contract_review(self, text):
        assert classify(text) == "contract_review", explain(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Find cases similar to this one",
            "Research precedents for breach of contract",
            "Look up statute of limitations in Texas",
            "Search for relevant case law",
        ],
    )
    def test_case_research(self, text):
        assert classify(text) == "case_research", explain(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Draft an NDA agreement",
            "Create a demand letter",
            "Write a contract template",
            "Prepare a motion to dismiss",
        ],
    )
    def test_drafting(self, text):
        assert classify(text) == "drafting", explain(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Check filing deadlines for this case",
            "When is the statute of limitations?",
            "Track court dates and deadlines",
            "Generate docket report",
        ],
    )
    def test_deadline(self, text):
        assert classify(text) == "deadline", explain(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Generate invoice for this matter",
            "Calculate billing hours",
            "Create time entry report",
            "Bill the client for work done",
        ],
    )
    def test_billing(self, text):
        assert classify(text) == "billing", explain(text)


class TestTheSpecificRegressions:
    def test_time_entry_beats_create(self):
        """Was drafting: tie broken by dictionary order."""
        assert classify("Create time entry report") == "billing"

    def test_statute_of_limitations_without_a_verb_is_a_deadline(self):
        """Was case_research: same tie-break bug."""
        assert classify("When is the statute of limitations?") == "deadline"

    def test_statute_of_limitations_with_a_research_verb_is_research(self):
        """The verb carries the intent; the noun only carries the topic."""
        assert classify("Look up statute of limitations in Texas") == "case_research"

    def test_bill_the_client_matches_across_intervening_words(self):
        """Was zero-scoring: 'bill client' never matched 'bill the client'."""
        assert classify("Bill the client for work done") == "billing"

    def test_an_action_verb_outweighs_topic_nouns(self):
        """'Draft an NDA agreement' names two contract nouns but one drafting verb."""
        assert classify("Draft an NDA agreement") == "drafting"

    def test_find_is_disambiguated_by_its_object(self):
        assert classify("Find cases similar to this one") == "case_research"
        assert classify("Find risks in this service agreement") == "contract_review"


class TestScoringMechanics:
    def test_unmatched_text_takes_the_documented_default(self):
        assert classify("aaaa bbbb cccc") == DEFAULT_TASK

    def test_empty_input_does_not_raise(self):
        assert classify("") == DEFAULT_TASK

    def test_word_boundaries_are_respected(self):
        """'bill' must not match inside 'billboard'."""
        assert score("a billboard advertisement")["billing"] == 0

    def test_scores_are_reported_for_every_task(self):
        assert set(score("draft a motion")) == set(RULES)

    def test_priority_covers_every_task(self):
        """A tie must always be resolvable."""
        assert set(PRIORITY) == set(RULES)

    def test_explain_names_the_decision(self):
        assert "billing" in explain("Bill the client for work done")

    def test_classification_is_deterministic(self):
        text = "Create time entry report"
        assert len({classify(text) for _ in range(20)}) == 1

    def test_case_is_ignored(self):
        assert classify("DRAFT AN NDA AGREEMENT") == classify("draft an nda agreement")
