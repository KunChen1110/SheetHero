"""Retrieval catalog for SheetHero skills and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import HelperSpec, SkillSpec


@dataclass(frozen=True)
class SkillCatalogDocument:
    kind: str
    skill_name: str
    helper_name: str | None
    text: str


_SKILL_EXAMPLES: dict[str, tuple[str, ...]] = {
    "merge": (
        "join files by shared id",
        "merge related tables using common keys",
        "fill missing values from reference workbook",
        "combine multiple spreadsheets",
    ),
    "aggregate": (
        "summarise totals and averages by group",
        "group rows by department, month, region, category",
        "build utilisation and grouped comparison summaries",
    ),
    "statistical": (
        "correlation matrix, feature correlation, regression coefficients",
        "predict target from numeric features",
        "estimate relationship between fare, age, survival, salary, performance, and other factors",
        "measure how one column relates to another target column",
        "detect graph cycles",
    ),
    "schedule": (
        "schedule tasks with dependencies and durations",
        "ordered plan where jobs must happen before others",
        "allocate students or entities to rooms, slots, or resources with capacity",
    ),
    "scan": (
        "find missing values, blank cells, invalid identifiers",
        "audit spreadsheet for data quality issues",
    ),
    "rank": (
        "score entities with weighted formula and rank them",
        "leaderboard, top candidates, weighted composite score",
    ),
    "financial": (
        "cash flow efficiency, gross profit, net profit, EOQ, reorder point",
        "financial dashboard comparing actuals to targets",
    ),
    "proportion": (
        "percentage share, regional share, market share, expenditure per person",
        "part of total and proportional allocation",
    ),
    "highlight": (
        "highlight rows or cells that satisfy a condition",
        "mark highest, lowest, threshold, exceptions",
    ),
}


def build_skill_catalog_documents(skills: Sequence[SkillSpec]) -> list[SkillCatalogDocument]:
    documents: list[SkillCatalogDocument] = []
    for skill in skills:
        examples = " ".join(_SKILL_EXAMPLES.get(skill.name, ()))
        helper_text = " ".join(
            f"{helper.name}: {helper.description}" for helper in skill.helpers
        )
        documents.append(
            SkillCatalogDocument(
                kind="skill",
                skill_name=skill.name,
                helper_name=None,
                text=(
                    f"Skill {skill.name}. Examples: {examples}. "
                    f"Strategy: {skill.strategy_doc[:1200]}. Helpers: {helper_text}"
                ),
            )
        )
        for helper in skill.helpers:
            documents.append(_helper_document(skill, helper, examples))
    return documents


def _helper_document(skill: SkillSpec, helper: HelperSpec, skill_examples: str) -> SkillCatalogDocument:
    return SkillCatalogDocument(
        kind="helper",
        skill_name=skill.name,
        helper_name=helper.name,
        text=(
            f"Skill {skill.name}. Helper {helper.name}. "
            f"Description: {helper.description}. "
            f"Relevant user intents: {skill_examples}. "
            f"Use this helper when the task needs {helper.description}."
        ),
    )
