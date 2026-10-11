"""Parse a clinical note into front matter and body. Does not read gold files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

import yaml


@dataclass(frozen=True)
class ParsedNote:
    front_matter: Mapping[str, Any]
    body: str


def parse_note(text: str) -> ParsedNote:
    front_matter, body = _split_front_matter(text)
    return ParsedNote(front_matter=front_matter, body=body)


def _split_front_matter(text: str) -> Tuple[Mapping[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :]).strip("\n")
            loaded = yaml.safe_load(raw) or {}
            if not isinstance(loaded, dict):
                return {}, text
            return loaded, body
    return {}, text
