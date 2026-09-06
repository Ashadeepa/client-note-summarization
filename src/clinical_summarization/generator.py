"""Draft generation.

Must never emit prose first and attach citations after (docs/design.md,
Section 2: "retrofitted citation search is where hallucinated support gets
laundered into looking sourced"). The LLM is prompted one section's source
lines at a time and made to name the exact line it drew each sentence from,
via a structured output schema — not free text parsed after the fact.

`stub_generate_section` is a deterministic, offline stand-in with the same
signature as `LLMGenerator.generate_section`, used in tests and as the
default backend so nothing calls a paid API unless asked (see pipeline.py).
"""

from __future__ import annotations

from pydantic import BaseModel

from clinical_summarization.models import GeneratedSentence, SourceLine

DEFAULT_GENERATOR_MODEL = "claude-opus-5"

_SYSTEM_PROMPT = (
    "You draft sentences for one section of a clinical discharge summary from "
    "a set of line-numbered source lines. Rules:\n"
    "- Produce at most one sentence per source line.\n"
    "- Never combine facts from multiple lines into one sentence.\n"
    "- Never add, infer, or embellish anything the line doesn't literally state.\n"
    "- Set source_line to the exact line number the sentence is drawn from."
)


class _SentenceDraft(BaseModel):
    text: str
    source_line: int


class _SectionDraft(BaseModel):
    sentences: list[_SentenceDraft]


def stub_generate_sentence(section: str, line: SourceLine) -> GeneratedSentence:
    text = line.text.rstrip(".") + "."
    return GeneratedSentence(text=text, source_lines=(line.line_no,), section=section)


def stub_generate_section(section: str, lines: list[SourceLine]) -> list[GeneratedSentence]:
    return [stub_generate_sentence(section, line) for line in lines]


class LLMGenerator:
    """Real generator backend. Requires `pip install anthropic` and an
    ANTHROPIC_API_KEY (or another credential source the SDK resolves)."""

    def __init__(self, client=None, model: str = DEFAULT_GENERATOR_MODEL):
        import anthropic

        self.client = client or anthropic.Anthropic()
        self.model = model

    def generate_section(self, section: str, lines: list[SourceLine]) -> list[GeneratedSentence]:
        if not lines:
            return []

        source_block = "\n".join(f"line {line.line_no}: {line.text}" for line in lines)
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Section: {section}\n\nSource lines:\n{source_block}\n\n"
                        "Draft the sentences for this section."
                    ),
                }
            ],
            output_format=_SectionDraft,
        )
        draft = response.parsed_output
        valid_line_nos = {line.line_no for line in lines}
        return [
            GeneratedSentence(text=s.text, source_lines=(s.source_line,), section=section)
            for s in draft.sentences
            if s.source_line in valid_line_nos
        ]
