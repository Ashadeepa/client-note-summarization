"""Draft generation — stubbed.

Stands in for the real generator LLM call. It must never emit prose first and
attach citations after (docs/design.md, Section 2: "retrofitted citation
search is where hallucinated support gets laundered into looking sourced").
Every sentence is built directly from the source line(s) it cites, one line
in, one sentence out, so the binding is structural rather than trusted.

Swap `generate_sentence` for a real LLM call behind the same signature to
go from stub to production without touching the pipeline.
"""

from __future__ import annotations

from clinical_summarization.models import GeneratedSentence, SourceLine


def generate_sentence(section: str, line: SourceLine) -> GeneratedSentence:
    text = line.text.rstrip(".") + "."
    return GeneratedSentence(text=text, source_lines=(line.line_no,), section=section)


def generate_section(section: str, lines: list[SourceLine]) -> list[GeneratedSentence]:
    return [generate_sentence(section, line) for line in lines]
