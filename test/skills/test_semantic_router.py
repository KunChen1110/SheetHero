import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.skills.semantic_router import retrieve_skill_context, semantic_detect_skills


def test_semantic_router_recovers_schedule_without_exact_keywords():
    matches = semantic_detect_skills(
        "Create an ordered plan for jobs where some jobs must happen before others."
    )

    assert matches
    assert matches[0].skill.name == "schedule"
    assert matches[0].score >= 0.20


def test_semantic_router_does_not_match_unrelated_question():
    matches = semantic_detect_skills("what is the meaning of life")

    assert matches == []


def test_retrieved_skill_context_mentions_helpers_and_rag_evidence():
    context = retrieve_skill_context(
        "Estimate relationship between fare, age, and survival in the passenger data.",
        top_k=2,
    )

    assert "RETRIEVED SKILL CONTEXT" in context
    assert "statistical" in context
    assert "fit_linear_regression_weights" in context or "compute_feature_correlations" in context
