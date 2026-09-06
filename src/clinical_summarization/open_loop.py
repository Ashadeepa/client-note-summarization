"""Open-loop detection (stretch capability, docs/design.md Section 1/5):
find an ordered test/referral with no documented result anywhere in the note.

Deliberately simple substring join for the vertical slice — a real system
would join structured orders/results tables where they exist, falling back to
free-text matching only where structured joins fail (docs/design.md, Section 2).
"""

from __future__ import annotations

import re

from clinical_summarization.models import OpenLoop, SourceLine

_ORDER_PATTERN = re.compile(r"^(.*?)\bordered\b(.*)$", re.I)


def _order_subject(text: str) -> str | None:
    match = _ORDER_PATTERN.match(text)
    if not match:
        return None
    subject = match.group(1).strip()
    return subject or None


def find_open_loops(lines: list[SourceLine]) -> list[OpenLoop]:
    open_loops: list[OpenLoop] = []
    all_text = " ".join(line.text.lower() for line in lines)
    for line in lines:
        if "order" not in line.tags:
            continue
        subject = _order_subject(line.text)
        if not subject:
            continue
        result_mentioned = any(
            token in all_text.replace(line.text.lower(), "", 1)
            for token in subject.lower().split()
            if len(token) > 3
        )
        if not result_mentioned:
            open_loops.append(
                OpenLoop(
                    description=f"{line.text.strip()} — no result in chart, confirm follow-up",
                    order_line=line.line_no,
                )
            )
    return open_loops
