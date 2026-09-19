from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


def _stringify(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.date().isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _stringify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify(v) for v in obj]
    return obj


def load_yaml(path: Path) -> Any:
    with path.open() as f:
        return yaml.safe_load(f)


def dump_yaml(path: Path, data: Any, header: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _stringify(data)
    body = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        width=96,
        default_flow_style=False,
    )
    text = (header.rstrip() + "\n\n" + body) if header else body
    path.write_text(text)


def iso(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value)[:10]
