"""Format signature extraction for string columns."""

from __future__ import annotations

import re
from collections import Counter


_TITLE_RE = re.compile(r"^(mr|mrs|ms|dr|prof|professor|sir|dame)\b\.?", re.IGNORECASE)
_MULTISPACE_RE = re.compile(r"\s{2,}")
_CODE_RE = re.compile(r"^[A-Za-z]+ ?\d+$")
_NUMERIC_RE = re.compile(r"^\d+$")
_DATE_ISO_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_DATE_SLASH_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
_DATE_TEXT_RE = re.compile(r"^[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}$")


def extract_format_signature(values) -> dict:
    """Extract generic, domain-agnostic format features."""
    stripped = []
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text.strip() == "":
            continue
        stripped.append(text)

    total = len(stripped)
    if total == 0:
        return {"total": 0}

    titles = 0
    non_titles = 0
    token_counts = Counter()
    delimiter_counts = Counter()
    whitespace_issues = 0
    casing_categories = Counter()
    code_like = 0
    non_code_like = 0
    numeric_only = 0
    alpha_only = 0
    date_formats = Counter()

    for text in stripped:
        if _TITLE_RE.search(text.strip()):
            titles += 1
        else:
            non_titles += 1

        tokens = [t for t in text.strip().split() if t]
        token_counts[len(tokens)] += 1

        if "," in text:
            delimiter_counts["comma"] += 1
        if "." in text:
            delimiter_counts["period"] += 1
        if "-" in text:
            delimiter_counts["hyphen"] += 1
        if "/" in text:
            delimiter_counts["slash"] += 1
        if ":" in text:
            delimiter_counts["colon"] += 1

        if text != text.strip() or _MULTISPACE_RE.search(text):
            whitespace_issues += 1

        letters = "".join(ch for ch in text if ch.isalpha())
        if letters:
            if letters.isupper():
                casing_categories["upper"] += 1
            elif letters.islower():
                casing_categories["lower"] += 1
            elif letters.istitle():
                casing_categories["title"] += 1
            else:
                casing_categories["mixed"] += 1

        if _CODE_RE.match(text.strip()):
            code_like += 1
        else:
            non_code_like += 1

        if _NUMERIC_RE.match(text.strip()):
            numeric_only += 1
        elif any(ch.isalpha() for ch in text):
            alpha_only += 1

        if _DATE_ISO_RE.match(text.strip()):
            date_formats["iso"] += 1
        elif _DATE_SLASH_RE.match(text.strip()):
            date_formats["slash"] += 1
        elif _DATE_TEXT_RE.match(text.strip()):
            date_formats["text"] += 1

    return {
        "total": total,
        "titles": titles,
        "non_titles": non_titles,
        "token_counts": set(token_counts.keys()),
        "delimiter_counts": dict(delimiter_counts),
        "whitespace_issues": whitespace_issues,
        "casing_categories": set(casing_categories.keys()),
        "code_like": code_like,
        "non_code_like": non_code_like,
        "numeric_only": numeric_only,
        "alpha_only": alpha_only,
        "date_formats": set(date_formats.keys()),
    }
