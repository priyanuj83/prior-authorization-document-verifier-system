"""Lexical overlap. Exact terminology only; not a committed search engine."""

from __future__ import annotations

import re
from typing import Sequence

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "with",
    }
)


def tokenize(text: str) -> tuple:
    return tuple(
        token for token in _TOKEN.findall(text.lower()) if token not in _STOPWORDS
    )


def lexical_score(query_terms: Sequence[str], document: str) -> float:
    """Fraction of unique query tokens that appear in the document."""

    query = {token for term in query_terms for token in tokenize(term)}
    if not query:
        return 0.0
    document_tokens = set(tokenize(document))
    overlap = query & document_tokens
    return len(overlap) / len(query)
