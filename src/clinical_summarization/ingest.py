"""Ingest & normalize: parse a line-numbered note and tag each line.

Real ingestion has to normalize across EHR exports, dictation, and OCR'd text
(docs/design.md, Section 4) before line numbers can be trusted as citation
currency. This stub assumes clean, pre-line-numbered input and does keyword
tagging only, to keep the vertical slice deterministic.
"""

from __future__ import annotations

import re

from clinical_summarization.models import SourceLine

_TAG_RULES: dict[str, re.Pattern[str]] = {
    "medication": re.compile(r"\b(mg|bid|tid|qd|dose|continued on discharge)\b", re.I),
    "order": re.compile(r"\bordered\b", re.I),
    "functional_status": re.compile(r"\b(tolerating|ambulating|ambulatory)\b", re.I),
}


def tag_line(text: str) -> tuple[str, ...]:
    return tuple(tag for tag, pattern in _TAG_RULES.items() if pattern.search(text))


def parse_note(raw_note: str) -> list[SourceLine]:
    """Parse lines of the form 'line 42 — text' or plain numbered lines."""
    lines: list[SourceLine] = []
    for raw_line in raw_note.strip().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        match = re.match(r"^(?:line\s+)?(\d+)\s*[—\-:]\s*(.+)$", raw_line, re.I)
        if not match:
            continue
        line_no, text = int(match.group(1)), match.group(2).strip()
        lines.append(SourceLine(line_no=line_no, text=text, tags=tag_line(text)))
    return lines
