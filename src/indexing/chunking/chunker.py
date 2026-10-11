"""Section-aware clinical chunking.

The exact section grammar is still open. This splitter recognizes markdown
headings and bold clinical labels, and keeps Assessment together with a
following Plan. It does not use a fixed token window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_BOLD_LABEL = re.compile(r"^\*\*([^*]+?)\*\*\s*:?\s*(.*)$")


@dataclass(frozen=True)
class NoteChunk:
    section: str
    text: str
    index: int


def chunk_note_body(body: str) -> Tuple[NoteChunk, ...]:
    sections = _split_sections(body)
    merged = _merge_assessment_and_plan(sections)
    if len(merged) == 1 and merged[0][0] == "preamble":
        text = merged[0][1].strip()
        if not text:
            return ()
        return (NoteChunk(section="document", text=text, index=0),)
    chunks: List[NoteChunk] = []
    for section, text in merged:
        cleaned = text.strip()
        if not cleaned:
            continue
        chunks.append(NoteChunk(section=section, text=cleaned, index=len(chunks)))
    if not chunks and body.strip():
        chunks.append(NoteChunk(section="document", text=body.strip(), index=0))
    return tuple(chunks)


def _split_sections(body: str) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, List[str]]] = []
    current_name = "preamble"
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_lines
        if any(line.strip() for line in current_lines):
            sections.append((current_name, current_lines))
        current_lines = []

    for line in body.splitlines():
        heading = _heading_name(line)
        if heading is None:
            current_lines.append(line)
            continue
        flush()
        current_name = heading[0]
        current_lines = [line]
    flush()
    return [(name, "\n".join(lines).strip()) for name, lines in sections]


def _heading_name(line: str) -> Tuple[str, str] | None:
    stripped = line.strip()
    markdown = _MARKDOWN_HEADING.match(stripped)
    if markdown:
        return markdown.group(1).strip(), ""
    bold = _BOLD_LABEL.match(stripped)
    if bold:
        return bold.group(1).strip(), bold.group(2).strip()
    return None


def _merge_assessment_and_plan(sections: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    merged: List[Tuple[str, str]] = []
    index = 0
    while index < len(sections):
        name, text = sections[index]
        if (
            name.lower() == "assessment"
            and index + 1 < len(sections)
            and sections[index + 1][0].lower() == "plan"
        ):
            plan_text = sections[index + 1][1]
            merged.append(("Assessment / Plan", "\n\n".join(part for part in (text, plan_text) if part)))
            index += 2
            continue
        merged.append((name, text))
        index += 1
    return merged
