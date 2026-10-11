"""Support and contradiction channel query construction."""

from src.retrieval.contradiction_search.channels import (
    contradiction_query_terms,
    contradiction_query_text,
    support_query_terms,
    support_query_text,
)

__all__ = [
    "contradiction_query_terms",
    "contradiction_query_text",
    "support_query_terms",
    "support_query_text",
]
