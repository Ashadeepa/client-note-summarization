"""End-to-end orchestration for one encounter note.

Mirrors the walkthrough in docs/design.md, Section 5: ingest -> section
extraction -> generation (citation-bound) -> verification (independent,
citation-only) -> coverage check (deterministic gate) -> open-loop detection.

Generator and verifier are injected as callables so this stays a vertical
slice of the *architecture*, not a fixture of any one backend: pass the
deterministic stubs (offline, free, used in tests) or `LLMGenerator`/
`LLMVerifier` (real model calls, different models by default per
docs/design.md Section 2). No review UI, no audit log persistence, no
control plane yet — this proves the shape, especially that an unsupported
claim cannot silently reach the draft, before those layers are built.
"""

from __future__ import annotations

import os
from typing import Callable

from clinical_summarization.generator import stub_generate_section
from clinical_summarization.ingest import parse_note
from clinical_summarization.models import DraftSummary, GeneratedSentence, SourceLine, VerifierVerdict
from clinical_summarization.open_loop import find_open_loops
from clinical_summarization.section_extraction import extract_sections
from clinical_summarization.verifier import stub_verify
from clinical_summarization.coverage import check_coverage

GenerateSectionFn = Callable[[str, list[SourceLine]], list[GeneratedSentence]]
VerifyFn = Callable[[GeneratedSentence, list[SourceLine]], VerifierVerdict]


def _live_backends() -> tuple[GenerateSectionFn, VerifyFn]:
    from clinical_summarization.generator import LLMGenerator
    from clinical_summarization.verifier import LLMVerifier

    generator = LLMGenerator()
    verifier = LLMVerifier()
    return generator.generate_section, verifier.verify


def default_backends() -> tuple[GenerateSectionFn, VerifyFn]:
    """Backend selection is explicit opt-in to a paid API: set
    CLINICAL_SUMMARIZATION_BACKEND=live, or pass callables directly to
    run_pipeline. Defaults to the free, offline stubs."""
    if os.environ.get("CLINICAL_SUMMARIZATION_BACKEND", "stub").lower() == "live":
        return _live_backends()
    return stub_generate_section, stub_verify


def run_pipeline(
    raw_note: str,
    generate_section: GenerateSectionFn | None = None,
    verify: VerifyFn | None = None,
) -> DraftSummary:
    if generate_section is None or verify is None:
        default_generate, default_verify = default_backends()
        generate_section = generate_section or default_generate
        verify = verify or default_verify

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
