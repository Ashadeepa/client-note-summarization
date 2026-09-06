"""Route tagged source lines to summary sections."""

from __future__ import annotations

from clinical_summarization.models import SourceLine
from clinical_summarization.schema import SECTION_ROUTING


def extract_sections(lines: list[SourceLine]) -> dict[str, list[SourceLine]]:
    sections: dict[str, list[SourceLine]] = {section: [] for section in SECTION_ROUTING}
    for line in lines:
        for section, tags in SECTION_ROUTING.items():
            if any(tag in line.tags for tag in tags):
                sections[section].append(line)
    return sections
