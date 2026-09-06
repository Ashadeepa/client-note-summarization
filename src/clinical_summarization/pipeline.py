"""End-to-end orchestration for one encounter note.

Mirrors the walkthrough in docs/design.md, Section 5: ingest -> section
extraction -> generation (citation-bound) -> verification (independent,
citation-only) -> coverage check (deterministic gate) -> open-loop detection.

This is a vertical slice: one path through the architecture with mocked
generator/verifier logic, no review UI, no audit log persistence, no control
plane. It exists to prove the shape — especially that an unsupported claim
cannot silently reach the draft — before any of those layers are built.
"""

from __future__ import annotations

from clinical_summarization.generator import generate_section
from clinical_summarization.ingest import parse_note
from clinical_summarization.models import DraftSummary, VerifierVerdict
from clinical_summarization.open_loop import find_open_loops
from clinical_summarization.section_extraction import extract_sections
from clinical_summarization.verifier import verify
from clinical_summarization.coverage import check_coverage


def run_pipeline(raw_note: str) -> DraftSummary:
    lines = parse_note(raw_note)
    lines_by_no = {line.line_no: line for line in lines}
    sections = extract_sections(lines)

    verdicts_by_section: dict[str, list[VerifierVerdict]] = {}
    for section, section_lines in sections.items():
        sentences = generate_section(section, section_lines)
        verdicts = []
        for sentence in sentences:
            cited_lines = [lines_by_no[no] for no in sentence.source_lines]
            verdicts.append(verify(sentence, cited_lines))
        verdicts_by_section[section] = verdicts

    coverage = check_coverage(verdicts_by_section)
    open_loops = find_open_loops(lines)

    return DraftSummary(
        sections=verdicts_by_section,
        coverage=coverage,
        open_loops=open_loops,
    )
