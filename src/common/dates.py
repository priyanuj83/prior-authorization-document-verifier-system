"""Date parsing helpers used by deterministic policy matching."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union


DateLike = Union[date, datetime, str, None]


def parse_date(value: DateLike) -> Optional[date]:
    """Parse a YAML/ISO date, returning None for missing values."""

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"null", "none"}:
        return None
    return date.fromisoformat(text[:10])


def require_date(value: DateLike, field_name: str) -> date:
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"{field_name} is required and must be a YYYY-MM-DD date")
    return parsed


def iso(value: DateLike) -> Optional[str]:
    parsed = parse_date(value)
    return None if parsed is None else parsed.isoformat()
