"""Embedding-style semantic retrieval for skill and helper routing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import math
import re
from typing import Iterable, Sequence

from .models import HelperSpec, SkillSpec
from .skill_catalog import SkillCatalogDocument, build_skill_catalog_documents

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]*")
_MIN_SCORE = 0.20
_MIN_MARGIN = 0.025


@dataclass(frozen=True)
class SemanticSkillMatch:
    skill: SkillSpec
    score: float
    evidence: tuple[SkillCatalogDocument, ...]


def semantic_detect_skills(user_question: str, top_k: int = 3) -> list[SemanticSkillMatch]:
    """Return semantic skill candidates using local embedding similarity.

    This is intentionally conservative: unrelated or low-margin questions
    return no matches so deterministic keyword routing remains the precision
    guardrail.
    """

    from .registry import all_skills

    question = (user_question or "").strip()
    if not question:
        return []

    docs = _catalog_documents()
    scored_docs = _rank_documents(question, docs)
    by_skill: dict[str, list[tuple[float, SkillCatalogDocument]]] = {}
    for score, doc in scored_docs:
        by_skill.setdefault(doc.skill_name, []).append((score, doc))

    skills_by_name = {skill.name: skill for skill in all_skills()}
    matches: list[SemanticSkillMatch] = []
    for skill_name, scored in by_skill.items():
        best_score = scored[0][0]
        evidence = tuple(doc for _, doc in scored[:3])
        if best_score > 0:
            matches.append(SemanticSkillMatch(skills_by_name[skill_name], best_score, evidence))
    matches.sort(key=lambda match: match.score, reverse=True)

    if not matches:
        return []
    if matches[0].score < _MIN_SCORE:
        return []
    if len(matches) > 1 and (matches[0].score - matches[1].score) < _MIN_MARGIN:
        return []
    return matches[:top_k]


def retrieve_skill_context(user_question: str, top_k: int = 3) -> str:
    matches = semantic_detect_skills(user_question, top_k=top_k)
    if not matches:
        return ""

    lines = [
        "**RETRIEVED SKILL CONTEXT (LANGCHAIN/RAG SEMANTIC ROUTING):**",
        "The following skill/helper context was retrieved from the SheetHero capability catalog. "
        "Use it as grounding evidence, but keep runtime schema checks authoritative.",
    ]
    for match in matches:
        lines.append(f"- Skill `{match.skill.name}` similarity={match.score:.3f}")
        helper_names = [
            doc.helper_name for doc in match.evidence
            if doc.helper_name
        ]
        if helper_names:
            unique_helpers = []
            for helper_name in helper_names:
                if helper_name not in unique_helpers:
                    unique_helpers.append(helper_name)
            lines.append(f"  Candidate helpers: {', '.join(f'`{name}`' for name in unique_helpers[:4])}")
        snippets = [_compact(doc.text) for doc in match.evidence[:2]]
        for snippet in snippets:
            lines.append(f"  Evidence: {snippet}")
    return "\n".join(lines)


def semantic_select_helper(skill: SkillSpec, user_question: str) -> HelperSpec | None:
    helper_docs = [
        doc for doc in _catalog_documents()
        if doc.kind == "helper" and doc.skill_name == skill.name
    ]
    ranked = _rank_documents(user_question, helper_docs)
    if not ranked or ranked[0][0] < _MIN_SCORE:
        return None
    helper_name = ranked[0][1].helper_name
    return next((helper for helper in skill.helpers if helper.name == helper_name), None)


@lru_cache(maxsize=1)
def _catalog_documents() -> tuple[SkillCatalogDocument, ...]:
    from .registry import all_skills

    return tuple(build_skill_catalog_documents(all_skills()))


def _rank_documents(
    query: str,
    documents: Sequence[SkillCatalogDocument],
) -> list[tuple[float, SkillCatalogDocument]]:
    query_vec = _embed(query)
    scored = [
        (_cosine(query_vec, _embed(doc.text)), doc)
        for doc in documents
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _embed(text: str) -> Counter[str]:
    tokens = _normalize_tokens(_TOKEN_RE.findall((text or "").lower()))
    counts: Counter[str] = Counter(tokens)
    for left, right in zip(tokens, tokens[1:]):
        counts[f"{left}_{right}"] += 1
    return counts


def _normalize_tokens(tokens: Iterable[str]) -> list[str]:
    aliases = {
        "jobs": "task",
        "job": "task",
        "tasks": "task",
        "dependencies": "dependency",
        "depends": "dependency",
        "before": "dependency",
        "after": "dependency",
        "ordered": "schedule",
        "order": "schedule",
        "plan": "schedule",
        "relationship": "correlation",
        "relationships": "correlation",
        "estimate": "regression",
        "predict": "regression",
        "prediction": "regression",
        "passenger": "dataset",
        "passengers": "dataset",
        "combine": "merge",
        "join": "merge",
        "summarize": "summary",
        "summarise": "summary",
        "average": "mean",
        "averages": "mean",
    }
    stop = {
        "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
        "where", "some", "must", "happen", "create", "make", "data", "file",
        "spreadsheet", "workbook", "table",
    }
    normalized = []
    for token in tokens:
        token = aliases.get(token, token)
        if token not in stop and len(token) > 1:
            normalized.append(token)
    return normalized


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(value * right.get(token, 0) for token, value in left.items())
    if numerator == 0:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm)


def _compact(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."
